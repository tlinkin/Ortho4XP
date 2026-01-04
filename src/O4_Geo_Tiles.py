"""
Lightweight library to compute 1x1 WGS84 tiles (Ortho4XP style, e.g. +42+014)
that intersect a list of countries specified by ISO3 codes.

Public API:
  - list_tiles_for_countries(iso3_codes: list[str], full_only: bool = False) -> list[tuple[int, int]]

Notes:
- Coordinates and grids are in EPSG:4326 (WGS84 lon/lat).
- Only ISO3 codes (e.g., CHE, AUT, ITA) are supported.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Set, Tuple

import requests
from shapely.geometry import Polygon, box, shape
from shapely.ops import unary_union

__all__ = [
    "list_tiles_for_countries",
]

# ---------------------------------------------------------------------
# DATA SOURCES
# ---------------------------------------------------------------------
_NE_COUNTRIES_URLS = (
    "https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson",
    "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson",
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


# ---------------------------------------------------------------------
# Property helpers
# ---------------------------------------------------------------------
def _get_iso3(props: dict) -> str:
    return (
        props.get("ISO_A3")
        or props.get("ISO3166-1-Alpha-3")
        or props.get("alpha-3")
        or ""
    ).strip().upper()


# ---------------------------------------------------------------------
# Region builders
# ---------------------------------------------------------------------
def _country_features() -> list[dict]:
    gj = _fetch_countries_geojson()
    feats = gj.get("features", [])
    if not feats:
        raise RuntimeError("No features in countries GeoJSON.")
    return feats


def _geometry_for_iso3_codes(iso3_codes: Iterable[str]) -> Polygon:
    """
    Get unified geometry for countries matching ISO3 codes.
    """
    want_iso3 = {c.strip().upper() for c in iso3_codes}
    geoms = []

    for f in _country_features():
        props = f.get("properties", {})
        iso3 = _get_iso3(props)
        if iso3 in want_iso3:
            geoms.append(shape(f["geometry"]))

    if not geoms:
        raise ValueError(f"No matching countries found for: {want_iso3}")
    return unary_union(geoms).buffer(0)  # buffer(0) to clean topology


# ---------------------------------------------------------------------
# Tiling core
# ---------------------------------------------------------------------
def _tiles_for_geometry(
    geom,
    include_partial: bool = True,
) -> list[Tuple[int, int]]:
    """
    Return sorted list of Ortho4XP-style tiles intersecting (or within) geom.
    """
    result: Set[Tuple[int, int]] = set()

    gminx, gminy, gmaxx, gmaxy = geom.bounds
    lat_start = max(-90, int(gminy) - 1)
    lat_end = min(89, int(gmaxy) + 1)
    lon_start = max(-180, int(gminx) - 1)
    lon_end = min(179, int(gmaxx) + 1)

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
    iso3_codes: Iterable[str],
    full_only: bool = False,
) -> list[Tuple[int, int]]:
    """
    Get tiles that cover the given countries (ISO3 codes only).

    Args:
        iso3_codes: List of ISO3 country codes (e.g., ['CHE', 'AUT', 'ITA'])
        full_only: If True, only return tiles fully within the countries

    Returns:
        List of (lat, lon) tuples for matching tiles
    """
    geom = _geometry_for_iso3_codes(iso3_codes)
    return _tiles_for_geometry(geom, include_partial=not full_only)
