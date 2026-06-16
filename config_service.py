import json
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass
class DeviceConfig:
    name: str
    mac_address: str


@dataclass
class AppConfig:
    devices: list[DeviceConfig]
    scan_interval_seconds: int = 300
    scan_duration_seconds: int = 10


def load_config(path: Path = Path("config.json")) -> AppConfig:
    if not path.exists():
        _create_example_config(path)
        raise ConfigError(f"config.json nicht gefunden. Beispiel-Config erstellt unter: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json enthält ungültiges JSON: {exc}") from exc
    devices = [
        DeviceConfig(name=d["name"], mac_address=d["macAddress"])
        for d in data.get("devices", [])
    ]
    return AppConfig(
        devices=devices,
        scan_interval_seconds=int(data.get("scan_interval_seconds", 300)),
        scan_duration_seconds=int(data.get("scan_duration_seconds", 10)),
    )


def _create_example_config(path: Path) -> None:
    example = {
        "devices": [
            {"name": "Wohnzimmer", "macAddress": "AA:BB:CC:DD:EE:FF"},
            {"name": "Terrasse",   "macAddress": "11:22:33:44:55:66"},
        ],
        "scan_interval_seconds": 300,
        "scan_duration_seconds": 10,
    }
    path.write_text(json.dumps(example, indent=2, ensure_ascii=False), encoding="utf-8")
