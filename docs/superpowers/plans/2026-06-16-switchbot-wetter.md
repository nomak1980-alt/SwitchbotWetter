# SwitchBot Wetter — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows-Tray-Anwendung in Python, die SwitchBot Outdoor Meter per BLE-Advertisement passiv ausliest und Temperatur/Luftfeuchtigkeit im System-Tray anzeigt.

**Architecture:** Drei Threads (Main/tkinter, pystray-Daemon, BLE-asyncio-Daemon) kommunizieren über einen Lock-geschützten In-Memory-Cache. `device_parser.py` ist plattformunabhängig und MicroPython-kompatibel. BLE-Scanning via `bleak` im aktiven Modus ohne UUID-Filter, MAC-Filterung nach Empfang.

**Tech Stack:** Python 3.10+, bleak 0.21+, pystray 0.19+, Pillow 10+, tkinter (stdlib), pytest

---

## Dateiübersicht

| Datei | Zweck |
|-------|-------|
| `requirements.txt` | Runtime + Dev-Abhängigkeiten |
| `pytest.ini` | Test-Konfiguration |
| `config.json` | Gerätekonfiguration (Beispiel) |
| `log_service.py` | RotatingFileHandler-Setup |
| `config_service.py` | config.json lesen, DeviceConfig/AppConfig |
| `device_parser.py` | BLE Advertisement-Bytes → SensorReading (plattformunabhängig) |
| `ble_scanner.py` | bleak-Scanner, Cache, Cross-Thread-Koordination |
| `ui/__init__.py` | Package-Marker |
| `ui/popup_window.py` | tkinter Toplevel-Popup |
| `main.py` | Einstiegspunkt, Threading-Verdrahtung |
| `tests/test_config_service.py` | Config-Unit-Tests |
| `tests/test_device_parser.py` | Parser-Unit-Tests |
| `tests/test_ble_scanner.py` | Scanner-Unit-Tests (ohne BLE-Hardware) |

---

## Task 1: Projektgerüst

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `config.json`
- Create: `ui/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Schritt 1: requirements.txt erstellen**

```text
bleak>=0.21.0
pystray>=0.19.0
Pillow>=10.0.0
pytest>=7.4.0
```

- [ ] **Schritt 2: pytest.ini erstellen**

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Schritt 3: config.json (Beispiel) erstellen**

```json
{
  "devices": [
    {"name": "Wohnzimmer", "macAddress": "AA:BB:CC:DD:EE:FF"},
    {"name": "Terrasse",   "macAddress": "11:22:33:44:55:66"}
  ],
  "scan_interval_seconds": 300,
  "scan_duration_seconds": 10
}
```

- [ ] **Schritt 4: Package-Marker erstellen**

`ui/__init__.py` und `tests/__init__.py` — beide leer.

- [ ] **Schritt 5: Abhängigkeiten installieren**

```bash
pip install -r requirements.txt
```

Erwartete Ausgabe: Alle vier Pakete werden ohne Fehler installiert.

- [ ] **Schritt 6: Commit**

```bash
git init
git add requirements.txt pytest.ini config.json ui/__init__.py tests/__init__.py
git commit -m "chore: Projektgerüst — Abhängigkeiten, Config-Beispiel, Package-Marker"
```

---

## Task 2: Logging-Service

**Files:**
- Create: `log_service.py`

- [ ] **Schritt 1: log_service.py schreiben**

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_path: Path = Path("switchbot_wetter.log"), debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    )
    logging.basicConfig(level=level, handlers=[handler])
```

- [ ] **Schritt 2: Manuell prüfen**

```python
# In Python-REPL ausführen:
from log_service import setup_logging
from pathlib import Path
import logging
setup_logging(Path("test_log.log"), debug=True)
logging.getLogger("test").debug("Logging funktioniert")
# Prüfen: test_log.log enthält den Eintrag
# Danach test_log.log löschen
```

- [ ] **Schritt 3: Commit**

```bash
git add log_service.py
git commit -m "feat: Logging-Service mit RotatingFileHandler"
```

