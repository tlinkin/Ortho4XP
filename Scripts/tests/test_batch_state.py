"""Tests for batch state persistence."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from batch.state import (
    BatchState,
    TileState,
    TileStatus,
    compute_config_hash,
    get_tiles_to_process,
    load_state,
    make_tile_id,
    mark_step_completed,
    mark_tile_completed,
    mark_tile_failed,
    mark_tile_started,
    save_state,
    update_run_metadata,
)


class TestLoadState:
    """Tests for state file loading."""

    def test_create_new_state_file(self, tmp_path):
        """Creates empty state when file missing."""
        state_path = tmp_path / "batch_state.toml"
        state = load_state(state_path)
        assert state.tiles == {}
        assert state.last_run is None
        assert state.config_hash == ""

    def test_load_existing_state(self, tmp_path):
        """Loads previous state correctly."""
        state_path = tmp_path / "batch_state.toml"
        state_path.write_text('''
[metadata]
last_run = "2025-12-31T10:00:00Z"
config_hash = "abc123"

[tiles]
[tiles."+45-122"]
status = "completed"
completed_at = "2025-12-31T10:30:00Z"
steps_completed = ["vector", "mesh", "masks", "tile"]
''')
        state = load_state(state_path)
        assert state.config_hash == "abc123"
        assert state.last_run is not None
        assert "+45-122" in state.tiles
        assert state.tiles["+45-122"].status == TileStatus.COMPLETED
        assert len(state.tiles["+45-122"].steps_completed) == 4

    def test_load_failed_tile_state(self, tmp_path):
        """Loads failed tile state with error message."""
        state_path = tmp_path / "batch_state.toml"
        state_path.write_text('''
[metadata]
last_run = "2025-12-31T10:00:00Z"

[tiles]
[tiles."+46-123"]
status = "failed"
failed_at = "2025-12-31T11:00:00Z"
error = "HTTP timeout on imagery download"
last_step = "tile"
''')
        state = load_state(state_path)
        tile = state.tiles["+46-123"]
        assert tile.status == TileStatus.FAILED
        assert tile.error == "HTTP timeout on imagery download"
        assert tile.last_step == "tile"


class TestSaveState:
    """Tests for state file saving."""

    def test_save_and_reload_state(self, tmp_path):
        """State survives round-trip save/load."""
        state_path = tmp_path / "batch_state.toml"
        state = BatchState()
        state.config_hash = "def456"
        state.last_run = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

        tile = TileState()
        tile.status = TileStatus.COMPLETED
        tile.completed_at = datetime(2025, 12, 31, 12, 30, 0, tzinfo=timezone.utc)
        tile.steps_completed = ["vector", "mesh"]
        state.tiles["+45-122"] = tile

        save_state(state, state_path)
        reloaded = load_state(state_path)

        assert reloaded.config_hash == "def456"
        assert "+45-122" in reloaded.tiles
        assert reloaded.tiles["+45-122"].status == TileStatus.COMPLETED
        assert reloaded.tiles["+45-122"].steps_completed == ["vector", "mesh"]


class TestMarkTileCompleted:
    """Tests for marking tiles as completed."""

    def test_mark_tile_completed(self):
        """Updates tile status to completed."""
        state = BatchState()
        mark_tile_completed(state, "+45-122", ["vector", "mesh", "masks", "tile"])

        tile = state.tiles["+45-122"]
        assert tile.status == TileStatus.COMPLETED
        assert tile.completed_at is not None
        assert tile.steps_completed == ["vector", "mesh", "masks", "tile"]

    def test_mark_tile_completed_default_steps(self):
        """Uses default steps when none specified."""
        state = BatchState()
        mark_tile_completed(state, "+45-122")

        tile = state.tiles["+45-122"]
        assert "vector" in tile.steps_completed
        assert "tile" in tile.steps_completed


class TestMarkTileFailed:
    """Tests for marking tiles as failed."""

    def test_mark_tile_failed(self):
        """Records failure with error message."""
        state = BatchState()
        mark_tile_failed(state, "+46-123", "HTTP timeout on imagery download", "tile")

        tile = state.tiles["+46-123"]
        assert tile.status == TileStatus.FAILED
        assert tile.failed_at is not None
        assert tile.error == "HTTP timeout on imagery download"
        assert tile.last_step == "tile"

    def test_mark_tile_failed_clears_on_retry(self):
        """Completing a previously failed tile clears error."""
        state = BatchState()
        mark_tile_failed(state, "+45-122", "Some error")
        mark_tile_completed(state, "+45-122")

        tile = state.tiles["+45-122"]
        assert tile.status == TileStatus.COMPLETED
        assert tile.error is None
        assert tile.failed_at is None


class TestGetTilesToProcess:
    """Tests for filtering tiles based on state."""

    def test_skip_completed_tiles(self):
        """Filter out already-completed tiles."""
        state = BatchState()
        mark_tile_completed(state, "+45-122")

        all_tiles = ["+45-122", "+46-123", "+47-124"]
        to_process = get_tiles_to_process(state, all_tiles)

        assert "+45-122" not in to_process
        assert "+46-123" in to_process
        assert "+47-124" in to_process

    def test_resume_failed_tile(self):
        """--retry-failed flag reprocesses failed tiles."""
        state = BatchState()
        mark_tile_failed(state, "+46-123", "Some error")
        mark_tile_completed(state, "+45-122")

        all_tiles = ["+45-122", "+46-123", "+47-124"]

        # Without retry_failed - failed tile excluded
        to_process = get_tiles_to_process(state, all_tiles, retry_failed=False)
        assert "+46-123" not in to_process

        # With retry_failed - failed tile included
        to_process = get_tiles_to_process(state, all_tiles, retry_failed=True)
        assert "+46-123" in to_process

    def test_reprocess_on_config_change(self):
        """Config hash change triggers reprocess."""
        state = BatchState()
        state.config_hash = "old_hash"
        mark_tile_completed(state, "+45-122")
        mark_tile_completed(state, "+46-123")

        all_tiles = ["+45-122", "+46-123", "+47-124"]

        # Same hash - skip completed
        to_process = get_tiles_to_process(
            state, all_tiles, current_config_hash="old_hash"
        )
        assert "+45-122" not in to_process
        assert "+46-123" not in to_process

        # Different hash - reprocess all
        to_process = get_tiles_to_process(
            state, all_tiles, current_config_hash="new_hash"
        )
        assert "+45-122" in to_process
        assert "+46-123" in to_process
        assert "+47-124" in to_process

    def test_force_reprocess_all(self):
        """Force flag reprocesses everything."""
        state = BatchState()
        mark_tile_completed(state, "+45-122")
        mark_tile_completed(state, "+46-123")

        all_tiles = ["+45-122", "+46-123", "+47-124"]
        to_process = get_tiles_to_process(state, all_tiles, force=True)

        assert len(to_process) == 3
        assert "+45-122" in to_process


class TestConfigHash:
    """Tests for config hash computation."""

    def test_compute_config_hash(self, tmp_path):
        """Computes consistent hash for file."""
        config = tmp_path / "config.toml"
        config.write_text('[batch]\noutput_dir = "/tmp"')

        hash1 = compute_config_hash(config)
        hash2 = compute_config_hash(config)

        assert hash1 == hash2
        assert len(hash1) == 12  # First 12 chars of SHA256

    def test_hash_changes_on_content_change(self, tmp_path):
        """Hash changes when content changes."""
        config = tmp_path / "config.toml"
        config.write_text('[batch]\noutput_dir = "/tmp"')
        hash1 = compute_config_hash(config)

        config.write_text('[batch]\noutput_dir = "/other"')
        hash2 = compute_config_hash(config)

        assert hash1 != hash2

    def test_hash_empty_for_missing_file(self, tmp_path):
        """Returns empty string for non-existent file."""
        config = tmp_path / "nonexistent.toml"
        assert compute_config_hash(config) == ""


class TestMakeTileId:
    """Tests for tile ID generation."""

    def test_positive_coords(self):
        """Handles positive coordinates."""
        assert make_tile_id(45, 10) == "+45+010"

    def test_negative_coords(self):
        """Handles negative coordinates."""
        assert make_tile_id(-45, -122) == "-45-122"

    def test_mixed_coords(self):
        """Handles mixed positive/negative."""
        assert make_tile_id(45, -122) == "+45-122"
        assert make_tile_id(-45, 10) == "-45+010"


class TestMarkStepCompleted:
    """Tests for step completion tracking."""

    def test_mark_step_completed(self):
        """Records step completion."""
        state = BatchState()
        mark_tile_started(state, "+45-122")
        mark_step_completed(state, "+45-122", "vector")
        mark_step_completed(state, "+45-122", "mesh")

        tile = state.tiles["+45-122"]
        assert tile.steps_completed == ["vector", "mesh"]
        assert tile.last_step == "mesh"

    def test_no_duplicate_steps(self):
        """Doesn't add duplicate steps."""
        state = BatchState()
        mark_step_completed(state, "+45-122", "vector")
        mark_step_completed(state, "+45-122", "vector")

        assert state.tiles["+45-122"].steps_completed == ["vector"]


class TestUpdateRunMetadata:
    """Tests for run metadata updates."""

    def test_update_run_metadata(self):
        """Updates last_run and config_hash."""
        state = BatchState()
        update_run_metadata(state, "new_hash_123")

        assert state.last_run is not None
        assert state.config_hash == "new_hash_123"
