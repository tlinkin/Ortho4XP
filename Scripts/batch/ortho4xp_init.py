"""Ortho4XP initialization utilities.

This module provides shared initialization logic used by both:
- Batch_Processor.py (sequential processing)
- pipeline.py (parallel worker processes)

Extracted to ensure identical initialization in both modes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def setup_paths(ortho4xp_dir: str) -> None:
    """Configure sys.path and working directory for Ortho4XP imports.

    Args:
        ortho4xp_dir: Path to the Ortho4XP root directory
    """
    os.chdir(ortho4xp_dir)
    sys.path.insert(0, ortho4xp_dir)
    sys.path.insert(0, str(Path(ortho4xp_dir) / "src"))


def apply_directory_overrides(config_dict: dict[str, Any]) -> None:
    """Apply custom directory paths to O4_File_Names module.

    Args:
        config_dict: Dictionary with optional directory override keys:
            osm_dir, elevation_dir, orthophotos_dir, masks_dir,
            geotiffs_dir, patches_dir, tmp_dir
    """
    import O4_File_Names as FNAMES

    if config_dict.get("osm_dir"):
        FNAMES.OSM_dir = config_dict["osm_dir"]
    if config_dict.get("elevation_dir"):
        FNAMES.Elevation_dir = config_dict["elevation_dir"]
    if config_dict.get("orthophotos_dir"):
        FNAMES.Imagery_dir = config_dict["orthophotos_dir"]
    if config_dict.get("masks_dir"):
        FNAMES.Mask_dir = config_dict["masks_dir"]
    if config_dict.get("geotiffs_dir"):
        FNAMES.Geotiff_dir = config_dict["geotiffs_dir"]
    if config_dict.get("patches_dir"):
        FNAMES.Patch_dir = config_dict["patches_dir"]
    if config_dict.get("tmp_dir"):
        FNAMES.Tmp_dir = config_dict["tmp_dir"]


def create_directories() -> None:
    """Create required Ortho4XP directories if they don't exist."""
    import O4_File_Names as FNAMES

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


def initialize_providers() -> None:
    """Initialize imagery provider dictionaries."""
    import O4_Imagery_Utils as IMG

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()


def init_ortho4xp(
    ortho4xp_dir: str,
    config_dict: dict[str, Any] | None = None,
    skip_validation: bool = False,
) -> bool:
    """Initialize Ortho4XP environment.

    This is the main entry point for initialization. It:
    1. Sets up sys.path for imports
    2. Applies any directory overrides
    3. Creates required directories
    4. Initializes provider dictionaries

    Args:
        ortho4xp_dir: Path to the Ortho4XP root directory
        config_dict: Optional dictionary with directory overrides
        skip_validation: If True, skip utils directory check

    Returns:
        True if initialization succeeded, False otherwise
    """
    try:
        setup_paths(ortho4xp_dir)

        import O4_File_Names as FNAMES

        # Apply custom directory paths before anything else
        if config_dict:
            apply_directory_overrides(config_dict)

        sys.path.append(FNAMES.Provider_dir)

        # Check utils directory (optional)
        if not skip_validation and not os.path.isdir(FNAMES.Utils_dir):
            print("Error: Missing utils directory, check your install.")
            return False

        # Create required directories
        create_directories()

        # Initialize providers
        initialize_providers()

        return True

    except ImportError as e:
        print(f"Error: Failed to import Ortho4XP modules: {e}")
        return False


def batch_config_to_dict(batch_config) -> dict[str, Any]:
    """Convert BatchConfig to serializable dict for init functions.

    Args:
        batch_config: BatchConfig object with optional directory paths

    Returns:
        Dictionary suitable for apply_directory_overrides()
    """
    return {
        "osm_dir": str(batch_config.osm_dir) if batch_config.osm_dir else None,
        "elevation_dir": str(batch_config.elevation_dir) if batch_config.elevation_dir else None,
        "orthophotos_dir": str(batch_config.orthophotos_dir) if batch_config.orthophotos_dir else None,
        "masks_dir": str(batch_config.masks_dir) if batch_config.masks_dir else None,
        "geotiffs_dir": str(batch_config.geotiffs_dir) if batch_config.geotiffs_dir else None,
        "patches_dir": str(batch_config.patches_dir) if batch_config.patches_dir else None,
        "tmp_dir": str(batch_config.tmp_dir) if batch_config.tmp_dir else None,
    }