---

## Task 3: Config-Service + Tests

**Files:**
- Create: `config_service.py`
- Create: `tests/test_config_service.py`

- [ ] **Schritt 1: Failing Tests schreiben**

`tests/test_config_service.py`:

```python
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
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_config_service.py -v
```

Erwartete Ausgabe: `ImportError: No module named 'config_service'`

- [ ] **Schritt 3: config_service.py implementieren**

```python
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
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_config_service.py -v
```

Erwartete Ausgabe: `6 passed`

- [ ] **Schritt 5: Commit**

```bash
git add config_service.py tests/test_config_service.py
git commit -m "feat: Config-Service mit Fehlerbehandlung und Beispiel-Config-Generierung"
```

---

## Task 4: Device-Parser + Tests

**Files:**
- Create: `device_parser.py`
- Create: `tests/test_device_parser.py`

- [ ] **Schritt 1: Failing Tests schreiben**

`tests/test_device_parser.py`:

```python
import pytest
from datetime import datetime
from device_parser import parse, SensorReading, SWITCHBOT_COMPANY_ID, SWITCHBOT_SERVICE_UUID


def _make_mfr(temp_int: int, temp_dec: int, positive: bool, humidity: int) -> bytes:
    """Hilfsfunktion: erzeugt synthetische Manufacturer-Data-Bytes."""
    data = bytearray(11)
    data[8] = temp_dec & 0x0F
    data[9] = (temp_int & 0x7F) | (0x80 if positive else 0x00)
    data[10] = humidity & 0x7F
    return bytes(data)


def _make_svc(battery: int, device_type: int = 0x54) -> bytes:
    data = bytearray(3)
    data[0] = device_type & 0x7F
    data[2] = battery & 0x7F
    return bytes(data)


# --- Negativfälle ---

def test_returns_none_with_empty_dicts():
    assert parse("AA:BB:CC:DD:EE:FF", {}, {}) is None


def test_returns_none_with_wrong_company_id():
    assert parse("AA:BB:CC:DD:EE:FF", {0x1234: b"\x00" * 11}, {}) is None


def test_returns_none_with_too_short_manufacturer_data():
    assert parse("AA:BB:CC:DD:EE:FF", {SWITCHBOT_COMPANY_ID: b"\x00" * 8}, {}) is None


# --- Positivfälle ---

def test_parses_positive_temperature_and_humidity():
    mfr = _make_mfr(temp_int=22, temp_dec=3, positive=True, humidity=48)
    svc = _make_svc(battery=85)
    result = parse("AA:BB:CC:DD:EE:FF",
                   {SWITCHBOT_COMPANY_ID: mfr},
                   {SWITCHBOT_SERVICE_UUID: svc})
    assert result is not None
    assert result.temperature == pytest.approx(22.3)
    assert result.humidity == 48
    assert result.battery == 85
    assert result.mac_address == "AA:BB:CC:DD:EE:FF"


def test_parses_negative_temperature():
    mfr = _make_mfr(temp_int=3, temp_dec=5, positive=False, humidity=70)
    result = parse("AA:BB:CC:DD:EE:FF", {SWITCHBOT_COMPANY_ID: mfr}, {})
    assert result is not None
    assert result.temperature == pytest.approx(-3.5)


def test_parses_zero_degrees():
    mfr = _make_mfr(temp_int=0, temp_dec=0, positive=True, humidity=50)
    result = parse("AA:BB:CC:DD:EE:FF", {SWITCHBOT_COMPANY_ID: mfr}, {})
    assert result is not None
    assert result.temperature == pytest.approx(0.0)


def test_battery_none_when_no_service_data():
    mfr = _make_mfr(22, 0, True, 50)
    result = parse("AA:BB:CC:DD:EE:FF", {SWITCHBOT_COMPANY_ID: mfr}, {})
    assert result is not None
    assert result.battery is None


def test_battery_parsed_from_service_data():
    mfr = _make_mfr(20, 0, True, 60)
    svc = _make_svc(battery=73)
    result = parse("AA:BB:CC:DD:EE:FF",
                   {SWITCHBOT_COMPANY_ID: mfr},
                   {SWITCHBOT_SERVICE_UUID: svc})
    assert result.battery == 73


def test_timestamp_is_recent_datetime():
    mfr = _make_mfr(20, 0, True, 50)
    result = parse("AA:BB:CC:DD:EE:FF", {SWITCHBOT_COMPANY_ID: mfr}, {})
    assert isinstance(result.timestamp, datetime)


def test_humidity_max_boundary():
    mfr = _make_mfr(25, 0, True, 99)
    result = parse("AA:BB:CC:DD:EE:FF", {SWITCHBOT_COMPANY_ID: mfr}, {})
    assert result.humidity == 99


def test_mac_address_stored_on_reading():
    mfr = _make_mfr(20, 0, True, 50)
    result = parse("11:22:33:44:55:66", {SWITCHBOT_COMPANY_ID: mfr}, {})
    assert result.mac_address == "11:22:33:44:55:66"
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_device_parser.py -v
```

