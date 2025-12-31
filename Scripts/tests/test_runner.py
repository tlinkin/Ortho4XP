"""Tests for batch runner functionality."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from batch.config import (
    AppConfig,
    BatchConfig,
    Config,
    SourcesConfig,
    TileConfig,
)
from batch.runner import (
    apply_tile_overrides,
    build_tile_list,
    find_dem_for_tile,
    process_tile,
    run_batch,
)
from batch.state import BatchState, TileStatus, make_tile_id, mark_tile_completed


@pytest.fixture
def basic_config(tmp_path):
    """Create a basic config for testing."""
    output_dir = tmp_path / "output"
    dem_dir = tmp_path / "dem"
    output_dir.mkdir()
    dem_dir.mkdir()

    return Config(
        batch=BatchConfig(
            output_dir=output_dir,
            dem_dir=dem_dir,
        ),
        sources=SourcesConfig(
            countries=[],
            tiles=[(45, -122), (46, -123)],
        ),
        app=AppConfig(),
        tile=TileConfig(),
        tile_overrides={},
    )


class TestBuildTileList:
    """Tests for tile list building."""

    def test_build_tile_list_from_coords(self, basic_config):
        """Direct coords work."""
        tiles = build_tile_list(basic_config)
        assert (45, -122) in tiles
        assert (46, -123) in tiles
        assert len(tiles) == 2

    def test_combined_sources_deduplicated(self, tmp_path):
        """Countries + coords deduplicated."""
        # Create config with duplicate coords
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(
                countries=[],  # No countries to avoid network calls
                tiles=[(45, -122), (45, -122), (46, -123)],  # Duplicate
            ),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        tiles = build_tile_list(config)
        # Duplicates should be removed
        assert len(tiles) == 2
        assert (45, -122) in tiles
        assert (46, -123) in tiles

    def test_empty_sources(self, tmp_path):
        """Empty sources returns empty list."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(countries=[], tiles=[]),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        tiles = build_tile_list(config)
        assert tiles == []


class TestFindDemForTile:
    """Tests for DEM file matching."""

    def test_dem_auto_detection(self, tmp_path):
        """DEM files matched to tiles by coords."""
        dem_dir = tmp_path / "dem"
        dem_dir.mkdir()

        # Create a DEM file
        dem_file = dem_dir / "N45W122.hgt"
        dem_file.write_bytes(b"fake dem data")

        result = find_dem_for_tile(45, -122, dem_dir)
        assert result == dem_file

    def test_dem_case_insensitive(self, tmp_path):
        """DEM matching is case-insensitive."""
        dem_dir = tmp_path / "dem"
        dem_dir.mkdir()

        # Create lowercase DEM file
        dem_file = dem_dir / "n45w122.hgt"
        dem_file.write_bytes(b"fake dem data")

        result = find_dem_for_tile(45, -122, dem_dir)
        assert result == dem_file

    def test_dem_not_found(self, tmp_path):
        """Returns None when no matching DEM."""
        dem_dir = tmp_path / "dem"
        dem_dir.mkdir()

        result = find_dem_for_tile(45, -122, dem_dir)
        assert result is None

    def test_dem_dir_not_exists(self, tmp_path):
        """Returns None when DEM dir doesn't exist."""
        dem_dir = tmp_path / "nonexistent"
        result = find_dem_for_tile(45, -122, dem_dir)
        assert result is None

    def test_dem_positive_coords(self, tmp_path):
        """Handles positive lat/lon correctly."""
        dem_dir = tmp_path / "dem"
        dem_dir.mkdir()

        dem_file = dem_dir / "N45E010.hgt"
        dem_file.write_bytes(b"fake dem data")

        result = find_dem_for_tile(45, 10, dem_dir)
        assert result == dem_file

    def test_dem_negative_coords(self, tmp_path):
        """Handles negative lat/lon correctly."""
        dem_dir = tmp_path / "dem"
        dem_dir.mkdir()

        dem_file = dem_dir / "S45W122.hgt"
        dem_file.write_bytes(b"fake dem data")

        result = find_dem_for_tile(-45, -122, dem_dir)
        assert result == dem_file


