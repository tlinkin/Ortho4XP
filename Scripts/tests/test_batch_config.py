"""Tests for batch configuration loading and validation."""

import os
from pathlib import Path

import pytest

from batch.config import (
    Config,
    ConfigError,
    expand_path,
    get_tile_config,
    load_config,
    validate_config,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_toml(self, valid_toml):
        """Parse valid TOML, verify all fields accessible."""
        config = load_config(valid_toml)
        assert config.batch.output_dir == Path("/tmp/output")
        assert config.batch.dem_dir == Path("/tmp/dem")
        assert config.sources.countries == ["USA"]
        assert config.sources.tiles == [(45, -122)]

    def test_load_full_toml(self, full_toml):
        """Parse full TOML with all options."""
        config = load_config(full_toml)
        assert config.batch.output_dir == Path("/tmp/output")
        assert config.batch.state_file == Path("custom_state.toml")
        assert config.app.verbosity == 2
        assert config.app.max_download_slots == 2
        assert config.tile.default_zl == 17
        assert config.tile.curvature_tol == 2.0
        assert "+45-122" in config.tile_overrides

    def test_missing_batch_section(self, tmp_path):
        """Raise error for missing [batch] section."""
        config = tmp_path / "bad.toml"
        config.write_text('[sources]\ncountries = ["USA"]')
        with pytest.raises(ConfigError, match="batch"):
            load_config(config)

    def test_missing_output_dir(self, tmp_path):
        """Raise error for missing output_dir."""
        config = tmp_path / "bad.toml"
        config.write_text('[batch]\ndem_dir = "/tmp"')
        with pytest.raises(ConfigError, match="output_dir"):
            load_config(config)

    def test_missing_dem_dir(self, tmp_path):
        """Raise error for missing dem_dir."""
        config = tmp_path / "bad.toml"
        config.write_text('[batch]\noutput_dir = "/tmp"')
        with pytest.raises(ConfigError, match="dem_dir"):
            load_config(config)

    def test_invalid_toml_syntax(self, tmp_path):
        """Graceful error on malformed TOML."""
        config = tmp_path / "bad.toml"
        config.write_text("[batch\nbroken")
        with pytest.raises(ConfigError, match="TOML|parse"):
            load_config(config)

    def test_file_not_found(self, tmp_path):
        """Raise error for non-existent config file."""
        config = tmp_path / "nonexistent.toml"
        with pytest.raises(ConfigError, match="not found|No such file"):
            load_config(config)


class TestDefaults:
    """Tests for default value handling."""

    def test_app_defaults_applied(self, valid_toml):
        """Verify app defaults fill in missing values."""
        config = load_config(valid_toml)
        assert config.app.verbosity == 1
        assert config.app.cleaning_level == 1
        assert config.app.max_download_slots == 1
        assert config.app.max_convert_slots == 4
        assert config.app.check_tms_response is True
        assert config.app.http_timeout == 10.0
        assert config.app.max_connect_retries == 5
        assert config.app.max_baddata_retries == 5

    def test_tile_defaults_applied(self, valid_toml):
        """Verify tile defaults fill in missing values."""
        config = load_config(valid_toml)
        assert config.tile.default_zl == 16
        assert config.tile.curvature_tol == 2.0
        assert config.tile.mesh_zl == 19
        assert config.tile.apt_smoothing_pix == 8
        assert config.tile.iterate == 0
        assert config.tile.mask_zl == 14

    def test_batch_defaults_applied(self, valid_toml):
        """Verify batch defaults for optional fields."""
        config = load_config(valid_toml)
        assert config.batch.state_file == Path("batch_state.toml")

    def test_empty_sources_defaults(self, tmp_path):
        """Empty sources lists default correctly."""
        config = tmp_path / "config.toml"
        config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"
''')
        cfg = load_config(config)
        assert cfg.sources.countries == []
        assert cfg.sources.tiles == []


class TestTileOverrides:
    """Tests for per-tile configuration overrides."""

    def test_tile_overrides_merge(self, tmp_path):
        """Per-tile config merges with defaults."""
        config = tmp_path / "override.toml"
        config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"

[sources]
tiles = [[45, -122]]

[tile]
iterate = 0

[tile_overrides."+45-122"]
custom_dem = "/path/to/lidar.tif"
iterate = 3
''')
        cfg = load_config(config)
        tile_cfg = get_tile_config(cfg, 45, -122)
        assert tile_cfg.custom_dem == "/path/to/lidar.tif"
        assert tile_cfg.iterate == 3

    def test_non_overridden_tile_gets_defaults(self, tmp_path):
        """Non-overridden tile gets base tile config."""
        config = tmp_path / "override.toml"
        config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"