Erwartete Ausgabe: `ImportError: No module named 'device_parser'`

- [ ] **Schritt 3: device_parser.py implementieren**

```python
import dataclasses
from dataclasses import dataclass
from datetime import datetime

SWITCHBOT_COMPANY_ID: int = 0x0969
SWITCHBOT_SERVICE_UUID: str = "0000fd3d-0000-1000-8000-00805f9b34fb"


@dataclass
class SensorReading:
    mac_address: str
    temperature: float
    humidity: int
    battery: int | None
    timestamp: datetime


def parse(
    mac_address: str,
    manufacturer_data: dict[int, bytes],
    service_data: dict[str, bytes],
) -> SensorReading | None:
    """
    Parst SwitchBot Outdoor Meter W3400010 BLE-Advertisement.

    Gibt None zurück wenn keine Manufacturer-Data mit Company-ID 0x0969 vorhanden.
    Plattformunabhängig: erhält nur dict/bytes, keine bleak-Typen.

    Byte-Layout Manufacturer Data (Company-ID-Bytes von bleak bereits entfernt):
      [8]  & 0x0F  = Temperatur Dezimal (× 0.1)
      [9]  & 0x7F  = Temperatur Integer (°C)
      [9]  & 0x80  = Vorzeichen (gesetzt = positiv)
      [10] & 0x7F  = Luftfeuchtigkeit (%)

    Byte-Layout Service Data UUID 0000fd3d-...:
      [0]  & 0x7F  = Device-Typ (0x54 = Meter)
      [2]  & 0x7F  = Batterie (%)

    HINWEIS: Offsets mit echtem Gerät per DEBUG-Log der Roh-Bytes verifizieren.
    """
    mfr = manufacturer_data.get(SWITCHBOT_COMPANY_ID)
    if mfr is None or len(mfr) < 11:
        return None

    temp_decimal = mfr[8] & 0x0F
    temp_integer = mfr[9] & 0x7F
    is_positive = bool(mfr[9] & 0x80)
    temperature = temp_integer + temp_decimal * 0.1
    if not is_positive:
        temperature = -temperature

    humidity = mfr[10] & 0x7F

    battery: int | None = None
    svc = service_data.get(SWITCHBOT_SERVICE_UUID)
    if svc is not None and len(svc) >= 3:
        battery = svc[2] & 0x7F

    return SensorReading(
        mac_address=mac_address,
        temperature=temperature,
        humidity=humidity,
        battery=battery,
        timestamp=datetime.now(),
    )
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_device_parser.py -v
```

Erwartete Ausgabe: `10 passed`

- [ ] **Schritt 5: Commit**

```bash
git add device_parser.py tests/test_device_parser.py
git commit -m "feat: Device-Parser für SwitchBot W3400010 BLE-Advertisements"
```

---

## Task 5: BLE-Scanner + Tests

**Files:**
- Create: `ble_scanner.py`
- Create: `tests/test_ble_scanner.py`

- [ ] **Schritt 1: Failing Tests schreiben**

