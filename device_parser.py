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
