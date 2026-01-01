#!/usr/bin/env python3
"""Batch tile processor for Ortho4XP."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated

import typer

# ===== Path setup =====
Ortho4XP_dir = Path(__file__).resolve().parent.parent
Scripts_dir = Path(__file__).resolve().parent
Original_cwd = Path.cwd()  # Save before chdir for resolving relative paths
sys.path.insert(0, str(Scripts_dir))
sys.path.insert(0, str(Ortho4XP_dir / "src"))

# Change to Ortho4XP root (required by O4_File_Names path resolution)
os.chdir(Ortho4XP_dir)

# Import batch processing modules
from batch import (
    batch_config_to_dict,
    compute_config_hash,
    copy_overlays,
    create_ortho4xp_callbacks,
    init_ortho4xp,
    load_config,
    load_state,
    make_tile_id,
    run_batch,
    save_state,
    update_run_metadata,
    validate_config,
    write_ortho4xp_cfg,
)

app = typer.Typer(
    help="Batch tile processor for Ortho4XP",
    no_args_is_help=True,
)


@app.command()
def main(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to TOML configuration file"),
    ],
    retry_failed: Annotated[
        bool,
        typer.Option("--retry-failed", help="Retry previously failed tiles"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be processed"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Force reprocessing of all tiles"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
) -> None:
    """Process tiles in batch mode."""
    # Resolve config path against original working directory
    if not config.is_absolute():
        config = Original_cwd / config

    # Load configuration
    try:
        cfg = load_config(config)
    except Exception as e:
        typer.echo(f"Error loading config: {e}", err=True)
        raise typer.Exit(code=1)

    # Validate configuration
    errors = validate_config(cfg)
    if errors:
        typer.echo("Configuration errors:", err=True)
        for error in errors:
            typer.echo(f"  - {error}", err=True)
        raise typer.Exit(code=1)

    # Compute config hash for change detection
    config_hash = compute_config_hash(config)

    # Load state
    state_path = cfg.batch.output_dir / cfg.batch.state_file
    state = load_state(state_path)

    # Initialize Ortho4XP (skip for dry run)
    callbacks = None
    if not dry_run:
        # Write config BEFORE importing Ortho4XP modules
        write_ortho4xp_cfg(str(Ortho4XP_dir), cfg.app, cfg.tile)
        if not init_ortho4xp(str(Ortho4XP_dir), batch_config_to_dict(cfg.batch)):
            raise typer.Exit(code=1)
        callbacks = create_ortho4xp_callbacks(str(cfg.batch.output_dir))

    # Progress callbacks
    def on_tile_start(lat: int, lon: int):
        tile_id = make_tile_id(lat, lon)
        typer.echo(f"Processing {tile_id}...")

    def on_tile_complete(lat: int, lon: int, success: bool):
        tile_id = make_tile_id(lat, lon)
        status = "completed" if success else "FAILED"
        typer.echo(f"  {tile_id}: {status}")

    # Run batch processing
    typer.echo(f"Batch processing with config: {config}")
    if dry_run:
        typer.echo("(Dry run - no actual processing)")

    total, succeeded, failed = run_batch(
        config=cfg,
        state=state,
        state_path=state_path,
        config_hash=config_hash,
        retry_failed=retry_failed,
        force=force,
        dry_run=dry_run,
        callbacks=callbacks,
        on_tile_start=on_tile_start if verbose else None,
        on_tile_complete=on_tile_complete if verbose else None,
    )

    # Update run metadata and save state
    if not dry_run:
        update_run_metadata(state, config_hash)
        save_state(state, state_path)

        # Copy overlays
        copy_overlays(Ortho4XP_dir, cfg.batch.output_dir)

    # Print summary
    typer.echo(f"\nSummary: {total} tiles processed, {succeeded} succeeded, {failed} failed")

    if failed > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