`tests/test_ble_scanner.py`:

```python
import pytest
from unittest.mock import MagicMock
from ble_scanner import BleScanner
from config_service import AppConfig, DeviceConfig
from device_parser import SWITCHBOT_COMPANY_ID, SWITCHBOT_SERVICE_UUID

MAC_A = "AA:BB:CC:DD:EE:FF"
MAC_B = "11:22:33:44:55:66"

def _make_config(macs: list[str] = None) -> AppConfig:
    macs = macs or [MAC_A]
    return AppConfig(
        devices=[DeviceConfig(name=f"Sensor{i}", mac_address=m) for i, m in enumerate(macs)],
        scan_interval_seconds=300,
        scan_duration_seconds=1,
    )


def _make_mfr_bytes(temp_int: int = 22, temp_dec: int = 3,
                    positive: bool = True, humidity: int = 48) -> bytes:
    data = bytearray(11)
    data[8] = temp_dec & 0x0F
    data[9] = (temp_int & 0x7F) | (0x80 if positive else 0x00)
    data[10] = humidity & 0x7F
    return bytes(data)


def test_get_readings_empty_initially():
    scanner = BleScanner(_make_config())
    assert scanner.get_readings() == {}


def test_get_last_error_none_initially():
    scanner = BleScanner(_make_config())
    assert scanner.get_last_error() is None


def test_callback_ignores_unknown_mac():
    scanner = BleScanner(_make_config([MAC_A]))
    device = MagicMock()
    device.address = MAC_B
    adv = MagicMock()
    adv.manufacturer_data = {SWITCHBOT_COMPANY_ID: _make_mfr_bytes()}
    adv.service_data = {}
    scanner._advertisement_callback(device, adv)
    assert scanner.get_readings() == {}


def test_callback_ignores_invalid_advertisement():
    scanner = BleScanner(_make_config([MAC_A]))
    device = MagicMock()
    device.address = MAC_A
    adv = MagicMock()
    adv.manufacturer_data = {}   # kein SwitchBot-Manufacturer-Eintrag
    adv.service_data = {}
    scanner._advertisement_callback(device, adv)
    assert scanner.get_readings() == {}


def test_callback_stores_valid_reading():
    scanner = BleScanner(_make_config([MAC_A]))
    device = MagicMock()
    device.address = MAC_A
    adv = MagicMock()
    adv.manufacturer_data = {SWITCHBOT_COMPANY_ID: _make_mfr_bytes(22, 3, True, 48)}
    adv.service_data = {}
    scanner._advertisement_callback(device, adv)
    readings = scanner.get_readings()
    assert MAC_A in readings
    assert readings[MAC_A].temperature == pytest.approx(22.3)
    assert readings[MAC_A].humidity == 48


def test_callback_merges_battery_from_previous_reading():
    """Wenn neues Advertisement keine Service-Data hat, Batterie aus Cache übernehmen."""
    from device_parser import SWITCHBOT_SERVICE_UUID
    scanner = BleScanner(_make_config([MAC_A]))
    device = MagicMock()
    device.address = MAC_A

    # Erstes Advertisement: mit Batterie (85 %)
    svc = bytearray(3)
    svc[2] = 85
    adv1 = MagicMock()
    adv1.manufacturer_data = {SWITCHBOT_COMPANY_ID: _make_mfr_bytes(20, 0, True, 50)}
    adv1.service_data = {SWITCHBOT_SERVICE_UUID: bytes(svc)}
    scanner._advertisement_callback(device, adv1)

    # Zweites Advertisement: ohne Service-Data
    adv2 = MagicMock()
    adv2.manufacturer_data = {SWITCHBOT_COMPANY_ID: _make_mfr_bytes(21, 5, True, 52)}
    adv2.service_data = {}
    scanner._advertisement_callback(device, adv2)

    readings = scanner.get_readings()
    assert readings[MAC_A].battery == 85   # aus erstem Reading beibehalten
    assert readings[MAC_A].temperature == pytest.approx(21.5)


def test_get_readings_returns_snapshot_not_reference():
    """Veränderungen am zurückgegebenen Dict dürfen den Cache nicht beeinflussen."""
    scanner = BleScanner(_make_config([MAC_A]))
    device = MagicMock()
    device.address = MAC_A
    adv = MagicMock()
    adv.manufacturer_data = {SWITCHBOT_COMPANY_ID: _make_mfr_bytes()}
    adv.service_data = {}
    scanner._advertisement_callback(device, adv)
    snapshot = scanner.get_readings()
    snapshot.clear()
    assert MAC_A in scanner.get_readings()
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_ble_scanner.py -v
```

