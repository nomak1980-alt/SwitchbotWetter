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
