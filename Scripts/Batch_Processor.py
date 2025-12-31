#!/usr/bin/env python3
"""Batch tile processor for Ortho4XP."""

from __future__ import annotations

import os
import shutil
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
    Config,
    apply_directory_overrides,
    compute_config_hash,
    load_config,
    load_state,
    make_tile_id,
    run_batch,
    save_state,
    update_run_metadata,
    validate_config,
)

app = typer.Typer(
    help="Batch tile processor for Ortho4XP",
    no_args_is_help=True,
)


def write_ortho4xp_cfg(config: Config) -> None:
    """Write Ortho4XP.cfg from batch config before module imports.

    This must be called before importing Ortho4XP modules so they
    pick up the settings on load.

    Args:
        config: Batch configuration
    """
    cfg_path = Ortho4XP_dir / "Ortho4XP.cfg"

    lines = []

    # App settings
    app = config.app
    lines.append(f"verbosity={app.verbosity}")
    lines.append(f"cleaning_level={app.cleaning_level}")
    lines.append(f"overpass_server_choice={app.overpass_server_choice}")
    lines.append(f"skip_downloads={app.skip_downloads}")
    lines.append(f"skip_converts={app.skip_converts}")
    lines.append(f"max_download_slots={app.max_download_slots}")
    lines.append(f"max_convert_slots={app.max_convert_slots}")
    lines.append(f"check_tms_response={app.check_tms_response}")
    lines.append(f"http_timeout={app.http_timeout}")
    lines.append(f"max_connect_retries={app.max_connect_retries}")
    lines.append(f"max_baddata_retries={app.max_baddata_retries}")
    lines.append(f"ovl_exclude_pol={app.ovl_exclude_pol}")
    lines.append(f"ovl_exclude_net={app.ovl_exclude_net}")
    lines.append(f"custom_scenery_dir={app.custom_scenery_dir}")
    lines.append(f"custom_overlay_src={app.custom_overlay_src}")
    lines.append(f"custom_overlay_src_alternate={app.custom_overlay_src_alternate}")

    # Tile settings (as global defaults)
    # Note: default_website and default_zl are tile-only, not valid in global config
    tile = config.tile
    lines.append(f"curvature_tol={tile.curvature_tol}")
    lines.append(f"apt_curv_tol={tile.apt_curv_tol}")
    lines.append(f"apt_curv_ext={tile.apt_curv_ext}")
    lines.append(f"coast_curv_tol={tile.coast_curv_tol}")
    lines.append(f"coast_curv_ext={tile.coast_curv_ext}")
    lines.append(f"limit_tris={tile.limit_tris}")
    lines.append(f"min_angle={tile.min_angle}")
    lines.append(f"mesh_zl={tile.mesh_zl}")
    lines.append(f"mask_zl={tile.mask_zl}")
    lines.append(f"clean_bad_geometries={tile.clean_bad_geometries}")
    lines.append(f"masks_width={tile.masks_width}")
    lines.append(f"masking_mode={tile.masking_mode}")
    lines.append(f"use_masks_for_inland={tile.use_masks_for_inland}")
    lines.append(f"imprint_masks_to_dds={tile.imprint_masks_to_dds}")
    lines.append(f"fill_nodata={tile.fill_nodata}")

    cfg_path.write_text("\n".join(lines) + "\n")


