import json
import pytest
from pathlib import Path
from config_service import load_config, ConfigError, AppConfig, DeviceConfig


def test_raises_config_error_for_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="nicht gefunden"):
        load_config(tmp_path / "nonexistent.json")


def test_creates_example_config_when_missing(tmp_path):
    path = tmp_path / "config.json"
    with pytest.raises(ConfigError):
        load_config(path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "devices" in data


def test_raises_config_error_for_invalid_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("kein gültiges json {{}", encoding="utf-8")
    with pytest.raises(ConfigError, match="ungültiges JSON"):
        load_config(path)


def test_loads_two_devices(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "devices": [
            {"name": "Wohnzimmer", "macAddress": "AA:BB:CC:DD:EE:FF"},
            {"name": "Terrasse",   "macAddress": "11:22:33:44:55:66"},
        ]
    }), encoding="utf-8")
    config = load_config(path)
    assert len(config.devices) == 2
    assert config.devices[0].name == "Wohnzimmer"
    assert config.devices[0].mac_address == "AA:BB:CC:DD:EE:FF"
    assert config.devices[1].name == "Terrasse"
    assert config.devices[1].mac_address == "11:22:33:44:55:66"


def test_defaults_scan_params(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": []}), encoding="utf-8")
    config = load_config(path)
    assert config.scan_interval_seconds == 300
    assert config.scan_duration_seconds == 10


def test_custom_scan_params(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "devices": [],
        "scan_interval_seconds": 60,
        "scan_duration_seconds": 5,
    }), encoding="utf-8")
    config = load_config(path)
    assert config.scan_interval_seconds == 60
    assert config.scan_duration_seconds == 5
