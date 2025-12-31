"""Shared pytest fixtures for batch processing tests."""

import os
import sys
from pathlib import Path

import pytest

# Add Scripts directory to path for imports
scripts_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(scripts_dir))


@pytest.fixture
def valid_toml(tmp_path):
    """Create a valid minimal TOML config."""
    config = tmp_path / "batch_config.toml"
    config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"

[sources]
countries = ["USA"]
tiles = [[45, -122]]
''')
    return config


@pytest.fixture
def full_toml(tmp_path):
    """Create a full TOML config with all options."""
    config = tmp_path / "batch_config.toml"
    config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"
state_file = "custom_state.toml"

[sources]
countries = ["USA", "CAN"]
tiles = [[45, -122], [46, -123]]

[app]
verbosity = 2
cleaning_level = 2
overpass_server_choice = "DE"
skip_downloads = false
skip_converts = false
max_download_slots = 2
max_convert_slots = 8
check_tms_response = true
http_timeout = 30.0
max_connect_retries = 10
max_baddata_retries = 10
ovl_exclude_pol = [0, 1]
ovl_exclude_net = [22001]
custom_scenery_dir = "/tmp/scenery"
custom_overlay_src = "/tmp/overlay"
custom_overlay_src_alternate = ""

[tile]
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
mask_zl = 14
masks_width = 100
masking_mode = "sand"
use_masks_for_inland = false
imprint_masks_to_dds = false
distance_masks_too = false
masks_use_DEM_too = false
masks_custom_extent = ""
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
custom_dem = ""
fill_nodata = true

[tile_overrides."+45-122"]
custom_dem = "/path/to/lidar.tif"
iterate = 3
''')
    return config
