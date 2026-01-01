"""State persistence for batch processing - tracks tile processing status."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TileStatus(Enum):
    """Status of a tile in the processing pipeline."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStep(Enum):
    """Processing pipeline steps."""

    VECTOR = "vector"
    MESH = "mesh"
    MASKS = "masks"
    TILE = "tile"


@dataclass
class TileState:
    """State of a single tile."""

    status: TileStatus = TileStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    steps_completed: list[str] = field(default_factory=list)
    last_step: str | None = None
    error: str | None = None


@dataclass
class BatchState:
    """Batch processing state container."""

    last_run: datetime | None = None
    config_hash: str = ""
    tiles: dict[str, TileState] = field(default_factory=dict)


def _now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _format_datetime(dt: datetime) -> str:
    """Format datetime for TOML output."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_datetime(s: str) -> datetime:
    """Parse datetime from TOML format."""
    # Handle both with and without Z suffix
    s = s.rstrip("Z")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        # Try alternate format
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def compute_config_hash(config_path: Path) -> str:
    """Compute hash of config file for change detection.

    Args:
        config_path: Path to config file

    Returns:
        SHA256 hash of file contents (first 12 chars)
    """
    if not config_path.exists():
        return ""
    content = config_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:12]


def make_tile_id(lat: int, lon: int) -> str:
    """Create tile ID string from coordinates.

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)

    Returns:
        Tile ID string like "+45-122" or "-45+010"
    """
    lat_sign = "+" if lat >= 0 else ""
    lon_sign = "+" if lon >= 0 else ""
    return f"{lat_sign}{lat}{lon_sign}{lon:03d}"


def parse_tile_id(tile_id: str) -> tuple[int, int]:
    """Parse tile ID string to (lat, lon) tuple.

    Inverse of make_tile_id().

    Args:
        tile_id: Tile ID like "+45-122" or "-45+010"

    Returns:
        Tuple of (lat, lon) integers

    Raises:
        ValueError: If tile_id format is invalid
    """
    import re
    # Match: optional sign + digits, then required sign + digits
    match = re.match(r'^([+-]?\d+)([+-]\d+)$', tile_id)
    if not match:
        raise ValueError(f"Invalid tile ID format: {tile_id}")
    return int(match.group(1)), int(match.group(2))


def load_state(path: Path) -> BatchState:
    """Load state from TOML file.

    Args:
        path: Path to state file

    Returns:
        BatchState object (empty state if file doesn't exist)
    """
    if not path.exists():
        return BatchState()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    state = BatchState()

    # Load metadata
    metadata = data.get("metadata", {})
    if "last_run" in metadata:
        state.last_run = _parse_datetime(metadata["last_run"])
    state.config_hash = metadata.get("config_hash", "")

    # Load tiles
    tiles_data = data.get("tiles", {})
    for tile_id, tile_data in tiles_data.items():
        tile_state = TileState()
        tile_state.status = TileStatus(tile_data.get("status", "pending"))
        if "started_at" in tile_data:
            tile_state.started_at = _parse_datetime(tile_data["started_at"])
        if "completed_at" in tile_data:
            tile_state.completed_at = _parse_datetime(tile_data["completed_at"])
        if "failed_at" in tile_data:
            tile_state.failed_at = _parse_datetime(tile_data["failed_at"])
        tile_state.steps_completed = tile_data.get("steps_completed", [])
        tile_state.last_step = tile_data.get("last_step")
        tile_state.error = tile_data.get("error")
        state.tiles[tile_id] = tile_state

    return state


def save_state(state: BatchState, path: Path) -> None:
    """Save state to TOML file.

    Args:
        state: BatchState to save
        path: Path to write state file
    """
    lines = []

    # Metadata section
    lines.append("[metadata]")
    if state.last_run:
        lines.append(f'last_run = "{_format_datetime(state.last_run)}"')
    if state.config_hash:
        lines.append(f'config_hash = "{state.config_hash}"')
    lines.append("")

    # Tiles section
    lines.append("[tiles]")
    for tile_id, tile_state in sorted(state.tiles.items()):
        lines.append(f'[tiles."{tile_id}"]')
        lines.append(f'status = "{tile_state.status.value}"')
        if tile_state.started_at:
            lines.append(f'started_at = "{_format_datetime(tile_state.started_at)}"')
        if tile_state.completed_at:
            lines.append(
                f'completed_at = "{_format_datetime(tile_state.completed_at)}"'
            )
        if tile_state.failed_at:
            lines.append(f'failed_at = "{_format_datetime(tile_state.failed_at)}"')
        if tile_state.steps_completed:
            steps = ", ".join(f'"{s}"' for s in tile_state.steps_completed)
            lines.append(f"steps_completed = [{steps}]")
        if tile_state.last_step:
            lines.append(f'last_step = "{tile_state.last_step}"')
        if tile_state.error:
            # Escape quotes and use multiline if needed
            error = tile_state.error.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'error = "{error}"')
        lines.append("")

    path.write_text("\n".join(lines))


def mark_tile_started(state: BatchState, tile_id: str) -> None:
    """Mark a tile as in progress.

    Args:
        state: BatchState to update
        tile_id: Tile identifier
    """
    if tile_id not in state.tiles:
        state.tiles[tile_id] = TileState()
    state.tiles[tile_id].status = TileStatus.IN_PROGRESS
    state.tiles[tile_id].started_at = _now()


def mark_tile_completed(
    state: BatchState, tile_id: str, steps: list[str] | None = None
) -> None:
    """Mark a tile as completed.

    Args:
        state: BatchState to update
        tile_id: Tile identifier
        steps: List of completed steps (defaults to all)
    """
    if tile_id not in state.tiles:
        state.tiles[tile_id] = TileState()

    tile = state.tiles[tile_id]
    tile.status = TileStatus.COMPLETED
    tile.completed_at = _now()
    tile.steps_completed = steps or [s.value for s in ProcessingStep]
    tile.error = None
    tile.failed_at = None


def mark_tile_failed(
    state: BatchState, tile_id: str, error: str, last_step: str | None = None
) -> None:
    """Mark a tile as failed.

    Args:
        state: BatchState to update
        tile_id: Tile identifier
        error: Error message
        last_step: Last step that was attempted
    """
    if tile_id not in state.tiles:
        state.tiles[tile_id] = TileState()

    tile = state.tiles[tile_id]
    tile.status = TileStatus.FAILED
    tile.failed_at = _now()
    tile.error = error
    if last_step:
        tile.last_step = last_step


def mark_step_completed(state: BatchState, tile_id: str, step: str) -> None:
    """Mark a processing step as completed for a tile.

    Args:
        state: BatchState to update
        tile_id: Tile identifier
        step: Step name that completed
    """
    if tile_id not in state.tiles:
        state.tiles[tile_id] = TileState()

    tile = state.tiles[tile_id]
    if step not in tile.steps_completed:
        tile.steps_completed.append(step)
    tile.last_step = step


def get_tiles_to_process(
    state: BatchState,
    all_tiles: list[str],
    retry_failed: bool = False,
    force: bool = False,
    current_config_hash: str = "",
) -> list[str]:
    """Get list of tiles that need processing.

    Args:
        state: Current batch state
        all_tiles: List of all tile IDs to potentially process
        retry_failed: If True, include failed tiles
        force: If True, reprocess all tiles regardless of status
        current_config_hash: Hash of current config (triggers reprocess if changed)

    Returns:
        List of tile IDs to process
    """
    # Force reprocesses everything
    if force:
        return list(all_tiles)

    # Config change triggers full reprocess
    if current_config_hash and state.config_hash:
        if current_config_hash != state.config_hash:
            return list(all_tiles)

    result = []
    for tile_id in all_tiles:
        tile_state = state.tiles.get(tile_id)

        if tile_state is None:
            # Never processed
            result.append(tile_id)
        elif tile_state.status == TileStatus.COMPLETED:
            # Skip completed tiles
            continue
        elif tile_state.status == TileStatus.FAILED:
            # Include failed if retry_failed is set
            if retry_failed:
                result.append(tile_id)
        else:
            # Pending or in_progress (interrupted)
            result.append(tile_id)

    return result


def update_run_metadata(state: BatchState, config_hash: str) -> None:
    """Update run metadata.

    Args:
        state: BatchState to update
        config_hash: Hash of config file used for this run
    """
    state.last_run = _now()
    state.config_hash = config_hash
