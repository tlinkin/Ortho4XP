# Ortho4XP CLI Reference

Command-line interface for batch tile processing and automation.

## Quick Start

```bash
# Build a single tile (all steps)
python Ortho4XP.py 47 8

# Build specific step only
python Ortho4XP.py 47 8 --mesh

# Batch processing with 4 parallel workers
python Ortho4XP.py --batch tiles.txt --workers 4
```

## Command Reference

### Tile Specification

| Option | Description |
|--------|-------------|
| `lat lon` | Latitude and longitude for single tile |
| `--batch, -b FILE` | File containing tile list (lat,lon per line) |

### Build Steps

| Option | Description |
|--------|-------------|
| `--steps STEPS` | Comma-separated: osm,mesh,mask,dsf,overlay |
| `--osm` | Run OSM/vector step only |
| `--mesh` | Run mesh step only |
| `--mask` | Run mask step only |
| `--dsf` | Run DSF/imagery step only |
| `--overlay` | Run overlay step only |

### Configuration

The CLI uses `Ortho4XP.cfg` in the project root directory for settings.

| Option | Description |
|--------|-------------|
| `--provider, -p CODE` | Override imagery provider (BI, GO2, etc.) |
| `--zl INT` | Override zoom level |
| `--iterate INT` | Override mesh iterate value (for LIDAR refinement) |
| `--build-dir DIR` | Custom build directory |

### Parallelization

| Option | Description |
|--------|-------------|
| `--workers, -w N` | Number of parallel tile workers (default: 1) |

### Output Control

| Option | Description |
|--------|-------------|
| `--verbose, -v` | Increase verbosity (can be repeated) |
| `--quiet, -q` | Suppress output except errors |
| `--no-progress` | Disable progress bar |
| `--fail-fast` | Stop on first tile error |

### Utility Commands

| Option | Description |
|--------|-------------|
| `--organize-dem DIR` | Organize .hgt files from DIR into Elevation_data |

## Example Configuration

The CLI reads settings from `Ortho4XP.cfg` in the project root. Below is a complete example optimized for X-Plane 12.

### Settings by Step

| Step | Key Settings |
|------|--------------|
| `--osm` | `road_level`, `clean_bad_geometries`, `water_simplification` |
| `--mesh` | `curvature_tol`, `limit_tris`, `mesh_zl`, `iterate`, `custom_dem`, `cleaning_level` |
| `--mask` | `water_tech`, `masking_mode`, `masks_width`, `mask_zl`, `ratio_water` |
| `--dsf` | `default_zl`, `default_website`, `cover_zl`, `max_download_slots` |
| `--overlay` | `custom_overlay_src`, `overlay_lod`, `ovl_exclude_pol` |

### Example: Ortho4XP.cfg for X-Plane 12

```ini
# =============================================================================
# X-PLANE 12 WATER (used by: --mask, --dsf)
# =============================================================================
water_tech=XP12
imprint_masks_to_dds=False

# =============================================================================
# MESH QUALITY (used by: --mesh)
# =============================================================================
curvature_tol=1.0
apt_curv_tol=0.3
apt_curv_ext=0.5
coast_curv_tol=0.5
coast_curv_ext=0.5
limit_tris=4.0
mesh_zl=19
min_angle=10.0
sea_smoothing_mode=zero
water_smoothing=10

# =============================================================================
# IMAGERY (used by: --dsf)
# =============================================================================
default_zl=17
default_website=BI
cover_airports_with_highres=ICAO
cover_zl=19
cover_extent=1.0
sea_texture_blur=0.0

# =============================================================================
# WATER MASKING (used by: --mask)
# =============================================================================
masking_mode=3steps
masks_width=100
mask_zl=16
ratio_water=0.25
ratio_bathy=1.0
distance_masks_too=True
masks_use_DEM_too=False
use_masks_for_inland=False

# =============================================================================
# DSF & RENDERING (used by: --dsf)
# =============================================================================
terrain_casts_shadows=True
normal_map_strength=1.0
use_decal_on_terrain=True
overlay_lod=25000

# =============================================================================
# ROADS & VECTOR DATA (used by: --osm, --overlay)
# =============================================================================
road_level=1
road_banking_limit=0.5
lane_width=4.0
apt_smoothing_pix=8
clean_bad_geometries=True
water_simplification=0.0
min_area=0.001
max_area=200.0
max_levelled_segs=200000

# =============================================================================
# NETWORK & DOWNLOADS (used by: --dsf)
# =============================================================================
# Good balance for 24-core processor with --workers 4
max_download_slots=24
max_convert_slots=6
http_timeout=60.0
max_connect_retries=30
max_baddata_retries=30
check_tms_response=True
overpass_server_choice=KU

# =============================================================================
# PERFORMANCE
# =============================================================================
verbosity=0
skip_downloads=False
skip_converts=False
cleaning_level=0

# =============================================================================
# CUSTOM DEM / LIDAR (used by: --mesh --iterate)
# =============================================================================
# IMPORTANT: cleaning_level=0 is REQUIRED for iterate to preserve mesh files
fill_nodata=False
iterate=0
#custom_dem=/path/base.hgt;/path/lidar.hgt

# =============================================================================
# X-PLANE 12 OVERLAYS (used by: --overlay)
# =============================================================================
custom_overlay_src=C:/X-Plane 12/Global Scenery/X-Plane 12 Global Scenery
custom_scenery_dir=C:/X-Plane 12/Custom Scenery
ovl_exclude_pol=[0]
ovl_exclude_net=[]
```

