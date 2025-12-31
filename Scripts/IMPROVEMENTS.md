# Scripts/ Improvement Plan (TDD)

## Overview
Refactor and enhance the Scripts/ directory with TOML configuration, state persistence, and code optimization.

## Design Decisions
- **Config scope**: All Ortho4XP variables (50+) mapped to TOML
- **Test framework**: pytest
- **State format**: TOML

## Current State Analysis

**Batch_Processor.py Issues:**
- Hardcoded Windows paths (`D:\Ortho Tiles`, `D:\Sonny LiDAR`)
- No state/memory tracking between runs
- No error recovery or progress checkpointing
- Tight coupling with configuration values

**Generate_Tiles.py:**
- Clean utility code, minimal changes needed
- Good caching with `@lru_cache`

---

## Improvement 1: TOML Configuration System

### Goal
Replace hardcoded config with a `batch_config.toml` that maps to Ortho4XP config variables.

### TOML Schema
```toml
[batch]
output_dir = "/path/to/output"
dem_dir = "/path/to/dem"
state_file = "batch_state.toml"  # memory file

[sources]
countries = ["USA", "CAN"]
tiles = [[45, -122], [46, -123]]

# Application variables (cfg_app_vars)
[app]
verbosity = 1
cleaning_level = 1
overpass_server_choice = "random"
skip_downloads = false
skip_converts = false
max_download_slots = 1
max_convert_slots = 4
check_tms_response = true
http_timeout = 10.0
max_connect_retries = 5
max_baddata_retries = 5
ovl_exclude_pol = [0]
ovl_exclude_net = []
custom_scenery_dir = ""
custom_overlay_src = ""
custom_overlay_src_alternate = ""

# Tile variables (cfg_tile_vars) - all 50+ variables
[tile]
# Vector
apt_smoothing_pix = 8
road_level = 1
road_banking_limit = 0.5
lane_width = 4.0
max_levelled_segs = 200000
water_simplification = 0.0
min_area = 0.001
max_area = 200.0
clean_bad_geometries = true
mesh_zl = 19

# Mesh
curvature_tol = 2.0
apt_curv_tol = 0.5
apt_curv_ext = 0.5
coast_curv_tol = 1.0
coast_curv_ext = 0.5
limit_tris = 3.0
min_angle = 10.0
sea_smoothing_mode = "zero"
water_smoothing = 10
iterate = 0

# Masks
mask_zl = 14
masks_width = 100
masking_mode = "sand"
use_masks_for_inland = false
imprint_masks_to_dds = false
distance_masks_too = false
masks_use_DEM_too = false
masks_custom_extent = ""

# DSF/Imagery
default_website = "BI"
default_zl = 17
zone_list = []
cover_airports_with_highres = "False"
cover_extent = 1.0
cover_zl = 18
sea_texture_blur = 0.0
water_tech = "XP11 + bathy"
ratio_water = 0.25
ratio_bathy = 1.0
normal_map_strength = 1.0
terrain_casts_shadows = true
overlay_lod = 25000.0
use_decal_on_terrain = false

# Other
custom_dem = ""
fill_nodata = true

# Per-tile overrides (optional)
[tile_overrides."+45-122"]
custom_dem = "/path/to/lidar.tif"
iterate = 3
```

### Tests (test_batch_config.py)
1. `test_load_valid_toml` - Parse valid TOML, verify all fields accessible
2. `test_missing_required_fields` - Raise error for missing `output_dir`
3. `test_defaults_applied` - Verify defaults fill in missing values
4. `test_tile_overrides_merge` - Per-tile config merges with defaults
5. `test_invalid_toml_syntax` - Graceful error on malformed TOML
6. `test_path_expansion` - `~` and env vars expanded correctly

---

## Improvement 2: State/Memory System

### Goal
Track processed tiles to avoid reprocessing on subsequent runs.

### State File Format (`batch_state.toml`)
```toml
[metadata]
last_run = "2025-12-31T10:00:00"
config_hash = "abc123"  # detect config changes

[tiles]
[tiles."+45-122"]
status = "completed"
completed_at = "2025-12-31T10:30:00"
steps_completed = ["vector", "mesh", "masks", "tile"]

[tiles."+46-123"]
status = "failed"
failed_at = "2025-12-31T11:00:00"
error = "HTTP timeout on imagery download"
last_step = "tile"
```

### Tests (test_batch_state.py)
1. `test_create_new_state_file` - Creates state file if missing
2. `test_load_existing_state` - Loads previous state correctly
3. `test_mark_tile_completed` - Updates tile status to completed
4. `test_mark_tile_failed` - Records failure with error message
5. `test_skip_completed_tiles` - Filter out already-completed tiles
6. `test_reprocess_on_config_change` - Config hash change triggers reprocess
7. `test_resume_failed_tile` - `--retry-failed` flag reprocesses failed tiles

---

## Improvement 3: Refactored Architecture

### New File Structure
```
Scripts/
├── batch_config.toml      # User configuration
├── batch_state.toml       # Auto-generated state tracking
├── example.cfg            # Legacy example (keep for reference)
├── Batch_Processor.py     # Main entry point (simplified)
├── Generate_Tiles.py      # Tile enumeration (minimal changes)
├── batch/                  # New package
│   ├── __init__.py
│   ├── config.py          # TOML config loading
│   ├── state.py           # State persistence
│   └── runner.py          # Tile processing logic
└── tests/
    ├── __init__.py
    ├── test_batch_config.py
    ├── test_batch_state.py
    └── test_runner.py
```

### Tests (test_runner.py)
1. `test_build_tile_list_from_countries` - Countries resolve to tile coords
2. `test_build_tile_list_from_coords` - Direct coords work
3. `test_combined_sources` - Countries + coords deduplicated
4. `test_apply_tile_overrides` - Per-tile config applied correctly
5. `test_dem_auto_detection` - DEM files matched to tiles by coords
6. `test_process_tile_success` - Full pipeline runs on mock
7. `test_process_tile_failure_recovery` - State updated on failure

---

## Implementation Steps

### Phase 1: Config System
1. Create `batch/config.py` with TOML parsing
2. Write tests in `tests/test_batch_config.py`
3. Define schema validation

### Phase 2: State System
1. Create `batch/state.py` with persistence logic
2. Write tests in `tests/test_batch_state.py`
3. Implement config hash comparison

### Phase 3: Runner Refactor
1. Extract processing logic to `batch/runner.py`
2. Write tests in `tests/test_runner.py`
3. Simplify `Batch_Processor.py` to thin CLI wrapper

### Phase 4: Integration
1. Update `Batch_Processor.py` to use new modules
2. Add CLI argument parsing (`--config`, `--retry-failed`, `--dry-run`)
3. Integration tests

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `Scripts/Batch_Processor.py` | Refactor to use new modules, add CLI args |
| `Scripts/Generate_Tiles.py` | Minor cleanup, type hints |
| `Scripts/batch/config.py` | New: TOML config loading |
| `Scripts/batch/state.py` | New: State persistence |
| `Scripts/batch/runner.py` | New: Tile processing logic |

---

## CLI Interface (Final)

```bash
# Basic usage
python Batch_Processor.py --config batch_config.toml

# Retry failed tiles
python Batch_Processor.py --config batch_config.toml --retry-failed

# Dry run (show what would be processed)
python Batch_Processor.py --config batch_config.toml --dry-run

# Force reprocess all
python Batch_Processor.py --config batch_config.toml --force
```