Erwartete Ausgabe: `ImportError: No module named 'ble_scanner'`

- [ ] **Schritt 3: ble_scanner.py implementieren**

```python
import asyncio
import dataclasses
import logging
import threading
from collections.abc import Callable

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from config_service import AppConfig
from device_parser import SensorReading, parse

logger = logging.getLogger(__name__)


class BleScanner:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._mac_set = {d.mac_address.upper() for d in config.devices}
        self._cache: dict[str, SensorReading] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._periodic_task: asyncio.Task | None = None
        self._last_error: str | None = None
        self._backoff: float = 1.0

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BLE-Thread")
        self._thread.start()

    def stop(self) -> None:
        if self._loop is None:
            return
        if self._periodic_task is not None:
            self._loop.call_soon_threadsafe(self._periodic_task.cancel)
        self._loop.call_soon_threadsafe(self._loop.stop)

    def trigger_scan(self) -> None:
        if self._loop is None or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self._scan_burst(), self._loop)

    def get_readings(self) -> dict[str, SensorReading]:
        with self._lock:
            return dict(self._cache)

    def get_last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    # --- Internes Threading ---

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self) -> None:
        await self._scan_burst()
        self._periodic_task = asyncio.create_task(self._periodic_scan())
        try:
            await self._periodic_task
        except asyncio.CancelledError:
            pass

    async def _periodic_scan(self) -> None:
        while True:
            await asyncio.sleep(self._config.scan_interval_seconds)
            await self._scan_burst()

    async def _scan_burst(self) -> None:
        logger.info("BLE-Scan gestartet (Dauer: %ds)", self._config.scan_duration_seconds)
        try:
            scanner = BleakScanner(
                detection_callback=self._advertisement_callback,
                scanning_mode="active",
            )
            await scanner.start()
            await asyncio.sleep(self._config.scan_duration_seconds)
            await scanner.stop()
            with self._lock:
                self._last_error = None
            self._backoff = 1.0
            logger.info("BLE-Scan abgeschlossen")
        except Exception as exc:
            error_msg = str(exc)
            with self._lock:
                self._last_error = f"BLE-Fehler: {error_msg}"
            logger.exception("BLE-Scan-Fehler, Retry in %.0fs", self._backoff)
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, 60.0)

    # --- Advertisement-Callback (aus bleak asyncio-Thread) ---

    def _advertisement_callback(self, device: BLEDevice, advertisement: AdvertisementData) -> None:
        mac = device.address.upper()
        if mac not in self._mac_set:
            return
        logger.debug(
            "Advertisement von %s: mfr=%s svc=%s",
            mac,
            dict(advertisement.manufacturer_data),
            dict(advertisement.service_data),
        )
        reading = parse(mac, advertisement.manufacturer_data, advertisement.service_data)
        if reading is None:
            return
        with self._lock:
            existing = self._cache.get(mac)
            if reading.battery is None and existing is not None and existing.battery is not None:
                reading = dataclasses.replace(reading, battery=existing.battery)
            self._cache[mac] = reading
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_ble_scanner.py -v
```

Erwartete Ausgabe: `7 passed`

- [ ] **Schritt 5: Commit**

```bash
git add ble_scanner.py tests/test_ble_scanner.py
git commit -m "feat: BLE-Scanner mit Cache, Lock-Schutz, Backoff und Battery-Merge"
```

---

## Task 6: Popup-Fenster

**Files:**
- Create: `ui/popup_window.py`

