"""Pipelined batch processing for improved resource utilization.

Runs prep stages (OSM, mesh, masks) for multiple tiles while DSF building
proceeds on completed tiles, keeping network saturated.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Queue
from typing import Callable

from .config import Config, TileConfig, get_tile_config
from .runner import find_dem_for_tile
from .state import (
    BatchState,
    ProcessingStep,
    make_tile_id,
    mark_step_completed,
    mark_tile_completed,
    mark_tile_failed,
    mark_tile_started,
    save_state,
)


class PipelineStage(Enum):
    """Pipeline stage for a tile."""

    PENDING = "pending"
    PREP = "prep"
    DSF = "dsf"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class TileJob:
    """Job representing a tile in the pipeline."""

    lat: int
    lon: int
    tile_cfg: TileConfig
    custom_dem: Path | None
    stage: PipelineStage = PipelineStage.PENDING
    error: str | None = None

    @property
    def tile_id(self) -> str:
        return make_tile_id(self.lat, self.lon)


class PipelineManager:
    """Manages pipelined batch processing.

    Runs prep workers (OSM + mesh + masks) in parallel with DSF workers
    (imagery download + conversion + DSF build) to maximize resource usage.
    """

    def __init__(
        self,
        config: Config,
        state: BatchState,
        state_path: Path,
        callbacks: dict[str, Callable],
        max_prep: int = 2,
        max_dsf: int = 1,
        on_tile_start: Callable[[int, int], None] | None = None,
        on_tile_complete: Callable[[int, int, bool], None] | None = None,
    ):
        """Initialize pipeline manager.

        Args:
            config: Batch configuration
            state: Batch state for tracking progress
            state_path: Path to save state file
            callbacks: Dict with keys: build_poly_file, build_mesh, build_masks, build_tile
            max_prep: Number of parallel prep workers
            max_dsf: Number of parallel DSF workers
            on_tile_start: Optional callback when tile starts
            on_tile_complete: Optional callback when tile completes
        """
        self.config = config
        self.state = state
        self.state_path = state_path
        self.callbacks = callbacks
        self.max_prep = max_prep
        self.max_dsf = max_dsf
        self.on_tile_start = on_tile_start
        self.on_tile_complete = on_tile_complete

        # Queues for passing work between stages
        self.prep_queue: Queue[TileJob | None] = Queue()
        self.dsf_queue: Queue[TileJob | None] = Queue()

        # Synchronization
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()

        # Counters
        self.succeeded = 0
        self.failed = 0

    def prep_worker(self, worker_id: int) -> None:
        """Worker thread for prep stage (OSM + mesh + masks).

        Args:
            worker_id: Worker identifier for logging
        """
        while not self.shutdown_event.is_set():
            job = self.prep_queue.get()
            if job is None:
                # Poison pill - shutdown signal
                break

            job.stage = PipelineStage.PREP

            try:
                # Step 1: Vector/OSM
                self.callbacks["build_poly_file"](
                    job.lat, job.lon, job.tile_cfg, job.custom_dem
                )
                with self.lock:
                    mark_step_completed(self.state, job.tile_id, ProcessingStep.VECTOR.value)

                # Step 2: Mesh
                self.callbacks["build_mesh"](
                    job.lat, job.lon, job.tile_cfg, job.custom_dem
                )
                with self.lock:
                    mark_step_completed(self.state, job.tile_id, ProcessingStep.MESH.value)

                # Step 2.5: Masks
                self.callbacks["build_masks"](
                    job.lat, job.lon, job.tile_cfg, job.custom_dem
                )
                with self.lock:
                    mark_step_completed(self.state, job.tile_id, ProcessingStep.MASKS.value)

                # Hand off to DSF stage
                self.dsf_queue.put(job)

            except Exception as e:
                job.stage = PipelineStage.FAILED
                job.error = str(e)
                print(f"ERROR: Prep failed for {job.tile_id}: {e}")
                with self.lock:
                    mark_tile_failed(self.state, job.tile_id, str(e), "prep")
                    self.failed += 1
                    self._save_state()
                if self.on_tile_complete:
                    self.on_tile_complete(job.lat, job.lon, False)

    def dsf_worker(self, worker_id: int) -> None:
        """Worker thread for DSF stage (imagery + conversion + DSF).

        Args:
            worker_id: Worker identifier for logging
        """
        while not self.shutdown_event.is_set():
            job = self.dsf_queue.get()
            if job is None:
                # Poison pill - shutdown signal
                break

            job.stage = PipelineStage.DSF

            try:
                # Step 3: Tile (downloads, converts, builds DSF)
                self.callbacks["build_tile"](
                    job.lat, job.lon, job.tile_cfg, job.custom_dem
                )

                # Mark completed
                job.stage = PipelineStage.COMPLETE
                completed_steps = [s.value for s in ProcessingStep]
                with self.lock:
                    mark_tile_completed(self.state, job.tile_id, completed_steps)
                    self.succeeded += 1
                    self._save_state()

                if self.on_tile_complete:
                    self.on_tile_complete(job.lat, job.lon, True)

            except Exception as e:
                job.stage = PipelineStage.FAILED
                job.error = str(e)
                print(f"ERROR: DSF failed for {job.tile_id}: {e}")
                with self.lock:
                    mark_tile_failed(self.state, job.tile_id, str(e), ProcessingStep.TILE.value)
                    self.failed += 1
                    self._save_state()
                if self.on_tile_complete:
                    self.on_tile_complete(job.lat, job.lon, False)

    def _save_state(self) -> None:
        """Save state to disk (must be called with lock held)."""
        save_state(self.state, self.state_path)

    def run(self, tiles: list[tuple[int, int]]) -> tuple[int, int, int]:
        """Run pipelined processing on all tiles.

        Args:
            tiles: List of (lat, lon) tuples to process

        Returns:
            Tuple of (total, succeeded, failed) counts
        """
        if not tiles:
            return 0, 0, 0

        # Create jobs for all tiles
        jobs: list[TileJob] = []
        for lat, lon in tiles:
            tile_cfg = get_tile_config(self.config, lat, lon)
            custom_dem = find_dem_for_tile(lat, lon, self.config.batch.dem_dir)
            job = TileJob(lat, lon, tile_cfg, custom_dem)
            jobs.append(job)

            # Mark started in state
            with self.lock:
                mark_tile_started(self.state, job.tile_id)
            if self.on_tile_start:
                self.on_tile_start(lat, lon)

        # Start worker threads
        prep_threads = [
            threading.Thread(target=self.prep_worker, args=(i,), daemon=True)
            for i in range(self.max_prep)
        ]
        dsf_threads = [
            threading.Thread(target=self.dsf_worker, args=(i,), daemon=True)
            for i in range(self.max_dsf)
        ]

        for t in prep_threads + dsf_threads:
            t.start()

        # Queue all jobs for prep stage
        for job in jobs:
            self.prep_queue.put(job)

        # Send poison pills to prep workers
        for _ in range(self.max_prep):
            self.prep_queue.put(None)

        # Wait for prep workers to finish
        for t in prep_threads:
            t.join()

        # Send poison pills to DSF workers
        for _ in range(self.max_dsf):
            self.dsf_queue.put(None)

        # Wait for DSF workers to finish
        for t in dsf_threads:
            t.join()

        return len(tiles), self.succeeded, self.failed

    def shutdown(self) -> None:
        """Signal shutdown to all workers."""
        self.shutdown_event.set()
