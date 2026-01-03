# Ortho4XP CLI Reference

Command-line interface for batch tile processing and automation.

## Quick Start

```bash
# Build a single tile (all steps)
python Ortho4XP.py 47 8

# Build with XP12 config
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8

# Build specific step only
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8 --mesh

# Batch processing with 4 parallel workers
python Ortho4XP.py --config Ortho4XP_XP12.cfg --batch tiles.txt --workers 4
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

| Option | Description |
|--------|-------------|
| `--config, -c FILE` | Use specific config file |
| `--global-config` | Use global config only (ignore tile configs) |
| `--provider, -p CODE` | Override imagery provider (BI, GO2, etc.) |
| `--zl INT` | Override zoom level |
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

## Configuration Files

Use `Ortho4XP_XP12.cfg` for X-Plane 12 with optimized settings:

```bash
# Single tile
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8

# Batch
python Ortho4XP.py --config Ortho4XP_XP12.cfg --batch tiles.txt

# Specific step
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8 --mesh
```

Key settings in `Ortho4XP_XP12.cfg`:
- `water_tech=XP12` - Native XP12 water rendering
- `default_zl=17` - Base zoom level (0.6m/pixel)
- `cover_zl=19` - Airport coverage zoom level
- `curvature_tol=1.0` - Mesh detail level

## Batch Processing

### Tile List Format

Create a text file with one tile per line:

```
# tiles.txt - Comments start with #
47,8
47,9
48,8
48,9
```

### Parallel Processing

```bash
# Process 4 tiles simultaneously
python Ortho4XP.py --batch tiles.txt --workers 4

# With config and specific steps
python Ortho4XP.py --config Ortho4XP_XP12.cfg --batch tiles.txt --workers 4 --steps mesh,dsf
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

The iterate feature allows progressive mesh refinement with multiple DEM sources:

```ini
# In config file:
cleaning_level=0    # REQUIRED - preserves mesh files between iterations
iterate=0           # Start with base DEM
custom_dem=/path/base.hgt;/path/lidar.hgt
#          iterate=0         iterate=1
```

**Workflow:**

```bash
# Step 1: Build initial mesh with base DEM (iterate=0)
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8 --mesh

# Step 2: Edit config, set iterate=1, rebuild mesh with LiDAR refinement
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8 --mesh

# Step 3: Build masks and final DSF
python Ortho4XP.py --config Ortho4XP_XP12.cfg 47 8 --steps mask,dsf
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
