"""
Lightweight library to compute 1°×1° WGS84 tiles (Ortho4XP style, e.g. +42+014)
that intersect or are fully contained within:
  - a list of countries (ISO3 or names), or
  - a continent (UN geoscheme), or
  - an arbitrary Shapely geometry.

Public API:
  - list_tiles_for_countries(countries: list[str], full_only: bool = False) -> list[str]
  - list_tiles_for_continent(continent: str, full_only: bool = False) -> list[str]
  - list_tiles_for_geometry(geom, full_only: bool = False) -> list[str]
  - tile_code(lat_deg: int, lon_deg: int) -> str
  - tile_bbox(code: str) -> shapely.geometry.Polygon

Notes:
- Coordinates and grids are in EPSG:4326 (WGS84 lon/lat).
- Ortho4XP naming is ±DD for latitude and ±DDD for longitude with sign.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Set, Tuple

import requests
from shapely.geometry import Polygon, box, shape
from shapely.ops import unary_union

__all__ = [
  "list_tiles_for_countries",
  "list_tiles_for_continent",
  "list_tiles_for_geometry",
  "tile_code",
  "tile_bbox",
]

# ---------------------------------------------------------------------
# DATA SOURCES
# ---------------------------------------------------------------------
_NE_COUNTRIES_URLS = (
  "https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson",
  "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson",
)
_UN_CODES_URL = (
  "https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/master/all/all.json"
)


# ---------------------------------------------------------------------
# Fetchers (cached)
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def _fetch_countries_geojson() -> dict:
  last_err = None
  for url in _NE_COUNTRIES_URLS:
    try:
      r = requests.get(url, timeout=60)
      r.raise_for_status()
      return r.json()
    except Exception as e:
      last_err = e
  raise RuntimeError(f"Failed to download countries GeoJSON: {last_err}")


@lru_cache(maxsize=1)
def _fetch_un_codes() -> list[dict]:
  r = requests.get(_UN_CODES_URL, timeout=60)
  r.raise_for_status()
  return r.json()


# ---------------------------------------------------------------------
# Property helpers (schema-robust)
# ---------------------------------------------------------------------
def _get_iso3(props: dict) -> str:
  return (
      props.get("ISO_A3")
      or props.get("ISO3166-1-Alpha-3")
      or props.get("alpha-3")
      or ""
  ).strip().upper()


def _get_name(props: dict) -> str:
  return (props.get("ADMIN") or props.get("name") or "").strip().lower()


# ---------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------
def tile_code(lat_deg: int, lon_deg: int) -> str:
  """
  Build Ortho4XP-style code: ±DD ±DDD (with signs).
  Examples:
    tile_code(42, 14)  -> '+42+014'
    tile_code(-42, -6) -> '-42-006'
  """
  return f"{lat_deg:+03d}{lon_deg:+04d}"


def tile_bbox(code: str) -> Polygon:
  """
  Convert code like '+42+014' back to a 1×1 degree bbox polygon.
  """
  if len(code) not in (7, 8):  # e.g., '+42+014' (8), '-42-006' (8); '+9+009' (7)
    raise ValueError(f"Invalid tile code: {code}")

  # Parse signed ints: first 3 chars for lat (±DD), next 4 for lon (±DDD)
  lat_str = code[:3]
  lon_str = code[3:]
  lat = int(lat_str)
  lon = int(lon_str)
  return box(lon, lat, lon + 1, lat + 1)


# ---------------------------------------------------------------------
# Region builders
# ---------------------------------------------------------------------
def _iso3_by_continent(target_continent: str) -> set[str]:
  """
  Resolve a continent name to a set of ISO3 codes via UN geoscheme.
  Accepts: 'Europe', 'Africa', 'Asia', 'Oceania', 'Antarctica',
           'Americas', 'North America', 'South America'
  """
  target = target_continent.strip().lower()
  data = _fetch_un_codes()

  def belongs(row):
    r = (row.get("region") or "").strip().lower()
    sr = (row.get("sub-region") or "").strip().lower()
    if target in ("europe", "africa", "asia", "oceania", "antarctica"):
      return r == target
    if target in ("north america", "south america", "americas"):
      if target == "americas":
        return r == "americas"
      return sr == target
    return False

  return {
    (row.get("alpha-3") or "").strip().upper()
    for row in data
    if belongs(row)
  }


def _country_features() -> list[dict]:
  gj = _fetch_countries_geojson()
  feats = gj.get("features", [])
  if not feats:
    raise RuntimeError("No features in countries GeoJSON.")
  return feats


def _geometry_for_countries(countries: Iterable[str]) -> Polygon:
  """
  countries: ISO3 or names (case-insensitive for names).
  Returns unified Shapely geometry.
  """
  want_iso3 = {c.strip().upper() for c in countries}
  want_names = {c.strip().lower() for c in countries}
  geoms = []

  for f in _country_features():
    props = f.get("properties", {})
    iso3 = _get_iso3(props)
    name = _get_name(props)
    if iso3 in want_iso3 or name in want_names:
      geoms.append(shape(f["geometry"]))

  if not geoms:
    raise ValueError("No matching countries found.")
  return unary_union(geoms).buffer(0)  # buffer(0) to clean topology


def _geometry_for_continent(continent: str) -> Polygon:
  iso3_set = _iso3_by_continent(continent)
  geoms = []
  for f in _country_features():
    if _get_iso3(f.get("properties", {})) in iso3_set:
      geoms.append(shape(f["geometry"]))
  if not geoms:
    raise ValueError(f"No countries found for continent: {continent}")
  return unary_union(geoms).buffer(0)


# ---------------------------------------------------------------------
# Tiling core
# ---------------------------------------------------------------------
def _tiles_for_geometry(
    geom,
    include_partial: bool = True,
    lat_min: int = -90,
    lat_max: int = 89,
    lon_min: int = -180,
    lon_max: int = 179,
) -> list[Tuple[int, int]]:
  """
  Return sorted list of Ortho4XP-style codes intersecting (or within) geom.
  """
  result: Set[Tuple[int, int]] = set()

  gminx, gminy, gmaxx, gmaxy = geom.bounds
  lat_start = max(lat_min, int(max(-90, int(gminy) - 1)))
  lat_end = min(lat_max, int(min(89, int(gmaxy) + 1)))
  lon_start = max(lon_min, int(max(-180, int(gminx) - 1)))
  lon_end = min(lon_max, int(min(179, int(gmaxx) + 1)))

  for lat in range(lat_start, lat_end + 1):
    for lon in range(lon_start, lon_end + 1):
      cell = box(lon, lat, lon + 1, lat + 1)
      if include_partial:
        if geom.intersects(cell):
          result.add((lat, lon))
      else:
        if cell.within(geom):
          result.add((lat, lon))

  return sorted(result)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def list_tiles_for_countries(
    countries: Iterable[str],
    full_only: bool = False,
) -> list[Tuple[int, int]]:
  """
  Get tiles that cover the given countries (ISO3 or names).
  """
  geom = _geometry_for_countries(countries)
  return _tiles_for_geometry(geom, include_partial=not full_only)


def list_tiles_for_continent(
    continent: str,
    full_only: bool = False,
) -> list[Tuple[int, int]]:
  """
  Get tiles that cover the given continent.
  """
  geom = _geometry_for_continent(continent)
  return _tiles_for_geometry(geom, include_partial=not full_only)


def list_tiles_for_geometry(
    geom: Polygon,
    full_only: bool = False,
) -> list[Tuple[int, int]]:
  """
  Get tiles for any arbitrary Shapely geometry.
  """
  return _tiles_for_geometry(geom, include_partial=not full_only)
