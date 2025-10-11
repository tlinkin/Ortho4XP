import os
import shutil
import sys
from pathlib import Path

# ===== Ortho4XP setup =====
Ortho4XP_dir = Path(__file__).resolve().parent.parent
sys.path.append(os.path.join(Ortho4XP_dir, 'src'))
sys.path.append(os.path.join(Ortho4XP_dir, 'Scripts'))

import O4_File_Names as FNAMES

sys.path.append(FNAMES.Provider_dir)
import O4_Imagery_Utils as IMG
import O4_Vector_Map as VMAP
import O4_Mesh_Utils as MESH
import O4_Mask_Utils as MASK
import O4_Tile_Utils as TILE
import O4_Overlay_Utils as OVL
import O4_Config_Utils as CFG
import Generate_Tiles as GEN

# ===== Ensure required directories =====
if not os.path.isdir(FNAMES.Utils_dir):
  sys.exit("Missing utils directory, check your install.")

for directory in (
    FNAMES.Preview_dir, FNAMES.Provider_dir, FNAMES.Extent_dir, FNAMES.Filter_dir,
    FNAMES.OSM_dir, FNAMES.Mask_dir, FNAMES.Imagery_dir, FNAMES.Elevation_dir,
    FNAMES.Geotiff_dir, FNAMES.Patch_dir, FNAMES.Tile_dir, FNAMES.Tmp_dir
):
  if not os.path.isdir(directory):
    os.makedirs(directory, exist_ok=True)

# ===== Initialize Ortho4XP providers =====
IMG.initialize_extents_dict()
IMG.initialize_color_filters_dict()
IMG.initialize_providers_dict()
IMG.initialize_combined_providers_dict()

# ===== Configuration =====
output_dir = Path.home() / "Downloads" / "Ortho Tiles"
dem_dir = Path.home() / "Downloads" / "Sonny LiDAR"

default_zl = 17
default_website = "BI"

# tiles = GEN.list_tiles_for_countries([
#   "BGR",
#   "ROU",
#   "MDA",
#   "GRC",
#   "MKD",
#   "ALB",
#   "MNE",
#   "SRB",
# ])

tiles = [(42,24)]

# ===== Main =====
if __name__ == "__main__":
  dem_entries = os.listdir(dem_dir)

  for cords in tiles:
    lat, lon = cords

    tile = CFG.Tile(lat, lon, f"{output_dir}\\")
    tile.make_dirs()
    tile.read_from_config(use_global=True)

    tile.default_zl = default_zl
    tile.default_website = default_website

    target_dem = f"{FNAMES.hem_latlon(lat, lon)}.hgt"
    for name in dem_entries:
      if name.lower() == target_dem.lower():
        full_path = os.path.join(dem_dir, name)
        if os.path.isfile(full_path):
          tile.custom_dem = full_path
          tile.write_to_config()

    VMAP.build_poly_file(tile)
    MESH.build_mesh(tile)
    MASK.build_masks(tile)
    TILE.build_tile(tile)
    OVL.build_overlay(lat, lon)


source_overlay_dir = Ortho4XP_dir / "yOrtho4XP_Overlays"
target_overlay_dir = output_dir / "yOrtho4XP_Overlays"
if target_overlay_dir.exists():
    shutil.rmtree(target_overlay_dir)

shutil.copy(source_overlay_dir, target_overlay_dir)