def init_ortho4xp(config: Config | None = None) -> bool:
    """Initialize Ortho4XP environment.

    Args:
        config: Optional batch config to apply directory overrides

    Returns:
        True if initialization succeeded, False otherwise
    """
    try:
        import O4_File_Names as FNAMES

        # Apply custom directory paths before anything else
        if config:
            apply_directory_overrides(config.batch)

        sys.path.append(FNAMES.Provider_dir)

        # Check utils directory
        if not os.path.isdir(FNAMES.Utils_dir):
            print("Error: Missing utils directory, check your install.")
            return False

        # Create required directories
        for directory in (
            FNAMES.Preview_dir,
            FNAMES.Provider_dir,
            FNAMES.Extent_dir,
            FNAMES.Filter_dir,
            FNAMES.OSM_dir,
            FNAMES.Mask_dir,
            FNAMES.Imagery_dir,
            FNAMES.Elevation_dir,
            FNAMES.Geotiff_dir,
            FNAMES.Patch_dir,
            FNAMES.Tile_dir,
            FNAMES.Tmp_dir,
        ):
            if not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)

        # Initialize providers
        import O4_Imagery_Utils as IMG

        IMG.initialize_extents_dict()
        IMG.initialize_color_filters_dict()
        IMG.initialize_providers_dict()
        IMG.initialize_combined_providers_dict()

        return True
    except ImportError as e:
        print(f"Error: Failed to import Ortho4XP modules: {e}")
        return False


def create_ortho4xp_callbacks(output_dir: Path) -> dict:
    """Create callbacks that use Ortho4XP processing functions.

    Args:
        output_dir: Output directory for generated tiles

    Returns:
        Dict of processing callbacks
    """
    import O4_Config_Utils as CFG
    import O4_Mask_Utils as MASK
    import O4_Mesh_Utils as MESH
    import O4_Overlay_Utils as OVL
    import O4_Tile_Utils as TILE
    import O4_Vector_Map as VMAP

    def build_poly_file(lat: int, lon: int, tile_cfg, custom_dem: Path | None):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if VMAP.build_poly_file(tile) == 0:
            raise RuntimeError("build_poly_file failed")

    def build_mesh(lat: int, lon: int, tile_cfg, custom_dem: Path | None):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if MESH.build_mesh(tile) == 0:
            raise RuntimeError("build_mesh failed")

    def build_masks(lat: int, lon: int, tile_cfg, custom_dem: Path | None):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if MASK.build_masks(tile) == 0:
            raise RuntimeError("build_masks failed")

    def build_tile(lat: int, lon: int, tile_cfg, custom_dem: Path | None):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if TILE.build_tile(tile) == 0:
            raise RuntimeError("build_tile failed")
        OVL.build_overlay(lat, lon)

    def _create_tile(lat: int, lon: int, tile_cfg, custom_dem: Path | None):
        """Create an Ortho4XP Tile object with config applied."""
        # Ensure trailing slash so build_dir creates tile subdirectory
        output_path = str(output_dir)
        if not output_path.endswith(("/", "\\")):
            output_path += "/"
        tile = CFG.Tile(lat, lon, output_path)
        tile.make_dirs()
        tile.read_from_config(use_global=True)

        # Apply tile config values
        for field in tile_cfg.__dataclass_fields__:
            value = getattr(tile_cfg, field)
            if hasattr(tile, field):
                setattr(tile, field, value)

        # Apply custom DEM if found
        if custom_dem:
            tile.custom_dem = str(custom_dem)

        tile.write_to_config()
        return tile

    return {
        "build_poly_file": build_poly_file,
        "build_mesh": build_mesh,
        "build_masks": build_masks,
        "build_tile": build_tile,
    }


def copy_overlays(config: Config) -> None:
    """Copy overlay files to output directory."""
    source_overlay_dir = Ortho4XP_dir / "yOrtho4XP_Overlays"
    target_overlay_dir = config.batch.output_dir / "yOrtho4XP_Overlays"

    if source_overlay_dir.exists():
        if target_overlay_dir.exists():
            shutil.rmtree(target_overlay_dir)
        shutil.copytree(source_overlay_dir, target_overlay_dir)


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
        write_ortho4xp_cfg(cfg)
        if not init_ortho4xp(cfg):
            raise typer.Exit(code=1)
        callbacks = create_ortho4xp_callbacks(cfg.batch.output_dir)

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
        copy_overlays(cfg)

    # Print summary
    typer.echo(f"\nSummary: {total} tiles processed, {succeeded} succeeded, {failed} failed")

    if failed > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
