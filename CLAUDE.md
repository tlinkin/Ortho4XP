# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ortho4XP is a Python-based scenery generation tool for X-Plane flight simulator. It creates terrain mesh and texture layers using external elevation data and orthophoto sources. The application runs as a Tkinter GUI or via command line.

## Running the Application

**Setup (Mac):**
```bash
./install_mac.sh   # Requires Homebrew; creates venv and installs deps
./start_mac.sh     # Activates venv and runs Ortho4XP.py
```

**Setup (Windows):**
```batch
install_windows.bat   # Creates venv and installs deps (uses bundled wheel files)
start_windows.bat     # Activates venv and runs Ortho4XP.py
```

**Command line usage:**
```bash
python Ortho4XP.py                      # Launch GUI
python Ortho4XP.py lat lon              # Build tile using existing config
python Ortho4XP.py lat lon provider zl  # Build tile with specified provider/zoom
```

## Building Native Components

The project includes a C-based mesh triangulation tool (Triangle4XP) in `Utils/src/`:
```bash
cd Utils
cmake .
make
```
Pre-compiled binaries for each platform are in `Utils/mac/`, `Utils/win/`, `Utils/lin/`.

## Architecture

### Entry Point
`Ortho4XP.py` - Initializes directories, loads imagery providers, and either launches the GUI (`O4_GUI_Utils.Ortho4XP_GUI`) or runs command-line tile building.

### Core Modules (in `src/`)

The tile building pipeline follows this sequence:

1. **O4_Vector_Map.py** - `build_poly_file()`: Fetches OSM data and creates polygon/constraint files
2. **O4_Mesh_Utils.py** - `build_mesh()`: Generates terrain mesh using elevation data and Triangle4XP
3. **O4_Mask_Utils.py** - `build_masks()`: Creates water transparency masks
4. **O4_Tile_Utils.py** - `build_tile()`: Downloads imagery, converts to DDS, builds final DSF

Supporting modules:
- **O4_Cfg_Vars.py** - Configuration variable definitions with types, defaults, and hints
- **O4_Config_Utils.py** - Configuration loading/saving, global config file handling
- **O4_File_Names.py** - Path generation for all data files (elevation, imagery, masks, etc.)
- **O4_Imagery_Utils.py** - Provider management, tile downloading, image processing
- **O4_DSF_Utils.py** - X-Plane DSF file generation
- **O4_DEM_Utils.py** - Elevation data handling (Viewfinderpanoramas, SRTM, ALOS, custom DEMs)
- **O4_GUI_Utils.py** - Tkinter GUI (Ortho4XP_GUI class)
- **O4_Overlay_Utils.py** - Extracts overlay scenery from existing X-Plane installations
- **O4_Parallel_Utils.py** - Thread pool utilities for parallel downloads/conversions

### Data Directories

Created at runtime if missing:
- `Providers/` - Imagery provider definitions (.lay files, Python custom providers)
- `Elevation_data/` - Downloaded DEM files
- `Orthophotos/` - Downloaded imagery tiles
- `Masks/` - Generated water masks
- `Tiles/` - Output scenery packages (zOrtho4XP_*)
- `OSM_data/` - Cached OpenStreetMap vector data

### Configuration System

- `Ortho4XP.cfg` - Global configuration (app settings + default tile settings)
- `Ortho4XP_*.cfg` - Per-tile configuration files (in tile directories)
- Variables are defined in `O4_Cfg_Vars.py` with `cfg_app_vars` (application-wide) and `cfg_tile_vars` (per-tile)
- Module variable binding uses exec() to set values on appropriate module namespaces

### Provider System

Imagery providers are defined in `Providers/` subdirectories:
- `.lay` files - JSON-like provider definitions with URL templates
- `O4_Custom_URL.py` - Python hook for custom URL generation
- `.comb` files - Combined provider definitions (multiple sources)

## Key Dependencies

- numpy, Pillow - Image processing
- pyproj, GDAL - Geospatial operations
- shapely, Rtree - Vector geometry
- scikit-fmm - Fast marching for mask generation
- requests - HTTP downloads
