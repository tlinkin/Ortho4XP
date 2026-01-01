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
