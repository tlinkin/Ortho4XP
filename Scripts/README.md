# Ortho4XP Batch Processor

A command-line tool for batch processing Ortho4XP tiles with TOML configuration and state persistence.

## Features

- **TOML Configuration**: All settings in a single config file
- **State Persistence**: Resume interrupted runs, skip completed tiles
- **Country-based Tiles**: Specify countries by ISO3 code or name
- **Per-tile Overrides**: Custom settings for specific tiles
- **Dry Run Mode**: Preview what would be processed

## Installation

```bash
cd Scripts
uv sync  # or: pip install -e .
```

## Quick Start

1. **Copy the example config:**
   ```bash
   cp batch_config.example.toml batch_config.toml
   ```

2. **Edit the config** to set your paths and tile sources:
   ```toml
   [batch]
   output_dir = "D:/Ortho Tiles"
   dem_dir = "D:/DEMs"

   [sources]
   countries = ["USA"]
   # or specify tiles directly:
   tiles = [[45, -122], [46, -123]]
   ```

3. **Run the batch processor:**
   ```bash
   python Batch_Processor.py --config batch_config.toml
   ```

## CLI Options

```
Usage: Batch_Processor.py [OPTIONS]

Options:
  -c, --config PATH      Path to TOML configuration file [required]
  --retry-failed         Retry previously failed tiles
  --dry-run              Show what would be processed
  --force                Force reprocessing of all tiles
  -v, --verbose          Enable verbose output
  --help                 Show this message and exit
```

### Examples

```bash
# Basic run
python Batch_Processor.py -c batch_config.toml

# Preview without processing
python Batch_Processor.py -c batch_config.toml --dry-run

# Retry failed tiles only
python Batch_Processor.py -c batch_config.toml --retry-failed

# Reprocess everything (ignore state)
python Batch_Processor.py -c batch_config.toml --force

# Verbose output
python Batch_Processor.py -c batch_config.toml -v
```

## Configuration Reference

### [batch] Section (Required)

```toml
[batch]
output_dir = "~/Ortho4XP/Tiles"    # Where generated tiles go
dem_dir = "~/Ortho4XP/DEMs"        # Where to find DEM files
state_file = "batch_state.toml"    # State tracking file (in output_dir)
```

**Path expansion**: Use `~` for home directory or `$VAR`/`${VAR}` for environment variables.

**DEM auto-matching**: Place DEM files like `N45W122.hgt` in `dem_dir` and they'll be automatically matched to tiles by coordinate.

### [sources] Section (Required)

Specify tiles to process. You can use countries, direct coordinates, or both.

```toml
[sources]
# By country (ISO3 codes or names)
countries = [
    "USA",
    "CAN",
    "Germany",
]

# By coordinates [lat, lon]
tiles = [
    [45, -122],  # Portland, OR
    [46, -123],
]
```

### [app] Section (Optional)

Application-wide settings:

```toml
[app]
verbosity = 1                    # 0=quiet, 1=normal, 2=verbose, 3=debug
cleaning_level = 0               # 0=keep all, 1=normal, 2=clean more, 3=clean all
overpass_server_choice = "ku"    # OSM server: "random", "de", "fr", "ku", etc.
skip_downloads = false           # Skip imagery download (DSF only)
skip_converts = false            # Skip DDS conversion
max_download_slots = 96          # Parallel orthophoto downloads
max_convert_slots = 16           # Parallel DDS conversions
check_tms_response = true        # Retry on HTTP errors
http_timeout = 60.0              # HTTP timeout (seconds)
max_connect_retries = 30         # Connection retry attempts
max_baddata_retries = 30         # Server error retry attempts
ovl_exclude_pol = [0]            # Exclude polygon types from overlay
ovl_exclude_net = []             # Exclude network types from overlay
custom_scenery_dir = ""          # X-Plane Custom Scenery path
custom_overlay_src = ""          # Overlay source directory
```

### [tile] Section (Optional)

Default settings for all tiles:

```toml
[tile]
# Imagery
default_website = "BI"           # Imagery provider code
default_zl = 17                  # Zoom level (10-20)

# Vector Processing
road_level = 1                   # Road inclusion (0=none, 1-5=more)
water_simplification = 0.0       # Water node simplification (meters)
min_area = 0.001                 # Min water patch size (km²)
max_area = 200.0                 # Max water patch size (km²)

# Mesh Generation
mesh_zl = 19                     # Mesh zoom level (16-20)
curvature_tol = 2.0              # Global curvature tolerance
limit_tris = 3.0                 # Triangle limit (millions)

# Masks
mask_zl = 16                     # Mask zoom level (14-16)
masks_width = 100                # Mask extent from coastline (meters)
masking_mode = "sand"            # Mask type: "sand", "rocks", "3steps"
imprint_masks_to_dds = true      # Embed masks in DDS textures
masks_use_DEM_too = true         # Use DEM for mask precision

# DSF/Rendering
cover_airports_with_highres = "ICAO"  # High-res airports: "False", "True", "ICAO"
cover_zl = 19                    # Airport coverage zoom level
water_tech = "XP12"              # Water tech: "XP12", "XP11 + bathy"

# Elevation
custom_dem = ""                  # Custom DEM file path
fill_nodata = true               # Fill missing elevation data
```

### [tile_overrides] Section (Optional)

Override settings for specific tiles using tile ID format `+LAT+LON` or `+LAT-LON`:

```toml
# Custom LiDAR DEM for Portland area
[tile_overrides."+45-122"]
custom_dem = "/path/to/lidar/N45W122.tif"
iterate = 3

# Higher zoom level for Seattle
[tile_overrides."+47-122"]
default_zl = 18
cover_airports_with_highres = "ICAO"
```

## State Management

The batch processor tracks progress in a state file (`batch_state.toml` by default) stored in your output directory.

### How it works:

- **Completed tiles** are skipped on subsequent runs
- **Failed tiles** are skipped unless `--retry-failed` is used
- **Config changes** (detected via hash) trigger reprocessing
- **Force mode** (`--force`) ignores all state and reprocesses everything

### State file format:

```toml
[metadata]
last_run = "2025-12-31T10:00:00"
config_hash = "abc123def456"

[tiles."+45-122"]
status = "completed"
started_at = "2025-12-31T10:15:00"
completed_at = "2025-12-31T10:30:00"
steps_completed = ["vector", "mesh", "masks", "tile"]

[tiles."+46-123"]
status = "failed"
failed_at = "2025-12-31T11:00:00"
error = "HTTP timeout on imagery download"
last_step = "tile"
```

## Processing Pipeline

Each tile goes through four steps:

1. **Vector** (`build_poly_file`) - Fetch OSM data, create polygon files
2. **Mesh** (`build_mesh`) - Generate terrain mesh using elevation data
3. **Masks** (`build_masks`) - Create water transparency masks
4. **Tile** (`build_tile`) - Download imagery, convert to DDS, build DSF

## Troubleshooting

### "Config file not found"
Ensure the path to your config file is correct. Use absolute paths if needed.

### "Missing utils directory"
Run from the Ortho4XP root directory or ensure the `Utils/` directory exists.

### Tiles stuck in "failed" state
Use `--retry-failed` to reprocess failed tiles, or `--force` to start fresh.

### State file corrupted
Delete `batch_state.toml` from your output directory and run again.

## Running Tests

```bash
cd Scripts
uv run pytest -v
```