## Batch Processing

### Tile List Format

Create a text file with tiles specified as:

```
# tiles.txt - Comments start with #

# Coordinate format (lat,lon)
47,8
47,9

# ISO3 country codes (3 letters)
CHE
AUT
ITA
```

ISO3 codes are expanded to all intersecting 1x1 tiles automatically.

### Parallel Processing

```bash
# Process 4 tiles simultaneously
python Ortho4XP.py --batch tiles.txt --workers 4

# With specific steps
python Ortho4XP.py --batch tiles.txt --workers 4 --steps mesh,dsf
```

## Build Steps

| Step | Description |
|------|-------------|
| **osm** | Download and process OpenStreetMap vector data |
| **mesh** | Generate terrain mesh from elevation data |
| **mask** | Create water masks for coastlines and water bodies |
| **dsf** | Download imagery and build final DSF scenery file |
| **overlay** | Extract and build overlay scenery (roads, etc.) |

Default: All steps except overlay.

## Custom DEM / Iterate Workflow

For high-resolution terrain using custom DEM or LiDAR data:

### Setup

1. Place .hgt files in `Elevation_data/<10-degree-block>/`:
   ```
   Elevation_data/+40+000/N47E008.hgt
   ```

2. Or use `--organize-dem` to auto-organize flat directories:
   ```bash
   python Ortho4XP.py --organize-dem /path/to/dem/files
   ```

### Iterate Refinement

The iterate feature allows progressive mesh refinement with multiple DEM sources.

Set in `Ortho4XP.cfg`:
```ini
cleaning_level=0    # REQUIRED - preserves mesh files between iterations
custom_dem=/path/base.hgt;/path/lidar.hgt
#          iterate=0         iterate=1
```

**Workflow using --iterate flag:**

```bash
# Step 1: Build initial mesh with base DEM
python Ortho4XP.py 47 8 --mesh --iterate 0

# Step 2: Rebuild mesh with LiDAR refinement
python Ortho4XP.py 47 8 --mesh --iterate 1

# Step 3: Build masks and final DSF
python Ortho4XP.py 47 8 --steps mask,dsf
```

## Organize DEM Files

Copy .hgt files from a flat directory into the proper folder structure:

```bash
python Ortho4XP.py --organize-dem /path/to/dem/files
```

**Before:**
```
/path/to/dem/files/
  N47E006.hgt
  N50E010.hgt
```

**After:**
```
Elevation_data/
  +40+000/
    N47E006.hgt
  +50+010/
    N50E010.hgt
```

## Batch Iterate Workflow

For batch processing with LIDAR DEMs, use the `--iterate` flag to control mesh refinement.

**Required config settings:**
```ini
cleaning_level=0              # REQUIRED - preserves mesh files between iterations
custom_dem=/path/base.hgt;/path/lidar.hgt  # semicolon-separated DEM sources
```

**Batch commands:**

```bash
# Pre-step (optional): Organize DEM files into Elevation_data structure
# Note: Trailing backslash is required to mark path as folder
python Ortho4XP.py --organize-dem "D:\Sonny LiDAR\"

# Step 1: OSM data (uses: road_level, clean_bad_geometries)
python Ortho4XP.py --batch tiles.txt --workers 24 --osm --build-dir "D:\Ortho Tiles\"

# Step 2: Mesh iterations (uses: curvature_tol, limit_tris, custom_dem)
python Ortho4XP.py --batch tiles.txt --workers 24 --mesh --iterate 0 --build-dir "D:\Ortho Tiles\"
python Ortho4XP.py --batch tiles.txt --workers 24 --mesh --iterate 1 --build-dir "D:\Ortho Tiles\"
python Ortho4XP.py --batch tiles.txt --workers 24 --mesh --iterate 2 --build-dir "D:\Ortho Tiles\"

# Step 3: Masks (uses: water_tech, masking_mode, masks_width, mask_zl)
python Ortho4XP.py --batch tiles.txt --workers 24 --provider BI --zl 17 --mask --build-dir "D:\Ortho Tiles\"

# Step 4: DSF (uses: default_zl, default_website, max_download_slots)
# Fewer workers recommended - I/O bound
python Ortho4XP.py --batch tiles.txt --workers 4 --provider BI --zl 17 --dsf --build-dir "D:\Ortho Tiles\"

# Step 5: Overlay (uses: custom_overlay_src, overlay_lod) - optional
python Ortho4XP.py --batch tiles.txt --workers 24 --overlay --build-dir "D:\Ortho Tiles\"
```

**Notes:**
- `--osm` doesn't need `--provider`/`--zl`
- `--overlay` doesn't need `--provider`/`--zl`
- Reduce workers for `--dsf` as it's I/O bound
