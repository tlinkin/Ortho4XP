# Download queue stabilization plan

## Context
The latest iteration of `download_textures` introduces a `ThreadPoolExecutor` to
submit downloads from the queue and uses bounded queues to regulate back
pressure.【F:src/O4_Tile_Utils.py†L23-L109】【F:src/O4_Tile_Utils.py†L180-L204】
While this boosts throughput, it also adds several moving parts around
`schedule/wait` loops, duplicate filtering, queue limits, and progress tracking.
`DSF.build_dsf` continues to push work items and the terminating "quit" sentinel
into the download queue once geometry processing finishes.【F:src/O4_DSF_Utils.py†L720-L840】【F:src/O4_DSF_Utils.py†L1020-L1048】

## Observed pain points
1. **Busy spinning and race-prone state management** – The executor loop calls
   `concurrent.futures.wait(..., timeout=0)` on every iteration, which results in
   busy-waiting while juggling the `inflight` set and manual progress updates.【F:src/O4_Tile_Utils.py†L45-L103】
   This increases CPU load and leaves large sections of the logic outside the
   familiar `parallel_launch` helper that the rest of the codebase uses.
2. **Queue back-pressure ripple effects** – Both download and convert queues now
   have a hard `maxsize` of 512.【F:src/O4_Tile_Utils.py†L180-L204】 During large
   tiles, a slow DDS conversion step can fill `convert_queue`, which blocks
   download workers that try to `put` into it. That in turn prevents the download
   queue from draining, causing the DSF producer to stall on `put` calls.
3. **Progress tracking tied to `qsize()`** – The progress bar still divides by
   `done + download_queue.qsize()`.【F:src/O4_Tile_Utils.py†L40-L43】 With multiple
   workers and bounded queues, `qsize()` becomes more volatile, and we occasionally
   display regressions or division-by-zero edge cases when both values drop to
   zero momentarily.
4. **Duplicate suppression side effects** – The new `seen` set suppresses
   re-queued work, but `build_dsf` already guards against redundant texture
   requests. The extra dedupe can hide legitimate retries after transient errors
   (e.g., redownload after clearing `IMG.incomplete_imgs`).【F:src/O4_Tile_Utils.py†L74-L87】【F:src/O4_DSF_Utils.py†L720-L840】
5. **Cancellation propagation** – `UI.red_flag` is polled but there is no shared
   synchronisation primitive, so cancellation is discovered only on timeouts or
   after queue operations unblock. This makes it harder to shut down cleanly
   under error conditions compared with the existing worker abstractions.

## Proposed improvement steps
The overarching idea is to keep the original queue-driven architecture but let
multiple consumers process the download queue using the same idioms that the DDS
conversion step already employs. Each step is intentionally small and keeps the
existing APIs intact.

1. **Refactor the download worker loop to reuse the `parallel_worker` idiom**
   - Introduce a lightweight `download_worker` akin to `parallel_worker` that
     loops on `download_queue.get()` and stops on the "quit" sentinel, pushing
     work to `convert_queue` when successful. This keeps the multi-threading
     model close to the historical single-threaded version while still allowing
     multiple workers.
   - Replace the executor bookkeeping (`inflight`, `seen`, manual waits) with
     `parallel_launch` / `parallel_join`, mirroring the DDS conversion pipeline.
     That removes the busy-wait loop and leverages the well-tested worker pattern
     already present in `O4_Parallel_Utils`.【F:src/O4_Parallel_Utils.py†L1-L51】
   - Make the worker count configurable (defaulting to the previous value of 1
     for parity) so we can experiment safely without regressing low-end systems.

2. **Decouple queue sizing from hard-coded limits**
   - Remove the new `maxsize` settings so the queues remain unbounded as in the
     original implementation. This prevents the DSF producer from blocking when
     conversion throughput temporarily lags, improving overall stability on long
     builds.【F:src/O4_Tile_Utils.py†L180-L204】
   - Document the rationale for keeping the queue unbounded and rely on
     monitoring to catch pathological cases, instead of introducing configurable
     caps that risk reintroducing stalls.

3. **Stabilise progress accounting**
   - Track `total_enqueued` and `total_completed` counters protected by a lock
     instead of querying `qsize()` directly. Increment `total_enqueued` in the
     worker launcher when a job is fetched from the queue, and decrement on
     completion, so the denominator remains stable even with multiple threads.
   - Fall back to 100% when the DSF thread emits the sentinel and all workers
     have exited, ensuring deterministic completion updates.【F:src/O4_DSF_Utils.py†L1020-L1048】

4. **Improve cancellation and retry behaviour**
   - Use a `threading.Event` shared across workers to react immediately to
     `UI.red_flag` instead of polling inside the loop. Workers can check the
     event before fetching new items and abort promptly during shutdown.
   - Remove the extra `seen` filter and rely on the producer logic for deduping.
     This allows legitimate retry enqueues (for instance after removing damaged
     textures) to reach the workers again.【F:src/O4_Tile_Utils.py†L74-L87】
   - Surface download errors by re-queueing failed items a limited number of
     times, then record them in `IMG.incomplete_imgs` so the rest of the pipeline
     can react as before.【F:src/O4_Imagery_Utils.py†L1614-L1681】

5. **Validation plan**
   - Exercise single-tile builds with varying worker counts (1, 4, 8) to ensure
     deterministic shutdown and progress updates.
   - Simulate slow conversion by throttling `IMG.convert_texture` (e.g., via a
     debug flag) to confirm that bounded queues no longer deadlock the DSF
     producer.
   - Rebuild a tile after forcing white-square recovery (`IMG.incomplete_imgs`)
     to verify re-queued downloads are honoured.

These steps keep the public behaviour intact while reducing complexity and
borrowing existing concurrency patterns from the rest of the project, making the
new download queue more predictable without deviating from the original
codebase style.
