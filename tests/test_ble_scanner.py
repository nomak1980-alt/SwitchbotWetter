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
