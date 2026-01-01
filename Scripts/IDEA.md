# Pipeline Mode: Process Isolation Solution

## The Problem

Ortho4XP's `src/` modules use extensive global state (module-level variables, shared configuration, etc.). When we tried to parallelize tile processing using Python threads, the threads shared this global state, causing conflicts:

```
Thread 1: build_poly_file(tile_A)  ─┐
                                    ├── Shared globals → CONFLICT
Thread 2: build_tile(tile_B)       ─┘
```

Even processing different tiles at different stages caused failures because the modules weren't designed for concurrent access.

## The Solution: Process Isolation

Instead of threads, we use **separate processes** via Python's `multiprocessing` module. Each process gets its own Python interpreter with completely isolated memory:

```
Process 1: [Own Python interpreter] → build_poly_file(tile_A)
Process 2: [Own Python interpreter] → build_tile(tile_B)
                ↑ No shared state - true isolation
```

### How It Works

1. **Main process** queues tiles to a `multiprocessing.Queue`
2. **Worker processes** (spawned fresh) each:
   - Change to Ortho4XP directory
   - Import modules fresh (each gets own globals)
   - Initialize providers
   - Process tiles from queue
   - Send results back via another queue
3. **Main process** collects results and updates state

### Key Benefits

- **True isolation**: Each worker has its own copy of all globals
- **No code changes to src/**: Works with existing Ortho4XP modules
- **Parallel tile processing**: Multiple tiles build simultaneously
- **Scales with CPU cores**: Set `prep_workers` to match your system

### Configuration

```toml
[pipeline]
enabled = true
prep_workers = 2  # Number of parallel worker processes
```

### Trade-offs

- **Process overhead**: Starting processes is heavier than threads
- **Memory usage**: Each process loads its own copy of modules
- **IPC overhead**: Data must be serialized between processes

For large batches (50+ tiles), these overheads are negligible compared to the time saved by parallel processing.

## Why Not Just Fix src/?

Making `src/` thread-safe would require:
- Identifying all global state
- Adding locks or making state thread-local
- Extensive testing for race conditions

Process isolation achieves parallelism without touching `src/` at all.