class TestApplyTileOverrides:
    """Tests for per-tile config overrides."""

    def test_apply_tile_overrides(self, tmp_path):
        """Per-tile config applied correctly."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(tiles=[(45, -122)]),
            app=AppConfig(),
            tile=TileConfig(iterate=0, default_zl=16),
            tile_overrides={
                "+45-122": {"iterate": 3, "custom_dem": "/path/to/dem.hgt"}
            },
        )

        overrides = apply_tile_overrides(config, 45, -122)
        assert overrides["iterate"] == 3
        assert overrides["custom_dem"] == "/path/to/dem.hgt"
        assert overrides["default_zl"] == 16  # Non-overridden value

    def test_no_override_gets_defaults(self, tmp_path):
        """Non-overridden tile gets base tile config."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(tiles=[(46, -123)]),
            app=AppConfig(),
            tile=TileConfig(iterate=0, default_zl=17),
            tile_overrides={"+45-122": {"iterate": 3}},  # Different tile
        )

        overrides = apply_tile_overrides(config, 46, -123)
        assert overrides["iterate"] == 0  # Default value
        assert overrides["default_zl"] == 17


class TestProcessTile:
    """Tests for tile processing."""

    def test_process_tile_success(self, basic_config):
        """Full pipeline runs on mock."""
        state = BatchState()

        # Mock callbacks that succeed
        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        success = process_tile(45, -122, basic_config, state, callbacks=callbacks)

        assert success is True
        tile_id = make_tile_id(45, -122)
        assert state.tiles[tile_id].status == TileStatus.COMPLETED
        assert "vector" in state.tiles[tile_id].steps_completed
        assert "tile" in state.tiles[tile_id].steps_completed

        # Verify callbacks were called
        callbacks["build_poly_file"].assert_called_once()
        callbacks["build_mesh"].assert_called_once()

    def test_process_tile_failure_recovery(self, basic_config):
        """State updated on failure."""
        state = BatchState()

        # Mock callbacks with one that fails
        def failing_mesh(*args, **kwargs):
            raise RuntimeError("Mesh generation failed")

        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": failing_mesh,
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        success = process_tile(45, -122, basic_config, state, callbacks=callbacks)

        assert success is False
        tile_id = make_tile_id(45, -122)
        assert state.tiles[tile_id].status == TileStatus.FAILED
        assert "Mesh generation failed" in state.tiles[tile_id].error
        assert state.tiles[tile_id].last_step == "vector"  # Last completed step

    def test_process_tile_dry_run(self, basic_config):
        """Dry run doesn't execute callbacks."""
        state = BatchState()
        callbacks = {"build_poly_file": MagicMock()}

        success = process_tile(
            45, -122, basic_config, state, dry_run=True, callbacks=callbacks
        )

        assert success is True
        callbacks["build_poly_file"].assert_not_called()


class TestRunBatch:
    """Tests for batch processing."""

    def test_run_batch_processes_all_tiles(self, basic_config):
        """Batch processes all tiles."""
        state = BatchState()
        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        total, succeeded, failed = run_batch(
            basic_config, state, callbacks=callbacks
        )

        assert total == 2
        assert succeeded == 2
        assert failed == 0

    def test_run_batch_skips_completed(self, basic_config):
        """Skips already-completed tiles."""
        state = BatchState()
        mark_tile_completed(state, "+45-122")

        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        total, succeeded, failed = run_batch(
            basic_config, state, callbacks=callbacks
        )

        assert total == 1  # Only one tile processed
        assert succeeded == 1

    def test_run_batch_dry_run(self, basic_config):
        """Dry run doesn't process tiles."""
        state = BatchState()
        callbacks = {"build_poly_file": MagicMock()}

        total, succeeded, failed = run_batch(
            basic_config, state, dry_run=True, callbacks=callbacks
        )

        assert total == 2
        assert succeeded == 2
        callbacks["build_poly_file"].assert_not_called()

    def test_run_batch_callbacks(self, basic_config):
        """Progress callbacks are called."""
        state = BatchState()
        started_tiles = []
        completed_tiles = []

        def on_start(lat, lon):
            started_tiles.append((lat, lon))

        def on_complete(lat, lon, success):
            completed_tiles.append((lat, lon, success))

        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        run_batch(
            basic_config, state, callbacks=callbacks,
            on_tile_start=on_start, on_tile_complete=on_complete
        )

        assert len(started_tiles) == 2
        assert len(completed_tiles) == 2
        assert all(success for _, _, success in completed_tiles)
