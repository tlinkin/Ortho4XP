from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

# ===== Ortho4XP setup =====
# Assumes:
#   <repo_root>/Scripts/Batch_Cleaner.py
#   <repo_root>/src/O4_File_Names.py
Ortho4XP_dir = Path(__file__).resolve().parent.parent
sys.path.append(os.path.join(Ortho4XP_dir, "src"))

import O4_File_Names as FNAMES
import Generate_Tiles as GEN

# -----------------------
# CONFIGURATION
# -----------------------
KEEP_PROVIDERS = {"BI"}  # e.g., {"BI", "GO2", "ARC"} – imagery providers to keep (case-insensitive)
ALLOWED_ZLS = {17, 19}  # e.g., {16,17,18}; empty set = keep any ZL
DRY_RUN = False  # Safety flag — prints only, doesn't delete

tiles = GEN.list_tiles_for_countries([
  "BGR",
  "ROU",
  "MDA",
  "GRC",
  "MKD",
  "ALB",
  "MNE",
  "SRB",
])

# IMPORTANT: your actual tiles root on disk. Override FNAMES.Tile_dir to point there.
# Example given by you:
FNAMES.Tile_dir = r"C:\Users\manna\Downloads\Ortho Tiles"

# -----------------------
# HELPERS
# -----------------------
_PROV_ZL_DIR_RE = re.compile(r"^([A-Za-z0-9]+)[_\-]?(\d{1,2})$")
# Default Ortho4XP texture filename: <til_y>_<til_x>_<PROV><ZL>.<ext>
_TEX_FILE_RE = re.compile(
  r"^\d+_\d+_([A-Za-z0-9]+)(\d{1,2})\.(?:dds|png|jpg|jpeg|tif|tiff)$",
  re.IGNORECASE,
)
# g2xpl_16 special filenames — different pattern; we skip ZL parsing for these
_G2XPL_TEX_FILE_RE = re.compile(r"^\d{1,2}_\d+_\d+\.(?:dds|png|jpg|jpeg)$", re.IGNORECASE)


def parse_provider_and_zl_from_dir(name: str) -> tuple[str | None, int | None]:
  """Parse provider and ZL from dir names like 'BI_17', 'GO2-18', or 'BI18'."""
  m = _PROV_ZL_DIR_RE.match(name)
  if not m:
    return None, None
  prov = m.group(1)
  zl = None
  try:
    zl = int(m.group(2))
  except ValueError:
    pass
  return prov, zl


def rm_path(path: str):
  if not os.path.exists(path):
    return
  if DRY_RUN:
    print(f"[DRY] DELETE: {path}")
    return
  if os.path.isdir(path) and not os.path.islink(path):
    shutil.rmtree(path)
  else:
    try:
      os.remove(path)
    except FileNotFoundError:
      pass


def keep_path(path: str):
  print(f"[KEEP] {path}")


def is_empty_dir(path: str) -> bool:
  if not os.path.isdir(path):
    return False
  try:
    next(os.scandir(path))
    return False
  except StopIteration:
    return True


def allowed_sets(tiles_list):
  """Return sets of bands and tile tokens based on FNAMES helpers."""
  bands = set()
  tokens = set()
  for la, lo in tiles_list:
    bands.add(FNAMES.round_latlon(la, lo))  # '+40+020'
    tokens.add(FNAMES.short_latlon(la, lo))  # '+42+024'
  return bands, tokens


# -----------------------
# CLEANERS
# -----------------------
def clean_banded_tree(root_dir: str, allowed_bands: set[str], allowed_tokens: set[str]):
  """
  Remove unwanted bands/tiles under FNAMES-structured folders (Masks, OSM_data, Elevation_data, Orthophotos bands).
  Expected layout: root/+lat10+lon10/+lat+lon/...
  """
  if not os.path.isdir(root_dir):
    return

  for band_name in os.listdir(root_dir):
    band_path = os.path.join(root_dir, band_name)
    if not os.path.isdir(band_path):
      continue

    if band_name not in allowed_bands:
      rm_path(band_path)
      continue

    for tile_name in os.listdir(band_path):
      tile_path = os.path.join(band_path, tile_name)
      if not os.path.isdir(tile_path):
        continue
      if tile_name not in allowed_tokens:
        rm_path(tile_path)
      else:
        keep_path(tile_path)

    if is_empty_dir(band_path):
      rm_path(band_path)


def clean_orthophotos_by_provider_and_zl(root_dir: str, keep_providers: set[str], allowed_zls: set[int]):
  """
  Cleans Orthophotos to only keep selected providers and zoom levels.
  Handles structures like:
    Imagery_dir/+lat10+lon10/+lat+lon/BI_17/
    Imagery_dir/BI/BI_17/+lat+lon/
  """
  if not os.path.isdir(root_dir):
    return

  keep_prov_upper = {p.upper() for p in keep_providers} if keep_providers else set()

  # Pass 1: remove top-level provider buckets not in list (e.g., Imagery_dir/GO2/)
  for name in os.listdir(root_dir):
    p = os.path.join(root_dir, name)
    if not os.path.isdir(p):
      continue
    # Treat a pure alnum name as a provider root
    if re.fullmatch(r"[A-Za-z0-9]+", name) and keep_prov_upper and name.upper() not in keep_prov_upper:
      rm_path(p)

  # Pass 2: recursively remove provider/ZL folders that don't match
  for dirpath, dirnames, _ in os.walk(root_dir):
    for d in list(dirnames):
      sub = os.path.join(dirpath, d)
      if not os.path.isdir(sub):
        continue
      prov, zl = parse_provider_and_zl_from_dir(d)
      if prov is not None:
        if keep_prov_upper and prov.upper() not in keep_prov_upper:
          rm_path(sub)
          continue
        if allowed_zls and (zl is None or zl not in allowed_zls):
          rm_path(sub)
          continue
        keep_path(sub)


