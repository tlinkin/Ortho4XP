"""TOML configuration loading and validation for batch processing."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from .state import make_tile_id


class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


@dataclass
class BatchConfig:
    """Batch processing configuration."""

    output_dir: Path
    dem_dir: Path
    state_file: Path = field(default_factory=lambda: Path("batch_state.toml"))
    # Optional data directory overrides (None = use Ortho4XP defaults)
    osm_dir: Path | None = None
    elevation_dir: Path | None = None
    orthophotos_dir: Path | None = None
    masks_dir: Path | None = None
    geotiffs_dir: Path | None = None
    patches_dir: Path | None = None
    tmp_dir: Path | None = None


@dataclass
class SourcesConfig:
    """Tile source configuration."""

    countries: list[str] = field(default_factory=list)
    tiles: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class AppConfig:
    """Application-level config (maps to cfg_app_vars)."""

    verbosity: int = 1
    cleaning_level: int = 1
    overpass_server_choice: str = "random"
    skip_downloads: bool = False
    skip_converts: bool = False
    max_download_slots: int = 1
    max_convert_slots: int = 4
    masks_build_slots: int = 4
    check_tms_response: bool = True
    http_timeout: float = 10.0
    max_connect_retries: int = 5
    max_baddata_retries: int = 5
    ovl_exclude_pol: list[int] = field(default_factory=lambda: [0])
    ovl_exclude_net: list[int] = field(default_factory=list)
    custom_scenery_dir: str = ""
    custom_overlay_src: str = ""
    custom_overlay_src_alternate: str = ""


@dataclass
class PipelineConfig:
    """Pipeline processing configuration."""

    enabled: bool = False  # Use pipelined batch processing
    prep_workers: int = 2  # Parallel tiles in prep stage (OSM+mesh+masks)
    dsf_workers: int = 1  # Parallel tiles in DSF stage (usually 1)


@dataclass
class TileConfig:
    """Per-tile config (maps to cfg_tile_vars)."""

    # Vector
    apt_smoothing_pix: int = 8
    road_level: int = 1
    road_banking_limit: float = 0.5
    lane_width: float = 4.0
    max_levelled_segs: int = 200000
    water_simplification: float = 0.0
    min_area: float = 0.001
    max_area: float = 200.0
    clean_bad_geometries: bool = True
    mesh_zl: int = 19

    # Mesh
    curvature_tol: float = 2.0
    apt_curv_tol: float = 0.5
    apt_curv_ext: float = 0.5
    coast_curv_tol: float = 1.0
    coast_curv_ext: float = 0.5
    limit_tris: float = 3.0
    min_angle: float = 10.0
    sea_smoothing_mode: str = "zero"
    water_smoothing: int = 10
    iterate: int = 0

    # Masks
    mask_zl: int = 14
    masks_width: int | list[int] = 100
    masking_mode: str = "sand"
    use_masks_for_inland: bool = False
    imprint_masks_to_dds: bool = False
    distance_masks_too: bool = False
    masks_use_DEM_too: bool = False
    masks_custom_extent: str = ""

    # DSF/Imagery
    default_website: str = ""
    default_zl: int = 16
    zone_list: list = field(default_factory=list)
    cover_airports_with_highres: str = "False"
    cover_extent: float = 1.0
    cover_zl: int = 18
    sea_texture_blur: float = 0.0
    water_tech: str = "XP11 + bathy"
    ratio_water: float = 0.25
    ratio_bathy: float = 1.0
    normal_map_strength: float = 1.0
    terrain_casts_shadows: bool = True
    overlay_lod: float = 25000.0
    use_decal_on_terrain: bool = False

    # Other
    custom_dem: str = ""
    fill_nodata: bool = True


@dataclass
class Config:
    """Root configuration container."""

    batch: BatchConfig
    sources: SourcesConfig
    app: AppConfig = field(default_factory=AppConfig)
    tile: TileConfig = field(default_factory=TileConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    tile_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in path.

    Args:
        path: Path string that may contain ~ or $VAR/${VAR}

    Returns:
        Expanded Path object
    """
    # Expand environment variables first
    expanded = os.path.expandvars(path)
    # Then expand user home directory
    expanded = os.path.expanduser(expanded)
    return Path(expanded)


def _parse_tiles_list(tiles_data: list) -> list[tuple[int, int]]:
    """Parse tiles from TOML list format to tuples.

    Args:
        tiles_data: List of [lat, lon] pairs from TOML

    Returns:
        List of (lat, lon) tuples
    """
    result = []
    for item in tiles_data:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            result.append((int(item[0]), int(item[1])))
    return result


