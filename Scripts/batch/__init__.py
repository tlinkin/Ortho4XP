"""Batch processing package for Ortho4XP."""

from .config import (
    Config,
    BatchConfig,
    SourcesConfig,
    AppConfig,
    TileConfig,
    PipelineConfig,
    ConfigError,
    load_config,
    expand_path,
    get_tile_config,
    validate_config,
)

from .state import (
    BatchState,
    TileState,
    TileStatus,
    ProcessingStep,
    compute_config_hash,
    load_state,
    save_state,
    make_tile_id,
    parse_tile_id,
    mark_tile_started,
    mark_tile_completed,
    mark_tile_failed,
    mark_step_completed,
    get_tiles_to_process,
    update_run_metadata,
)

from .runner import (
    build_tile_list,
    find_dem_for_tile,
    apply_tile_overrides,
    process_tile,
    run_batch,
    copy_overlays,
)

from .tiles import (
    list_tiles_for_countries,
    list_tiles_for_continent,
    list_tiles_for_geometry,
)

from .ortho4xp_init import (
    init_ortho4xp,
    apply_directory_overrides,
    batch_config_to_dict,
    write_ortho4xp_cfg,
    create_ortho4xp_callbacks,
)

__all__ = [
    # Config
    "Config",
    "BatchConfig",
    "SourcesConfig",
    "AppConfig",
    "TileConfig",
    "PipelineConfig",
    "ConfigError",
    "load_config",
    "expand_path",
    "get_tile_config",
    "validate_config",
    "apply_directory_overrides",
    # State
    "BatchState",
    "TileState",
    "TileStatus",
    "ProcessingStep",
    "compute_config_hash",
    "load_state",
    "save_state",
    "make_tile_id",
    "parse_tile_id",
    "mark_tile_started",
    "mark_tile_completed",
    "mark_tile_failed",
    "mark_step_completed",
    "get_tiles_to_process",
    "update_run_metadata",
    # Runner
    "build_tile_list",
    "find_dem_for_tile",
    "apply_tile_overrides",
    "process_tile",
    "run_batch",
    "copy_overlays",
    # Tiles
    "list_tiles_for_countries",
    "list_tiles_for_continent",
    "list_tiles_for_geometry",
    # Ortho4XP Init
    "init_ortho4xp",
    "batch_config_to_dict",
    "write_ortho4xp_cfg",
    "create_ortho4xp_callbacks",
]