def clean_output_tiles(tiles_root: str, allowed_tokens: set[str], keep_providers: set[str], allowed_zls: set[int]):
  """
  Clean zOrtho4XP_* tiles, removing those not in the list and filtering textures by provider/ZL.

  Supports:
    - Flat texture files, e.g.: 194352_298496_BI19.dds (default Ortho4XP)
    - textures subfolders like 'BI_17'
    - 'BI/17' two-level layouts (best-effort)
  """
  if not os.path.isdir(tiles_root):
    return

  keep_prov_upper = {p.upper() for p in keep_providers} if keep_providers else set()

  def _ok(prov: str | None, zl: int | None) -> bool:
    if prov is not None and keep_prov_upper and prov.upper() not in keep_prov_upper:
      return False
    if allowed_zls and (zl is None or zl not in allowed_zls):
      return False
    return True

  for name in os.listdir(tiles_root):
    tile_path = os.path.join(tiles_root, name)
    if not os.path.isdir(tile_path):
      continue
    if not name.startswith("zOrtho4XP_"):
      continue

    token = name.replace("zOrtho4XP_", "")
    if token not in allowed_tokens:
      rm_path(tile_path)
      continue

    keep_path(tile_path)

    textures_path = os.path.join(tile_path, "textures")
    if not os.path.isdir(textures_path):
      continue

    # 1) Subfolders like 'BI_17'
    for subname in list(os.listdir(textures_path)):
      subpath = os.path.join(textures_path, subname)
      if not os.path.isdir(subpath):
        continue

      prov, zl = parse_provider_and_zl_from_dir(subname)
      if prov is not None:
        if not _ok(prov, zl):
          rm_path(subpath)
        else:
          keep_path(subpath)
        continue

      # Best-effort for 'BI/17' layout
      if re.fullmatch(r"[A-Za-z0-9]+", subname):
        prov_only = subname
        for zlname in list(os.listdir(subpath)):
          zlpath = os.path.join(subpath, zlname)
          if not os.path.isdir(zlpath):
            continue
          try:
            zl_val = int(zlname)
          except ValueError:
            continue
          if not _ok(prov_only, zl_val):
            rm_path(zlpath)
          else:
            keep_path(zlpath)
        # If provider folder ends up empty, remove it
        if is_empty_dir(subpath):
          rm_path(subpath)

    # 2) Flat files: 194352_298496_BI19.dds, 48576_74592_BI17.dds
    for fname in list(os.listdir(textures_path)):
      fpath = os.path.join(textures_path, fname)
      if not os.path.isfile(fpath):
        continue

      # Skip g2xpl_16 special filenames (unknown ZL mapping). Optional: remove if filters are set.
      if _G2XPL_TEX_FILE_RE.match(fname):
        # If desired, delete when filters active:
        # if (keep_prov_upper or allowed_zls):
        #     rm_path(fpath)
        continue

      m = _TEX_FILE_RE.match(fname)
      if not m:
        # Unknown pattern; leave it alone
        continue

      prov, zl_txt = m.group(1), m.group(2)
      zl = int(zl_txt)

      if not _ok(prov, zl):
        rm_path(fpath)
      else:
        keep_path(fpath)

    # Optional: clean up an empty textures dir (if everything inside was removed)
    if is_empty_dir(textures_path):
      rm_path(textures_path)


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
  bands_allow, tiles_allow = allowed_sets(tiles)

  print("=== Cleaning MASKS ===")
  clean_banded_tree(FNAMES.Mask_dir, bands_allow, tiles_allow)

  print("=== Cleaning ORTHOPHOTOS (bands/tiles) ===")
  clean_banded_tree(FNAMES.Imagery_dir, bands_allow, tiles_allow)

  print("=== Enforcing provider/ZL in ORTHOPHOTOS ===")
  clean_orthophotos_by_provider_and_zl(FNAMES.Imagery_dir, KEEP_PROVIDERS, ALLOWED_ZLS)

  print("=== Cleaning OSM_DATA ===")
  clean_banded_tree(FNAMES.OSM_dir, bands_allow, tiles_allow)

  print("=== Cleaning ELEVATION DATA ===")
  clean_banded_tree(FNAMES.Elevation_dir, bands_allow, tiles_allow)

  print("=== Cleaning OUTPUT TILE FOLDERS (zOrtho4XP_*) ===")
  clean_output_tiles(FNAMES.Tile_dir, tiles_allow, KEEP_PROVIDERS, ALLOWED_ZLS)

  print("\nDone. (Dry run: {})".format(DRY_RUN))