- [ ] **Schritt 1: ui/popup_window.py schreiben**

```python
import tkinter as tk
from datetime import datetime

from config_service import DeviceConfig
from device_parser import SensorReading

BG = "#2b2b2b"
FG_TITLE = "#ffffff"
FG_LABEL = "#aaaaaa"
FG_VALUE = "#ffffff"
FG_BATTERY = "#777777"
FG_NODATA = "#555555"
FG_ERROR = "#e74c3c"
FG_FOOTER = "#666666"
SEPARATOR = "#444444"


class PopupWindow:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._window: tk.Toplevel | None = None

    def show(
        self,
        devices: list[DeviceConfig],
        readings: dict[str, SensorReading],
        error: str | None = None,
    ) -> None:
        """Zeigt das Popup. Muss im Main-Thread aufgerufen werden."""
        if self._window is not None:
            self._window.destroy()
            self._window = None

        win = tk.Toplevel(self._root)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)

        # Titelzeile
        tk.Label(
            win, text="🌡 SwitchBot Wetter",
            bg=BG, fg=FG_TITLE, font=("Segoe UI", 11, "bold"),
            padx=14, pady=10,
        ).pack(fill=tk.X)
        tk.Frame(win, bg=SEPARATOR, height=1).pack(fill=tk.X)

        if error and not readings:
            tk.Label(
                win, text=error,
                bg=BG, fg=FG_ERROR, font=("Segoe UI", 9),
                padx=14, pady=10, wraplength=260,
            ).pack(fill=tk.X)
        else:
            for device in devices:
                mac = device.mac_address.upper()
                reading = readings.get(mac)
                frame = tk.Frame(win, bg=BG, padx=14, pady=8)
                frame.pack(fill=tk.X)
                tk.Label(
                    frame, text=device.name,
                    bg=BG, fg=FG_LABEL, font=("Segoe UI", 9),
                ).pack(anchor=tk.W)
                if reading is not None:
                    temp_str = f"{reading.temperature:.1f} °C  •  {reading.humidity} %"
                    tk.Label(
                        frame, text=temp_str,
                        bg=BG, fg=FG_VALUE, font=("Segoe UI", 14, "bold"),
                    ).pack(anchor=tk.W)
                    if reading.battery is not None:
                        tk.Label(
                            frame, text=f"Batterie: {reading.battery} %",
                            bg=BG, fg=FG_BATTERY, font=("Segoe UI", 8),
                        ).pack(anchor=tk.W)
                else:
                    tk.Label(
                        frame, text="— keine Daten —",
                        bg=BG, fg=FG_NODATA, font=("Segoe UI", 10),
                    ).pack(anchor=tk.W)

        # Fußzeile
        tk.Frame(win, bg=SEPARATOR, height=1).pack(fill=tk.X)
        last_ts = max((r.timestamp for r in readings.values()), default=None)
        if last_ts:
            ts_text = f"Aktualisiert: {last_ts.strftime('%H:%M:%S')}"
        else:
            ts_text = "Noch nicht aktualisiert"
        tk.Label(
            win, text=ts_text,
            bg=BG, fg=FG_FOOTER, font=("Segoe UI", 8),
            padx=14, pady=6,
        ).pack(fill=tk.X)

        # Positionieren: rechts unten
        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = sw - w - 14
        y = sh - h - 50
        win.geometry(f"{w}x{h}+{x}+{y}")

        # Schließen bei Klick außerhalb
        win.focus_force()
        win.grab_set()
        win.bind("<Button-1>", lambda e: self._on_click(win, e))

        self._window = win

    def close(self) -> None:
        """Schließt das Popup. Muss im Main-Thread aufgerufen werden."""
        if self._window is not None:
            try:
                self._window.grab_release()
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None

    def _on_click(self, win: tk.Toplevel, event: tk.Event) -> None:
        wx = win.winfo_rootx()
        wy = win.winfo_rooty()
        ww = win.winfo_width()
        wh = win.winfo_height()
        if not (wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh):
            self.close()
```