[sources]
tiles = [[45, -122], [46, -123]]

[tile]
iterate = 0
default_zl = 17

[tile_overrides."+45-122"]
iterate = 3
''')
        cfg = load_config(config)
        other = get_tile_config(cfg, 46, -123)
        assert other.iterate == 0
        assert other.default_zl == 17

    def test_negative_coordinates_override(self, tmp_path):
        """Override works with negative coordinates."""
        config = tmp_path / "neg.toml"
        config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"

[sources]
tiles = [[-45, -122]]

[tile_overrides."-45-122"]
iterate = 5
''')
        cfg = load_config(config)
        tile_cfg = get_tile_config(cfg, -45, -122)
        assert tile_cfg.iterate == 5

    def test_positive_lon_override(self, tmp_path):
        """Override works with positive longitude."""
        config = tmp_path / "pos.toml"
        config.write_text('''
[batch]
output_dir = "/tmp/output"
dem_dir = "/tmp/dem"

[sources]
tiles = [[45, 10]]

[tile_overrides."+45+010"]
iterate = 2
''')
        cfg = load_config(config)
        tile_cfg = get_tile_config(cfg, 45, 10)
        assert tile_cfg.iterate == 2


class TestPathExpansion:
    """Tests for path expansion functionality."""

    def test_expand_home_dir(self):
        """Expand ~ to home directory."""
        result = expand_path("~/foo")
        assert result == Path.home() / "foo"

    def test_expand_env_var_dollar(self):
        """Expand $VAR style environment variables."""
        os.environ["TEST_BATCH_DIR"] = "/test/path"
        result = expand_path("$TEST_BATCH_DIR/bar")
        assert result == Path("/test/path/bar")

    def test_expand_env_var_braces(self):
        """Expand ${VAR} style environment variables."""
        os.environ["TEST_BATCH_DIR"] = "/test/path"
        result = expand_path("${TEST_BATCH_DIR}/baz")
        assert result == Path("/test/path/baz")

    def test_expand_absolute_path(self):
        """Absolute paths pass through unchanged."""
        result = expand_path("/absolute/path")
        assert result == Path("/absolute/path")

    def test_expand_relative_path(self):
        """Relative paths converted to Path."""
        result = expand_path("relative/path")
        assert result == Path("relative/path")


class TestValidation:
    """Tests for configuration validation."""

    def test_validate_nonexistent_output_dir(self, tmp_path):
        """Validation warns about non-existent output_dir."""
        config = tmp_path / "config.toml"
        config.write_text('''
[batch]
output_dir = "/nonexistent/output"
dem_dir = "/nonexistent/dem"

[sources]
tiles = [[45, -122]]
''')
        cfg = load_config(config)
        errors = validate_config(cfg)
        assert any("output_dir" in e for e in errors)

    def test_validate_nonexistent_dem_dir(self, tmp_path):
        """Validation warns about non-existent dem_dir."""
        config = tmp_path / "config.toml"
        config.write_text('''
[batch]
output_dir = "/tmp"
dem_dir = "/nonexistent/dem"

[sources]
tiles = [[45, -122]]
''')
        cfg = load_config(config)
        errors = validate_config(cfg)
        assert any("dem_dir" in e for e in errors)

    def test_validate_empty_sources(self, tmp_path):
        """Validation warns if no countries or tiles specified."""
        config = tmp_path / "empty.toml"
        config.write_text('''
[batch]
output_dir = "/tmp"
dem_dir = "/tmp"

[sources]
countries = []
tiles = []
''')
        cfg = load_config(config)
        errors = validate_config(cfg)
        assert any("sources" in e.lower() or "tiles" in e.lower() for e in errors)

    def test_validate_valid_config(self, tmp_path):
        """Valid config returns no errors."""
        # Create actual directories
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = tmp_path / "config.toml"
        config.write_text(f'''
[batch]
output_dir = "{output_dir}"
dem_dir = "{dem_dir}"

[sources]
tiles = [[45, -122]]
''')
        cfg = load_config(config)
        errors = validate_config(cfg)
        assert errors == []

    def test_validate_invalid_zoom_level(self, tmp_path):
        """Validation warns about invalid zoom levels."""
        output_dir = tmp_path / "output"
        dem_dir = tmp_path / "dem"
        output_dir.mkdir()
        dem_dir.mkdir()

        config = tmp_path / "config.toml"
        config.write_text(f'''
[batch]
output_dir = "{output_dir}"
dem_dir = "{dem_dir}"

[sources]
tiles = [[45, -122]]

[tile]
default_zl = 25
mesh_zl = 25
''')
        cfg = load_config(config)
        errors = validate_config(cfg)
        assert any("zl" in e.lower() or "zoom" in e.lower() for e in errors)
