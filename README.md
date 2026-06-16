# SwitchBot Wetter

Windows-Tray-Anwendung zum Auslesen von SwitchBot Outdoor Meter / Hygrometer-Sensoren per Bluetooth Low Energy (BLE) — ohne Hub, ohne Cloud, ohne Pairing.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue) ![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- Liest bis zu 3 (oder mehr) SwitchBot Outdoor Meter passiv per BLE aus
- Kein SwitchBot Hub, kein Cloud-Account, kein Bluetooth-Pairing nötig
- Minimiert im Windows-Infobereich (System Tray)
- Hover über das Tray-Icon zeigt aktuelle Temperatur und Luftfeuchtigkeit aller Sensoren
- Klick auf das Tray-Icon öffnet/schließt ein Popup mit allen Messwerten
- Automatische Aktualisierung alle 5 Minuten
- Konfiguration per einfacher JSON-Datei

---

## Voraussetzungen

- Windows 10 / 11
- Python 3.10 oder neuer
- Bluetooth-Adapter mit BLE-Support (Bluetooth 4.0+)
- SwitchBot Outdoor Meter (Modell W3400010)

---

## Installation

```bash
git clone https://github.com/nomak1980-alt/SwitchbotWetter.git
cd SwitchbotWetter
pip install -r requirements.txt
```

---

## Konfiguration

`config.json` im Projektverzeichnis bearbeiten:

```json
{
  "devices": [
    {"name": "Wohnzimmer", "macAddress": "AA:BB:CC:DD:EE:FF"},
    {"name": "Terrasse",   "macAddress": "11:22:33:44:55:66"},
    {"name": "Keller",     "macAddress": "22:33:44:55:66:77"}
  ],
  "scan_interval_seconds": 300,
  "scan_duration_seconds": 10
}
```

**MAC-Adresse ermitteln:** SwitchBot-App → Gerät auswählen → Einstellungen → Geräteinformationen, oder mit einer BLE-Scanner-App wie [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile).

Fehlt `config.json` beim Start, wird automatisch eine Beispieldatei angelegt.

---

## Starten

**Manuell (Doppelklick):**
```
start.vbs
```
Startet die App ohne sichtbares Fenster. Das Thermometer-Icon erscheint im Infobereich rechts neben der Uhr.

**Per Kommandozeile:**
```bash
python main.py
# oder mit Debug-Logging:
python main.py --debug
```

**Autostart bei Windows-Anmeldung:**
1. `Win + R` → `shell:startup` → Enter
2. `start.vbs` in den geöffneten Ordner kopieren (oder Verknüpfung erstellen)

---

## Bedienung

| Aktion | Ergebnis |
|--------|----------|
| Maus über Tray-Icon halten | Tooltip mit allen aktuellen Messwerten |
| Linksklick auf Tray-Icon | Popup öffnen / schließen |
| ✕ im Popup | Popup schließen |
| Rechtsklick → Anzeigen | Popup öffnen |
| Rechtsklick → Aktualisieren | Config neu laden + sofortiger BLE-Scan |
| Rechtsklick → Einstellungen öffnen | `config.json` im Editor öffnen |
| Rechtsklick → Log anzeigen | `switchbot_wetter.log` öffnen |
| Rechtsklick → Beenden | App beenden |

---

## Popup

```
┌─────────────────────────────┐
│  🌡 SwitchBot Wetter      ✕ │
├─────────────────────────────┤
│  Außen Hinten               │
│  18,1 °C  •  65 %          │
│  Batterie: 85 %             │
│                             │
│  Außen Vorne                │
│  17,8 °C  •  68 %          │
│                             │
│  Büro                       │
│  22,3 °C  •  48 %          │
├─────────────────────────────┤
│  Aktualisiert: 14:32:07     │
└─────────────────────────────┘
```

---

## Projektstruktur

```
SwitchbotWetter/
├── main.py              # Einstiegspunkt, Threading-Verdrahtung, Tray-Icon
├── ble_scanner.py       # BLE-Scanning via bleak (passiv, kein Pairing)
├── device_parser.py     # BLE-Advertisement-Bytes → Messwerte (plattformunabhängig)
├── config_service.py    # config.json lesen
├── log_service.py       # Logging-Setup
├── ui/
│   └── popup_window.py  # Popup-Fenster (tkinter)
├── tests/
│   ├── test_ble_scanner.py
│   ├── test_config_service.py
│   └── test_device_parser.py
├── config.json          # Gerätekonfiguration
├── start.vbs            # Starter ohne CMD-Fenster
└── requirements.txt
```

---

## BLE-Protokoll

Die SwitchBot Outdoor Meter senden Messwerte als unverschlüsselte BLE-Advertisements. Die App empfängt diese passiv — kein Verbindungsaufbau, kein Pairing nötig.

**Manufacturer Data (Company ID `0x0969`):**
| Byte | Bits | Bedeutung |
|------|------|-----------|
| 8 | `& 0x0F` | Temperatur Dezimal (× 0,1) |
| 9 | `& 0x7F` | Temperatur Integer (°C) |
| 9 | `& 0x80` | Vorzeichen (gesetzt = positiv) |
| 10 | `& 0x7F` | Luftfeuchtigkeit (%) |

**Service Data (UUID `0000fd3d-...`):**
| Byte | Bits | Bedeutung |
|------|------|-----------|
| 2 | `& 0x7F` | Batterie (%) |

> **Hinweis:** Die Byte-Offsets können je nach Firmware-Version variieren. Mit `python main.py --debug` werden Roh-Bytes ins Log geschrieben, anhand derer die Offsets geprüft werden können.

---

## Threading-Modell

```
Main-Thread          pystray-Thread       BLE-Thread (asyncio)
(tkinter mainloop)   (icon.run)           (bleak BleakScanner)
        │                   │                      │
        │◄──root.after()────┤                      │
        │                   │         Lock-geschützter Cache
        │◄──────────────────┼──────────────────────┤
        │                   │    trigger_scan via   │
        │                   │──run_coroutine_──────►│
        │                   │   threadsafe()        │
```

Alle tkinter-Zugriffe aus dem pystray-Thread laufen über `root.after(0, ...)`.

---

## Tests

```bash
pytest -v
```

24 Unit-Tests für Parser, Config-Service und Scanner-Logik. BLE-Hardware nicht erforderlich.

---

## Portierbarkeit (LilyGo T5 4,7" / MicroPython)

`device_parser.py` ist bewusst plattformunabhängig gehalten — keine bleak- oder Windows-Imports. Die Parsing-Logik ist direkt auf MicroPython übertragbar. Der BLE-Teil wird auf dem ESP32 durch das eingebaute `bluetooth`-Modul ersetzt (`IRQ_SCAN_RESULT`-Callback liefert dieselben Roh-Bytes).

---

## Logging

Logdatei: `switchbot_wetter.log` im Programmverzeichnis (max. 1 MB, 3 Backups).

```
2026-06-16 14:32:01,123 INFO     __main__ — SwitchBot Wetter gestartet — 3 Geräte konfiguriert
2026-06-16 14:32:01,124 INFO     ble_scanner — BLE-Scan gestartet (Dauer: 10s)
2026-06-16 14:32:11,456 INFO     ble_scanner — BLE-Scan abgeschlossen
```

---

## Abhängigkeiten

| Paket | Zweck |
|-------|-------|
| `bleak` | BLE-Scanning unter Windows (WinRT-Backend) |
| `pystray` | System-Tray-Icon |
| `Pillow` | Programmatisches Tray-Icon (Thermometer) |
| `pytest` | Tests |

`tkinter` ist Teil der Python-Standardbibliothek.