- [ ] **Schritt 2: Manuell prüfen (optionaler Smoke-Test)**

```python
# In Python-REPL (nur für manuelle Prüfung):
import tkinter as tk
from datetime import datetime
from ui.popup_window import PopupWindow
from config_service import DeviceConfig
from device_parser import SensorReading

root = tk.Tk()
root.withdraw()
popup = PopupWindow(root)

devices = [DeviceConfig("Wohnzimmer", "AA:BB:CC:DD:EE:FF")]
readings = {
    "AA:BB:CC:DD:EE:FF": SensorReading("AA:BB:CC:DD:EE:FF", 22.3, 48, 85, datetime.now())
}
popup.show(devices, readings)
root.mainloop()
# Prüfen: Popup erscheint rechts unten, Klick außerhalb schließt es
```

- [ ] **Schritt 3: Commit**

```bash
git add ui/popup_window.py
git commit -m "feat: Popup-Fenster mit Dark-Theme, Sensor-Anzeige, Close-on-Outside-Click"
```

---

## Task 7: Hauptprogramm (Verdrahtung)

**Files:**
- Create: `main.py`

- [ ] **Schritt 1: main.py schreiben**

```python
import logging
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pystray
from PIL import Image, ImageDraw

from ble_scanner import BleScanner
from config_service import ConfigError, load_config
from log_service import setup_logging
from ui.popup_window import PopupWindow

logger = logging.getLogger(__name__)


def _create_tray_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([16, 42, 48, 64], fill=(231, 76, 60, 255))
    draw.rectangle([25, 6, 39, 52], fill=(180, 180, 180, 255))
    draw.rectangle([27, 8, 37, 52], fill=(231, 76, 60, 255))
    for mark_y in [16, 24, 32, 40]:
        draw.line([35, mark_y, 40, mark_y], fill=(100, 100, 100, 255), width=2)
    return img


def main() -> None:
    setup_logging(debug="--debug" in sys.argv)

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Konfigurationsfehler: %s", exc)
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("SwitchBot Wetter — Konfigurationsfehler", str(exc))
        root.destroy()
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()
    root.title("SwitchBot Wetter")

    scanner = BleScanner(config)
    popup = PopupWindow(root)

    # --- Tray-Callbacks (laufen im pystray-Thread) ---

    def _show_popup() -> None:
        readings = scanner.get_readings()
        error = scanner.get_last_error()
        root.after(0, lambda: popup.show(config.devices, readings, error))

    def on_left_click(icon: pystray.Icon, item: object = None) -> None:
        scanner.trigger_scan()
        _show_popup()

    def on_refresh(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        scanner.trigger_scan()

    def on_settings(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        config_path = Path("config.json").resolve()
        os.startfile(str(config_path))

    def on_show_log(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        log_path = Path("switchbot_wetter.log").resolve()
        if log_path.exists():
            os.startfile(str(log_path))
        else:
            root.after(0, lambda: messagebox.showinfo(
                "SwitchBot Wetter", "Noch keine Logdatei vorhanden."
            ))

    def on_quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Beenden...")
        scanner.stop()
        icon.stop()
        root.after(0, root.quit)

    # --- Tray-Icon aufbauen ---

    menu = pystray.Menu(
        pystray.MenuItem("Aktualisieren", on_refresh),
        pystray.MenuItem("Einstellungen öffnen", on_settings),
        pystray.MenuItem("Log anzeigen", on_show_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Beenden", on_quit),
    )

    icon = pystray.Icon(
        name="switchbot_wetter",
        icon=_create_tray_icon_image(),
        title="SwitchBot Wetter",
        menu=menu,
    )
    icon.on_activate = on_left_click

    # --- Threads starten ---

    scanner.start()

    tray_thread = threading.Thread(target=icon.run, daemon=True, name="pystray-Thread")
    tray_thread.start()

    logger.info("SwitchBot Wetter gestartet — %d Geräte konfiguriert", len(config.devices))

    # Main-Thread: tkinter-Event-Loop
    root.mainloop()

    logger.info("SwitchBot Wetter beendet")


if __name__ == "__main__":
    main()
```

