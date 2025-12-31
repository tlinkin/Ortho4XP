# Batch_Processor.py Dependencies

Complete dependency map for running `Scripts/Batch_Processor.py`.

## Module Dependency Graph

```mermaid
flowchart TB
    subgraph Entry["Entry Point"]
        BP[Batch_Processor.py]
    end

    subgraph Scripts["Scripts/"]
        GT[Generate_Tiles.py]
    end

    subgraph Core["src/ - Core Modules"]
        FNAMES[O4_File_Names]
        CFG[O4_Config_Utils]
        IMG[O4_Imagery_Utils]
        VMAP[O4_Vector_Map]
        MESH[O4_Mesh_Utils]
        MASK[O4_Mask_Utils]
        TILE[O4_Tile_Utils]
        OVL[O4_Overlay_Utils]
    end

    subgraph Support["src/ - Supporting Modules"]
        DEM[O4_DEM_Utils]
        DSF[O4_DSF_Utils]
        GEO[O4_Geo_Utils]
        OSM[O4_OSM_Utils]
        VEC[O4_Vector_Utils]
        PAR[O4_Parallel_Utils]
        APT[O4_Airport_Utils]
    end

    BP --> GT
    BP --> FNAMES
    BP --> CFG
    BP --> IMG
    BP --> VMAP
    BP --> MESH
    BP --> MASK
    BP --> TILE
    BP --> OVL

    IMG --> DEM
    IMG --> PAR
    VMAP --> OSM
    VMAP --> VEC
    VMAP --> APT
    MESH --> DEM
    MESH --> GEO
    TILE --> DSF
    TILE --> IMG
    OVL --> DSF
```

## Python Package Dependencies

```mermaid
flowchart LR
    subgraph PyPI["Python Packages (pip)"]
        numpy[numpy]
        pillow[Pillow]
        pyproj[pyproj]
        requests[requests]
        rtree[Rtree]
        shapely[shapely]
        skfmm[scikit-fmm]
        gdal[GDAL]
    end

    subgraph Modules["O4_* Modules"]
        IMG[O4_Imagery_Utils]
        MESH[O4_Mesh_Utils]
        MASK[O4_Mask_Utils]
        VMAP[O4_Vector_Map]
        DEM[O4_DEM_Utils]
        DSF[O4_DSF_Utils]
        GEO[O4_Geo_Utils]
    end

    numpy --> IMG & MESH & MASK & VMAP & DEM & DSF
    pillow --> IMG & MASK & DSF
    pyproj --> GEO
    requests --> IMG & DEM
    rtree --> VMAP
    shapely --> VMAP
    skfmm --> MASK
    gdal --> DEM
```

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| numpy | 1.26.4 | All modules | Array operations, mesh data |
| Pillow | 12.0.0 | IMG, MASK, DSF | Image processing, DDS conversion |
| pyproj | 3.7.2 | GEO | Coordinate transformations |
| requests | 2.32.5 | IMG, DEM, OSM | HTTP downloads |
| Rtree | 1.4.1 | VMAP, VEC | Spatial indexing |
| shapely | 2.1.2 | VMAP, VEC, APT | Vector geometry operations |
| scikit-fmm | 2025.6.23 | MASK | Fast marching for water masks |
| GDAL | 3.9.0-3.11.4* | DEM, IMG | Geospatial raster operations |

*GDAL version is platform-dependent (see below)

## External Tools & Binaries

```mermaid
flowchart TB
    subgraph Pipeline["Tile Build Pipeline"]
        direction LR
        V[Vector Map] --> M[Mesh] --> K[Masks] --> T[Tile/DSF]
    end

    subgraph Tools["External Binaries"]
        TRI[Triangle4XP]
        MOU[moulinette]
        DSF[DSFTool]
        DDS[DDSTool / nvcompress]
        Z7[7z / 7zz]
        GDAL_T[gdal_translate]
        GDAL_W[gdalwarp]
    end

    M --> TRI
    M --> MOU
    T --> DDS
    T --> DSF
    T --> GDAL_T
    T --> GDAL_W
    T --> Z7
```

| Tool | Location | Platform | Purpose |
|------|----------|----------|---------|
| Triangle4XP | `Utils/{platform}/` | All | Constrained Delaunay mesh generation |
| moulinette | `Utils/{platform}/` | All | Mesh triangle sorting for DSF |
| DSFTool | `Utils/{platform}/` | All | DSF text/binary conversion |
| DDSTool | `Utils/mac/` | macOS | PNG → DDS texture compression |
| nvcompress | `Utils/{win,lin}/` | Win/Linux | PNG → DDS texture compression |
| 7z / 7zz | `Utils/{platform}/` or system | All | Archive extraction |
| gdal_translate | System PATH | All | GeoTIFF georeferencing |
| gdalwarp | System PATH | All | Image reprojection |

## System Dependencies

### macOS (Homebrew)

```bash
brew install python python-tk spatialindex p7zip proj gdal
```

| Package | Purpose |
|---------|---------|
| python | Python 3.x interpreter |
| python-tk | Tkinter GUI framework |
| spatialindex | Required by Rtree |
| p7zip | 7-zip archive support |
| proj | PROJ coordinate library |
| gdal | GDAL/OGR geospatial library |

### Windows

All dependencies bundled in `Utils/win/`:
- Pre-built wheel files (`.whl`) for pip packages
- Compiled binaries (`.exe`, `.dll`)

### Linux

```bash
# Debian/Ubuntu
apt install python3 python3-tk libspatialindex-dev p7zip-full libproj-dev libgdal-dev

# pip packages
pip install numpy pillow pyproj requests Rtree shapely scikit-fmm gdal
```

## Platform Compatibility Matrix

| Component | macOS | Windows | Linux |
|-----------|-------|---------|-------|
| **Python** | 3.11+ | 3.11+ | 3.11+ |
| **GDAL version** | 3.11.4 | 3.11.1 | 3.9.0 |
| **DDS converter** | DDSTool | nvcompress | nvcompress |
| **7-zip binary** | 7zz | 7z.exe | 7z |
| **Install method** | Homebrew + pip | Bundled wheels | apt + pip |
| **Triangle4XP** | `Utils/mac/` | `Utils/win/` | `Utils/lin/` |

## Build Dependencies (Optional)

Only needed to recompile `Utils/src/` binaries:

```bash
# Build Triangle4XP and moulinette from source
cd Utils
cmake .
make
```

| Tool | Purpose |
|------|---------|
| CMake | Build system generator |
| C compiler (gcc/clang) | Compile Triangle4XP.c |

## Quick Start

```bash
# 1. Install system dependencies (macOS example)
brew install python python-tk spatialindex p7zip proj gdal

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Run batch processor
python Scripts/Batch_Processor.py --config batch_config.toml
```
