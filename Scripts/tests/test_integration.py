"""Integration tests for batch processing system."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from batch import (
    BatchState,
    Config,
    BatchConfig,
    SourcesConfig,
    AppConfig,
    TileConfig,
    compute_config_hash,
    load_config,
    load_state,
    run_batch,
    save_state,
    make_tile_id,
    TileStatus,
)


class TestFullWorkflow:
    """Integration tests for the complete batch workflow."""

    def test_full_batch_workflow(self, tmp_path):
        """Test complete batch processing workflow."""
        # Setup directories
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        # Create DEM file for one tile
        (dem_dir / "N45W122.hgt").write_bytes(b"fake dem")

        # Create config
        config = Config(
            batch=BatchConfig(
                output_dir=output_dir,
                dem_dir=dem_dir,
                state_file=Path("batch_state.toml"),
            ),
            sources=SourcesConfig(
                countries=[],
                tiles=[(45, -122), (46, -123)],
            ),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        # Create state
        state = BatchState()

        # Mock callbacks
        processed_tiles = []
        callbacks = {
            "build_poly_file": lambda *args: processed_tiles.append(("vector", args[0], args[1])),
            "build_mesh": lambda *args: processed_tiles.append(("mesh", args[0], args[1])),
            "build_masks": lambda *args: processed_tiles.append(("masks", args[0], args[1])),
            "build_tile": lambda *args: processed_tiles.append(("tile", args[0], args[1])),
        }

        # Run batch
        total, succeeded, failed = run_batch(
            config=config,
            state=state,
            config_hash="test_hash",
            callbacks=callbacks,
        )

        # Verify results
        assert total == 2
        assert succeeded == 2
        assert failed == 0

        # Verify all steps were called for both tiles
        assert len(processed_tiles) == 8  # 4 steps × 2 tiles

        # Verify state was updated
        assert state.tiles["+45-122"].status == TileStatus.COMPLETED
        assert state.tiles["+46-123"].status == TileStatus.COMPLETED

    def test_state_persistence_across_runs(self, tmp_path):
        """Test that state persists correctly between runs."""
        # Setup
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()
        state_path = output_dir / "batch_state.toml"

        config = Config(
            batch=BatchConfig(
                output_dir=output_dir,
                dem_dir=dem_dir,
            ),
            sources=SourcesConfig(tiles=[(45, -122), (46, -123), (47, -124)]),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        # First run - process first two tiles
        state1 = BatchState()
        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        # Only process first two tiles by marking third as "future"
        config_first = Config(
            batch=config.batch,
            sources=SourcesConfig(tiles=[(45, -122), (46, -123)]),
            app=config.app,
            tile=config.tile,
            tile_overrides={},
        )

        run_batch(config_first, state1, config_hash="hash1", callbacks=callbacks)
        save_state(state1, state_path)

        # Second run - load state and add third tile
        state2 = load_state(state_path)

        # Verify completed tiles are preserved
        assert state2.tiles["+45-122"].status == TileStatus.COMPLETED
        assert state2.tiles["+46-123"].status == TileStatus.COMPLETED

        # Run with all three tiles - only new tile should process
        call_count = {"count": 0}
        def counting_callback(*args):
            call_count["count"] += 1

        callbacks2 = {
            "build_poly_file": counting_callback,
            "build_mesh": counting_callback,
            "build_masks": counting_callback,
            "build_tile": counting_callback,
        }

        total, succeeded, failed = run_batch(
            config, state2, config_hash="hash1", callbacks=callbacks2
        )

        # Only the new tile should be processed
        assert total == 1
        assert succeeded == 1
        assert call_count["count"] == 4  # 4 steps for 1 tile

    def test_retry_failed_tiles(self, tmp_path):
        """Test retry-failed flag behavior."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(tiles=[(45, -122), (46, -123)]),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        # First run - one tile fails
        state = BatchState()
        fail_tile = True

        def failing_callback(*args):
            nonlocal fail_tile
            if args[0] == 46 and fail_tile:
                raise RuntimeError("Simulated failure")

        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": failing_callback,
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        run_batch(config, state, callbacks=callbacks)

        assert state.tiles["+45-122"].status == TileStatus.COMPLETED
        assert state.tiles["+46-123"].status == TileStatus.FAILED

        # Second run without retry_failed - failed tile should be skipped
        fail_tile = False
        callbacks2 = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        total, _, _ = run_batch(config, state, callbacks=callbacks2, retry_failed=False)
        assert total == 0  # No tiles to process

        # Third run with retry_failed - failed tile should be retried
        total, succeeded, failed = run_batch(
            config, state, callbacks=callbacks2, retry_failed=True
        )
        assert total == 1
        assert succeeded == 1
        assert state.tiles["+46-123"].status == TileStatus.COMPLETED

    def test_force_reprocess(self, tmp_path):
        """Test force flag reprocesses all tiles."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(tiles=[(45, -122), (46, -123)]),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        # First run - complete all
        state = BatchState()
        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        run_batch(config, state, callbacks=callbacks)

        # Second run without force - no tiles processed
        total, _, _ = run_batch(config, state, callbacks=callbacks)
        assert total == 0

        # Third run with force - all tiles processed
        total, succeeded, _ = run_batch(config, state, callbacks=callbacks, force=True)
        assert total == 2
        assert succeeded == 2


class TestConfigTomlWorkflow:
    """Test loading and using TOML config files."""

    def test_load_and_process_from_toml(self, tmp_path):
        """Load config from TOML and run processing."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        # Create TOML config
        config_path = tmp_path / "batch_config.toml"
        config_path.write_text(f'''
[batch]
output_dir = "{output_dir}"
dem_dir = "{dem_dir}"

[sources]
tiles = [[45, -122], [46, -123]]

[tile]
default_zl = 17
iterate = 0

[tile_overrides."+45-122"]
iterate = 3
''')

        # Load config
        config = load_config(config_path)
        config_hash = compute_config_hash(config_path)

        assert config.batch.output_dir == output_dir
        assert len(config.sources.tiles) == 2
        assert config.tile_overrides["+45-122"]["iterate"] == 3

        # Run with loaded config
        state = BatchState()
        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        total, succeeded, _ = run_batch(
            config, state, config_hash=config_hash, callbacks=callbacks
        )

        assert total == 2
        assert succeeded == 2

    def test_config_change_triggers_reprocess(self, tmp_path):
        """Changing config hash triggers full reprocess."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = Config(
            batch=BatchConfig(output_dir=output_dir, dem_dir=dem_dir),
            sources=SourcesConfig(tiles=[(45, -122)]),
            app=AppConfig(),
            tile=TileConfig(),
            tile_overrides={},
        )

        # First run with hash1
        state = BatchState()
        callbacks = {
            "build_poly_file": MagicMock(),
            "build_mesh": MagicMock(),
            "build_masks": MagicMock(),
            "build_tile": MagicMock(),
        }

        run_batch(config, state, config_hash="hash1", callbacks=callbacks)
        state.config_hash = "hash1"

        # Second run with same hash - no tiles
        total, _, _ = run_batch(config, state, config_hash="hash1", callbacks=callbacks)
        assert total == 0

        # Third run with different hash - reprocess
        total, _, _ = run_batch(config, state, config_hash="hash2", callbacks=callbacks)
        assert total == 1


class TestCLIInterface:
    """Test command-line interface."""

    def test_cli_help(self):
        """CLI shows help without error."""
        result = subprocess.run(
            [sys.executable, "Batch_Processor.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--retry-failed" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--force" in result.stdout

    def test_cli_missing_config(self):
        """CLI errors when config not provided."""
        result = subprocess.run(
            [sys.executable, "Batch_Processor.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "config" in result.stderr.lower()

    def test_cli_nonexistent_config(self, tmp_path):
        """CLI errors for non-existent config file."""
        result = subprocess.run(
            [sys.executable, "Batch_Processor.py", "--config", str(tmp_path / "nonexistent.toml")],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_cli_dry_run(self, tmp_path):
        """CLI dry run doesn't require Ortho4XP."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config_path = tmp_path / "config.toml"
        config_path.write_text(f'''
[batch]
output_dir = "{output_dir}"
dem_dir = "{dem_dir}"

[sources]
tiles = [[45, -122]]
''')

        result = subprocess.run(
            [sys.executable, "Batch_Processor.py", "--config", str(config_path), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        # Dry run should succeed even without Ortho4XP
        assert "Dry run" in result.stdout
        assert "Summary:" in result.stdout
