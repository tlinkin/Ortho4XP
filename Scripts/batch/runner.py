"""Tile processing runner for batch operations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config, get_tile_config
from .state import (
    BatchState,
    ProcessingStep,
    get_tiles_to_process,
    make_tile_id,
    mark_step_completed,
    mark_tile_completed,
    mark_tile_failed,
    mark_tile_started,
)
from .tiles import list_tiles_for_countries


@dataclass
class TileProcessor:
    """Handles processing of a single tile."""

    lat: int
    lon: int
    config: Config
    output_dir: Path
    dem_dir: Path

    # Processing callbacks (for dependency injection/testing)
    build_poly_file: Callable | None = None
    build_mesh: Callable | None = None
    build_masks: Callable | None = None
    build_tile: Callable | None = None
    build_overlay: Callable | None = None


def build_tile_list(config: Config) -> list[tuple[int, int]]:
    """Build list of tile coordinates from config sources.

    Args:
        config: Configuration with sources

    Returns:
        List of (lat, lon) tuples, deduplicated and sorted
    """
    tiles: set[tuple[int, int]] = set()

    # Add tiles from direct coordinates
    for lat, lon in config.sources.tiles:
        tiles.add((lat, lon))

    # Add tiles from countries
    if config.sources.countries:
        country_tiles = list_tiles_for_countries(config.sources.countries)
        for lat, lon in country_tiles:
            tiles.add((lat, lon))

    return sorted(tiles)


def find_dem_for_tile(lat: int, lon: int, dem_dir: Path) -> Path | None:
    """Find DEM file matching tile coordinates.

    Args:
        lat: Tile latitude
        lon: Tile longitude
        dem_dir: Directory containing DEM files

    Returns:
        Path to DEM file if found, None otherwise
    """
    if not dem_dir.exists():
        return None

    # Build expected filename pattern (e.g., N45W122.hgt or n45w122.hgt)
    lat_char = "N" if lat >= 0 else "S"
    lon_char = "E" if lon >= 0 else "W"
    target = f"{lat_char}{abs(lat):02d}{lon_char}{abs(lon):03d}.hgt"

    for entry in os.listdir(dem_dir):
        if entry.lower() == target.lower():
            full_path = dem_dir / entry
            if full_path.is_file():
                return full_path

    return None


def apply_tile_overrides(config: Config, lat: int, lon: int) -> dict:
    """Get tile configuration with any overrides applied.

    Args:
        config: Root configuration
        lat: Tile latitude
        lon: Tile longitude

    Returns:
        Dictionary of tile configuration values
    """
    tile_cfg = get_tile_config(config, lat, lon)
    return {
        field: getattr(tile_cfg, field)
        for field in tile_cfg.__dataclass_fields__
    }


def process_tile(
    lat: int,
    lon: int,
    config: Config,
    state: BatchState,
    dry_run: bool = False,
    callbacks: dict | None = None,
) -> bool:
    """Process a single tile through the full pipeline.

    Args:
        lat: Tile latitude
        lon: Tile longitude
        config: Batch configuration
        state: Batch state for tracking progress
        dry_run: If True, don't actually process
        callbacks: Optional dict of step callbacks for testing

    Returns:
        True if successful, False if failed
    """
    tile_id = make_tile_id(lat, lon)
    callbacks = callbacks or {}

    if dry_run:
        return True

    mark_tile_started(state, tile_id)

    # Get tile config with overrides
    tile_cfg = get_tile_config(config, lat, lon)

    # Check for custom DEM
    custom_dem = find_dem_for_tile(lat, lon, config.batch.dem_dir)

    steps = [
        (ProcessingStep.VECTOR, callbacks.get("build_poly_file")),
        (ProcessingStep.MESH, callbacks.get("build_mesh")),
        (ProcessingStep.MASKS, callbacks.get("build_masks")),
        (ProcessingStep.TILE, callbacks.get("build_tile")),
    ]

    try:
        for step, callback in steps:
            if callback:
                callback(lat, lon, tile_cfg, custom_dem)
            mark_step_completed(state, tile_id, step.value)

        # Mark completed
        completed_steps = [s.value for s, _ in steps]
        mark_tile_completed(state, tile_id, completed_steps)
        return True

    except Exception as e:
        # Print error so user can see what failed
        print(f"ERROR: {e}")
        # Get last completed step
        tile_state = state.tiles.get(tile_id)
        last_step = tile_state.last_step if tile_state else None
        mark_tile_failed(state, tile_id, str(e), last_step)
        return False


def run_batch(
    config: Config,
    state: BatchState,
    state_path: Path | None = None,
    config_hash: str = "",
    retry_failed: bool = False,
    force: bool = False,
    dry_run: bool = False,
    callbacks: dict | None = None,
    on_tile_start: Callable[[int, int], None] | None = None,
    on_tile_complete: Callable[[int, int, bool], None] | None = None,
) -> tuple[int, int, int]:
    """Run batch processing on all tiles.

    Args:
        config: Batch configuration
        state: Batch state for tracking
        state_path: Path to state file (required for pipeline mode)
        config_hash: Hash of config file for change detection
        retry_failed: If True, retry failed tiles
        force: If True, reprocess all tiles
        dry_run: If True, don't actually process
        callbacks: Optional dict of processing callbacks
        on_tile_start: Called when tile processing starts
        on_tile_complete: Called when tile processing finishes

    Returns:
        Tuple of (total, succeeded, failed) counts
    """
    # Build tile list
    all_tiles = build_tile_list(config)
    tile_ids = [make_tile_id(lat, lon) for lat, lon in all_tiles]

    # Filter to tiles that need processing
    to_process_ids = get_tiles_to_process(
        state, tile_ids, retry_failed=retry_failed, force=force,
        current_config_hash=config_hash
    )

    # Convert back to coordinates
    to_process = [t for t in all_tiles if make_tile_id(*t) in to_process_ids]

    if not to_process:
        return 0, 0, 0

    # Use pipeline mode if enabled and we have callbacks
    if config.pipeline.enabled and callbacks and not dry_run:
        if state_path is None:
            raise ValueError("state_path required for pipeline mode")

        from .pipeline import PipelineManager

        manager = PipelineManager(
            config=config,
            state=state,
            state_path=state_path,
            callbacks=callbacks,
            max_prep=config.pipeline.prep_workers,
            max_dsf=config.pipeline.dsf_workers,
            on_tile_start=on_tile_start,
            on_tile_complete=on_tile_complete,
        )
        return manager.run(to_process)

    # Sequential processing (original behavior)
    succeeded = 0
    failed = 0

    for lat, lon in to_process:
        if on_tile_start:
            on_tile_start(lat, lon)

        success = process_tile(
            lat, lon, config, state,
            dry_run=dry_run, callbacks=callbacks
        )

        if success:
            succeeded += 1
        else:
            failed += 1

        if on_tile_complete:
            on_tile_complete(lat, lon, success)

    return len(to_process), succeeded, failed
