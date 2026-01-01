"""Pipelined batch processing using multiprocessing for true isolation.

Uses separate processes instead of threads to avoid global state conflicts
in the Ortho4XP modules. Each subprocess gets its own Python interpreter
with isolated globals.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config, TileConfig, get_tile_config
from .ortho4xp_init import init_ortho4xp
from .runner import find_dem_for_tile
from .state import (
    BatchState,
    ProcessingStep,
    make_tile_id,
    load_state,
    save_state,
    mark_tile_completed,
    mark_tile_failed,
)


@dataclass
class TileTask:
    """Serializable task for subprocess processing."""

    lat: int
    lon: int
    tile_cfg_dict: dict[str, Any]  # Serialized TileConfig
    custom_dem: str | None  # Path as string for serialization
    output_dir: str
    ortho4xp_dir: str


def _tile_cfg_to_dict(tile_cfg: TileConfig) -> dict[str, Any]:
    """Convert TileConfig to dict for pickling."""
    return {
        field: getattr(tile_cfg, field)
        for field in tile_cfg.__dataclass_fields__
    }


def _worker_process(
    task_queue: mp.Queue,
    result_queue: mp.Queue,
    ortho4xp_dir: str,
    config_dict: dict[str, Any],
) -> None:
    """Worker process that runs tile processing in isolation.

    Each worker has its own Python interpreter with isolated global state.

    Args:
        task_queue: Queue to receive TileTask objects
        result_queue: Queue to send results (tile_id, success, error)
        ortho4xp_dir: Path to Ortho4XP directory
        config_dict: Serialized batch config for directory overrides
    """
    # Initialize Ortho4XP in this process using shared init logic
    try:
        if not init_ortho4xp(ortho4xp_dir, config_dict, skip_validation=True):
            result_queue.put(("__init__", False, "Ortho4XP initialization failed"))
            return

        # Import processing modules
        import O4_Config_Utils as CFG
        import O4_Mask_Utils as MASK
        import O4_Mesh_Utils as MESH
        import O4_Overlay_Utils as OVL
        import O4_Tile_Utils as TILE
        import O4_UI_Utils as UI
        import O4_Vector_Map as VMAP

    except Exception as e:
        # Send initialization error and exit
        result_queue.put(("__init__", False, str(e)))
        return

    # Process tiles
    while True:
        task = task_queue.get()
        if task is None:
            # Poison pill - shutdown
            break

        tile_id = make_tile_id(task.lat, task.lon)

        # Reset UI flags to ensure clean state for each tile
        UI.is_working = 0
        UI.red_flag = 0

        try:
            # Create tile object
            output_path = task.output_dir
            if not output_path.endswith(("/", "\\")):
                output_path += "/"
            tile = CFG.Tile(task.lat, task.lon, output_path)
            tile.make_dirs()
            tile.read_from_config(use_global=True)

            # Apply tile config
            for key, value in task.tile_cfg_dict.items():
                if hasattr(tile, key):
                    setattr(tile, key, value)

            # Apply custom DEM
            if task.custom_dem:
                tile.custom_dem = task.custom_dem

            tile.write_to_config()

            # Step 1: Vector
            if VMAP.build_poly_file(tile) == 0:
                raise RuntimeError("build_poly_file failed")

            # Step 2: Mesh
            if MESH.build_mesh(tile) == 0:
                raise RuntimeError("build_mesh failed")

            # Step 2.5: Masks
            if MASK.build_masks(tile) == 0:
                raise RuntimeError("build_masks failed")

            # Step 3: Tile
            if TILE.build_tile(tile) == 0:
                raise RuntimeError("build_tile failed")

            # Step 4: Overlay
            OVL.build_overlay(task.lat, task.lon)

            result_queue.put((tile_id, True, None))

        except Exception as e:
            result_queue.put((tile_id, False, str(e)))


class PipelineManager:
    """Manages parallel batch processing using multiprocessing.

    Uses separate processes instead of threads to achieve true isolation
    of Ortho4XP's global state.
    """

    def __init__(
        self,
        config: Config,
        state: BatchState,
        state_path: Path,
        callbacks: dict | None = None,  # Not used, kept for API compatibility
        max_prep: int = 2,  # Now means max parallel processes
        max_dsf: int = 1,   # Not used, kept for API compatibility
        on_tile_start=None,
        on_tile_complete=None,
    ):
        """Initialize pipeline manager.

        Args:
            config: Batch configuration
            state: Batch state for tracking progress
            state_path: Path to save state file
            callbacks: Not used (processes create their own)
            max_prep: Number of parallel worker processes
            max_dsf: Not used (kept for API compatibility)
            on_tile_start: Optional callback when tile starts
            on_tile_complete: Optional callback when tile completes
        """
        self.config = config
        self.state = state
        self.state_path = state_path
        self.max_workers = max(1, max_prep)  # Use max_prep as worker count
        self.on_tile_start = on_tile_start
        self.on_tile_complete = on_tile_complete

        # Find Ortho4XP directory (parent of Scripts)
        self.ortho4xp_dir = str(Path(__file__).resolve().parent.parent.parent)

        # Prepare config dict for workers
        self.config_dict = {
            "osm_dir": str(config.batch.osm_dir) if config.batch.osm_dir else None,
            "elevation_dir": str(config.batch.elevation_dir) if config.batch.elevation_dir else None,
            "orthophotos_dir": str(config.batch.orthophotos_dir) if config.batch.orthophotos_dir else None,
            "masks_dir": str(config.batch.masks_dir) if config.batch.masks_dir else None,
            "geotiffs_dir": str(config.batch.geotiffs_dir) if config.batch.geotiffs_dir else None,
            "patches_dir": str(config.batch.patches_dir) if config.batch.patches_dir else None,
            "tmp_dir": str(config.batch.tmp_dir) if config.batch.tmp_dir else None,
        }

    def run(self, tiles: list[tuple[int, int]]) -> tuple[int, int, int]:
        """Run parallel processing on all tiles.

        Args:
            tiles: List of (lat, lon) tuples to process

        Returns:
            Tuple of (total, succeeded, failed) counts
        """
        if not tiles:
            return 0, 0, 0

        # Create queues
        task_queue: mp.Queue = mp.Queue()
        result_queue: mp.Queue = mp.Queue()

        # Start worker processes
        workers = []
        for _ in range(self.max_workers):
            p = mp.Process(
                target=_worker_process,
                args=(task_queue, result_queue, self.ortho4xp_dir, self.config_dict),
            )
            p.start()
            workers.append(p)

        # Queue all tasks
        output_dir = str(self.config.batch.output_dir)
        for lat, lon in tiles:
            tile_cfg = get_tile_config(self.config, lat, lon)
            custom_dem = find_dem_for_tile(lat, lon, self.config.batch.dem_dir)

            task = TileTask(
                lat=lat,
                lon=lon,
                tile_cfg_dict=_tile_cfg_to_dict(tile_cfg),
                custom_dem=str(custom_dem) if custom_dem else None,
                output_dir=output_dir,
                ortho4xp_dir=self.ortho4xp_dir,
            )
            task_queue.put(task)

            if self.on_tile_start:
                self.on_tile_start(lat, lon)

        # Send poison pills
        for _ in range(self.max_workers):
            task_queue.put(None)

        # Collect results
        succeeded = 0
        failed = 0
        results_collected = 0

        while results_collected < len(tiles):
            tile_id, success, error = result_queue.get()

            if tile_id == "__init__":
                # Worker initialization failed
                print(f"ERROR: Worker initialization failed: {error}")
                failed += len(tiles) - results_collected
                break

            results_collected += 1

            if success:
                succeeded += 1
                # Update state
                completed_steps = [s.value for s in ProcessingStep]
                mark_tile_completed(self.state, tile_id, completed_steps)
            else:
                failed += 1
                print(f"ERROR: {tile_id} failed: {error}")
                mark_tile_failed(self.state, tile_id, error or "Unknown error", "tile")

            save_state(self.state, self.state_path)

            # Parse tile_id back to lat/lon for callback
            if self.on_tile_complete:
                # Parse "+45-122" format
                parts = tile_id.replace("+", " +").replace("-", " -").split()
                if len(parts) >= 2:
                    try:
                        lat = int(parts[0])
                        lon = int(parts[1])
                        self.on_tile_complete(lat, lon, success)
                    except ValueError:
                        pass

        # Wait for workers to finish
        for p in workers:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()

        return len(tiles), succeeded, failed

    def shutdown(self) -> None:
        """Signal shutdown (not currently used with processes)."""
        pass