def write_ortho4xp_cfg(
    ortho4xp_dir: str,
    app_config,
    tile_config,
) -> None:
    """Write Ortho4XP.cfg from batch config before module imports.

    This must be called before importing Ortho4XP modules so they
    pick up the settings on load.

    Args:
        ortho4xp_dir: Path to Ortho4XP root directory
        app_config: AppConfig object with app-level settings
        tile_config: TileConfig object with tile defaults
    """
    cfg_path = Path(ortho4xp_dir) / "Ortho4XP.cfg"

    lines = []

    # App settings
    lines.append(f"verbosity={app_config.verbosity}")
    lines.append(f"cleaning_level={app_config.cleaning_level}")
    lines.append(f"overpass_server_choice={app_config.overpass_server_choice}")
    lines.append(f"skip_downloads={app_config.skip_downloads}")
    lines.append(f"skip_converts={app_config.skip_converts}")
    lines.append(f"max_download_slots={app_config.max_download_slots}")
    lines.append(f"max_convert_slots={app_config.max_convert_slots}")
    lines.append(f"masks_build_slots={app_config.masks_build_slots}")
    lines.append(f"check_tms_response={app_config.check_tms_response}")
    lines.append(f"http_timeout={app_config.http_timeout}")
    lines.append(f"max_connect_retries={app_config.max_connect_retries}")
    lines.append(f"max_baddata_retries={app_config.max_baddata_retries}")
    lines.append(f"ovl_exclude_pol={app_config.ovl_exclude_pol}")
    lines.append(f"ovl_exclude_net={app_config.ovl_exclude_net}")
    lines.append(f"custom_scenery_dir={app_config.custom_scenery_dir}")
    lines.append(f"custom_overlay_src={app_config.custom_overlay_src}")
    lines.append(f"custom_overlay_src_alternate={app_config.custom_overlay_src_alternate}")

    # Tile settings (as global defaults)
    # Note: default_website and default_zl are tile-only, not valid in global config
    lines.append(f"curvature_tol={tile_config.curvature_tol}")
    lines.append(f"apt_curv_tol={tile_config.apt_curv_tol}")
    lines.append(f"apt_curv_ext={tile_config.apt_curv_ext}")
    lines.append(f"coast_curv_tol={tile_config.coast_curv_tol}")
    lines.append(f"coast_curv_ext={tile_config.coast_curv_ext}")
    lines.append(f"limit_tris={tile_config.limit_tris}")
    lines.append(f"min_angle={tile_config.min_angle}")
    lines.append(f"mesh_zl={tile_config.mesh_zl}")
    lines.append(f"mask_zl={tile_config.mask_zl}")
    lines.append(f"clean_bad_geometries={tile_config.clean_bad_geometries}")
    lines.append(f"masks_width={tile_config.masks_width}")
    lines.append(f"masking_mode={tile_config.masking_mode}")
    lines.append(f"use_masks_for_inland={tile_config.use_masks_for_inland}")
    lines.append(f"imprint_masks_to_dds={tile_config.imprint_masks_to_dds}")
    lines.append(f"fill_nodata={tile_config.fill_nodata}")

    cfg_path.write_text("\n".join(lines) + "\n")


def create_ortho4xp_callbacks(output_dir: str) -> dict:
    """Create callbacks that use Ortho4XP processing functions.

    Args:
        output_dir: Output directory for generated tiles (as string)

    Returns:
        Dict of processing callbacks
    """
    import O4_Config_Utils as CFG
    import O4_Mask_Utils as MASK
    import O4_Mesh_Utils as MESH
    import O4_Overlay_Utils as OVL
    import O4_Tile_Utils as TILE
    import O4_Vector_Map as VMAP

    def build_poly_file(lat: int, lon: int, tile_cfg, custom_dem):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if VMAP.build_poly_file(tile) == 0:
            raise RuntimeError("build_poly_file failed")

    def build_mesh(lat: int, lon: int, tile_cfg, custom_dem):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if MESH.build_mesh(tile) == 0:
            raise RuntimeError("build_mesh failed")

    def build_masks(lat: int, lon: int, tile_cfg, custom_dem):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if MASK.build_masks(tile) == 0:
            raise RuntimeError("build_masks failed")

    def build_tile(lat: int, lon: int, tile_cfg, custom_dem):
        tile = _create_tile(lat, lon, tile_cfg, custom_dem)
        if TILE.build_tile(tile) == 0:
            raise RuntimeError("build_tile failed")
        OVL.build_overlay(lat, lon)

    def _create_tile(lat: int, lon: int, tile_cfg, custom_dem):
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