def load_config(path: Path) -> Config:
    """Load and validate TOML config file.

    Args:
        path: Path to TOML configuration file

    Returns:
        Parsed Config object

    Raises:
        ConfigError: If file not found, parse error, or missing required fields
    """
    path = Path(path)

    # Check file exists
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    # Parse TOML
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML parse error: {e}") from e

    # Validate required sections
    if "batch" not in data:
        raise ConfigError("Missing required [batch] section")

    batch_data = data.get("batch", {})

    # Validate required fields
    if "output_dir" not in batch_data:
        raise ConfigError("Missing required field: batch.output_dir")
    if "dem_dir" not in batch_data:
        raise ConfigError("Missing required field: batch.dem_dir")

    # Build BatchConfig
    batch_config = BatchConfig(
        output_dir=expand_path(batch_data["output_dir"]),
        dem_dir=expand_path(batch_data["dem_dir"]),
        state_file=Path(batch_data.get("state_file", "batch_state.toml")),
        osm_dir=expand_path(batch_data["osm_dir"]) if batch_data.get("osm_dir") else None,
        elevation_dir=expand_path(batch_data["elevation_dir"]) if batch_data.get("elevation_dir") else None,
        orthophotos_dir=expand_path(batch_data["orthophotos_dir"]) if batch_data.get("orthophotos_dir") else None,
        masks_dir=expand_path(batch_data["masks_dir"]) if batch_data.get("masks_dir") else None,
        geotiffs_dir=expand_path(batch_data["geotiffs_dir"]) if batch_data.get("geotiffs_dir") else None,
        patches_dir=expand_path(batch_data["patches_dir"]) if batch_data.get("patches_dir") else None,
        tmp_dir=expand_path(batch_data["tmp_dir"]) if batch_data.get("tmp_dir") else None,
    )

    # Build SourcesConfig
    sources_data = data.get("sources", {})
    sources_config = SourcesConfig(
        countries=sources_data.get("countries", []),
        tiles=_parse_tiles_list(sources_data.get("tiles", [])),
    )

    # Build AppConfig with defaults
    app_data = data.get("app", {})
    app_config = AppConfig()
    for fld in fields(AppConfig):
        if fld.name in app_data:
            setattr(app_config, fld.name, app_data[fld.name])

    # Build TileConfig with defaults
    tile_data = data.get("tile", {})
    tile_config = TileConfig()
    for fld in fields(TileConfig):
        if fld.name in tile_data:
            setattr(tile_config, fld.name, tile_data[fld.name])

    # Build PipelineConfig with defaults
    pipeline_data = data.get("pipeline", {})
    pipeline_config = PipelineConfig()
    for fld in fields(PipelineConfig):
        if fld.name in pipeline_data:
            setattr(pipeline_config, fld.name, pipeline_data[fld.name])

    # Get tile overrides
    tile_overrides = data.get("tile_overrides", {})

    return Config(
        batch=batch_config,
        sources=sources_config,
        app=app_config,
        tile=tile_config,
        pipeline=pipeline_config,
        tile_overrides=tile_overrides,
    )


def get_tile_config(config: Config, lat: int, lon: int) -> TileConfig:
    """Get merged tile config with any overrides applied.

    Args:
        config: Root configuration
        lat: Tile latitude
        lon: Tile longitude

    Returns:
        TileConfig with overrides merged in
    """
    # Start with base tile config
    tile_cfg = replace(config.tile)

    # Check for override using various ID formats
    tile_ids = [
        make_tile_id(lat, lon),  # +45-122
        f"{'+' if lat >= 0 else ''}{lat}{'+' if lon >= 0 else ''}{lon}",  # +45-122
        f"{'+' if lat >= 0 else ''}{lat}{'+' if lon >= 0 else ''}{lon:03d}",  # +45-122
    ]

    for tile_id in tile_ids:
        if tile_id in config.tile_overrides:
            overrides = config.tile_overrides[tile_id]
            for key, value in overrides.items():
                if hasattr(tile_cfg, key):
                    setattr(tile_cfg, key, value)
            break

    return tile_cfg


def validate_config(config: Config) -> list[str]:
    """Validate configuration and return list of errors.

    Args:
        config: Configuration to validate

    Returns:
        List of error/warning messages (empty if valid)
    """
    errors = []

    # Check output directory exists
    if not config.batch.output_dir.exists():
        errors.append(f"output_dir does not exist: {config.batch.output_dir}")

    # Check DEM directory exists
    if not config.batch.dem_dir.exists():
        errors.append(f"dem_dir does not exist: {config.batch.dem_dir}")

    # Check at least one source is specified
    if not config.sources.countries and not config.sources.tiles:
        errors.append("No sources specified: need at least one country or tile")

    # Validate zoom levels
    valid_mesh_zl = (16, 17, 18, 19, 20)
    if config.tile.mesh_zl not in valid_mesh_zl:
        errors.append(
            f"Invalid mesh_zl: {config.tile.mesh_zl} (must be one of {valid_mesh_zl})"
        )

    valid_mask_zl = (14, 15, 16)
    if config.tile.mask_zl not in valid_mask_zl:
        errors.append(
            f"Invalid mask_zl: {config.tile.mask_zl} (must be one of {valid_mask_zl})"
        )

    if not 10 <= config.tile.default_zl <= 20:
        errors.append(
            f"Invalid default_zl: {config.tile.default_zl} (must be between 10 and 20)"
        )

    # Validate custom directories (check parent exists so directory can be created)
    custom_dirs = [
        ("osm_dir", config.batch.osm_dir),
        ("elevation_dir", config.batch.elevation_dir),
        ("orthophotos_dir", config.batch.orthophotos_dir),
        ("masks_dir", config.batch.masks_dir),
        ("geotiffs_dir", config.batch.geotiffs_dir),
        ("patches_dir", config.batch.patches_dir),
        ("tmp_dir", config.batch.tmp_dir),
    ]
    for name, path in custom_dirs:
        if path and not path.exists() and not path.parent.exists():
            errors.append(f"{name} parent directory does not exist: {path.parent}")

    return errors