- [ ] **Schritt 2: Commit**

```bash
git add main.py
git commit -m "feat: Hauptprogramm — Threading-Verdrahtung, Tray-Icon, Shutdown-Sequenz"
```

---

## Task 8: Gesamt-Test + Smoke-Test

**Files:** keine neuen Dateien

- [ ] **Schritt 1: Alle Unit-Tests ausführen**

```bash
pytest -v
```

Erwartete Ausgabe: `23 passed` (oder mehr). Kein Fehler.

- [ ] **Schritt 2: App starten**

```bash
python main.py
```

Erwartete Ausgabe:
- Kein sichtbares Fenster erscheint.
- Im Windows-Infobereich (rechts neben der Uhr) erscheint ein rotes Thermometer-Icon.
- In `switchbot_wetter.log` erscheint: `SwitchBot Wetter gestartet — 2 Geräte konfiguriert`
- Danach: `BLE-Scan gestartet (Dauer: 10s)`

- [ ] **Schritt 3: Linksklick auf Tray-Icon testen**

Erwartete Ausgabe:
- Popup erscheint rechts unten neben der Uhr.
- Geräte-Namen aus config.json werden angezeigt.
- Solange keine echten Sensoren in Reichweite: "— keine Daten —"
- Klick außerhalb schließt das Popup.

- [ ] **Schritt 4: Rechtsklick-Menü testen**

- "Aktualisieren" → Scan wird getriggert (Log-Eintrag sichtbar)
- "Einstellungen öffnen" → config.json öffnet in Notepad
- "Log anzeigen" → switchbot_wetter.log öffnet in Texteditor
- "Beenden" → App beendet sich sauber (kein hängender Prozess)

- [ ] **Schritt 5: Mit echtem Sensor testen**

Konfiguriere die echte MAC-Adresse des SwitchBot-Sensors in `config.json`.
MAC-Adresse ermitteln: SwitchBot-App → Gerät → Details, oder mit BLE-Scanner-App.

```bash
python main.py --debug
```

Prüfe `switchbot_wetter.log` auf DEBUG-Einträge:
```
DEBUG ble_scanner — Advertisement von AA:BB:CC:DD:EE:FF: mfr={...} svc={...}
```

Falls keine Daten ankommen:
1. Sicherstellen dass Windows BT eingeschaltet ist.
2. MAC-Adresse in config.json prüfen (Groß-/Kleinschreibung irrelevant, wird zu Upper normalisiert).
3. Sensor muss in BLE-Reichweite sein (~10 m ohne Hindernisse).
4. Byte-Offsets im Log prüfen und ggf. `device_parser.py` korrigieren (Hinweis in Spec).

- [ ] **Schritt 6: Finaler Commit**

```bash
git add .
git commit -m "docs: Implementierung abgeschlossen — alle Tests grün, Smoke-Test bestanden"
```

---

## Hinweise

### Python-Version
Python 3.10+ erforderlich (Union-Typ-Syntax `int | None`, `match`-Statement nicht verwendet aber `|`-Syntax in Dataclass-Feldern).

### BLE-Adapter
Ein Bluetooth-Adapter mit BLE-Support (Bluetooth 4.0+) ist erforderlich. Die meisten PCs mit Windows 10/11 haben einen eingebauten Adapter der dies unterstützt. Prüfen: Geräte-Manager → Bluetooth.

### Byte-Offsets verifizieren
Das SwitchBot-Protokoll variiert leicht zwischen Geräte-Revisionen. Mit `--debug` starten, die Roh-Bytes im Log prüfen und ggf. die Indizes in `device_parser.py` anpassen. Die RSSI-Werte und Advertisement-Strukturen sind im SwitchBot BLE Open API Dokument dokumentiert.

### Autostart (optional, nicht im Scope)
Windows-Aufgabenplaner: Neuer Task → Trigger "Bei Anmeldung" → Aktion `python C:\Pfad\main.py` → "Nur ausführen wenn Benutzer angemeldet ist".
