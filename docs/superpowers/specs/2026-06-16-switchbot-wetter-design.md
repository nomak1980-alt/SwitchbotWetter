# SwitchBot Wetter — Design-Spezifikation

**Datum:** 2026-06-16  
**Status:** Überarbeitet (BLE-Protokoll + Threading-Modell korrigiert)

---

## Übersicht

Windows-Tray-Anwendung in Python, die bis zu 3 SwitchBot Outdoor Meter/Hygrometer per Bluetooth Low Energy (BLE) passiv ausliest und die Messwerte im System-Tray anzeigt. Kein SwitchBot Hub, kein Cloud-Zugriff — reine lokale BLE-Auslesung.

Spätere Portierbarkeit auf LilyGo T5 4.7" (ESP32/MicroPython) ist architektonisch berücksichtigt: der BLE-Parser ist als eigenständiges, plattformunabhängiges Modul implementiert.

---

## Projektstruktur

```
SwitchbotWetter/
├── main.py                  # Einstiegspunkt, Tray-Setup, DI-Verdrahtung
├── ble_scanner.py           # BLE-Scanning via bleak (passiv, kein Connect)
├── device_parser.py         # SwitchBot Advertisement-Bytes → Messwerte
├── config_service.py        # config.json lesen
├── log_service.py           # Logging-Setup
├── ui/
│   └── popup_window.py      # tkinter Toplevel Popup
├── assets/
│   ├── thermometer_16.png
│   └── thermometer_32.png
├── config.json
├── requirements.txt
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-16-switchbot-wetter-design.md
```

---

## Komponenten

### `main.py`
- Initialisiert Logging, Config, BLE-Scanner
- **Threading-Modell (kritisch — siehe Abschnitt „Nebenläufigkeit"):**
  - **Main-Thread:** verstecktes `tkinter.Tk()`-Root + `root.mainloop()`. tkinter ist nicht thread-safe und muss im Main-Thread laufen.
  - **pystray-Thread (Daemon):** `threading.Thread(target=icon.run)`. Tray-Callbacks marshallen alle UI-Aktionen via `root.after(0, ...)` in den Main-Thread.
  - **BLE-Thread (Daemon):** eigener `asyncio`-Event-Loop (`asyncio.new_event_loop()` + `run_forever()`) für bleak.
- Verdrahtet die Cross-Thread-Übergänge (Lock für Cache, `run_coroutine_threadsafe` für Scan-Trigger, `root.after` für UI-Updates)

### `ble_scanner.py`
- Verwendet `bleak.BleakScanner` (kein Pairing, kein Connect)
- **Windows/WinRT-Besonderheit (kritisch):**
  - Passiver Modus (`scanning_mode="passive"`) erfordert auf WinRT zwingend `bleak`-`BleakScanner(..., bluez=..., or_patterns=...)` bzw. einen Advertisement-Filter — ohne Pattern wirft das WinRT-Backend einen Fehler. Daher: entweder passiver Modus **mit** `or_patterns` (Filter auf SwitchBot Manufacturer ID `0x0969` / Service UUID `0xFD3D`), oder als robuste Variante **aktiver Modus** (`scanning_mode="active"`) und MAC-Filterung nach Empfang.
  - **Kein `service_uuids`-Filter setzen:** WinRT liefert mit UUID-Filter nur Advertisement *oder* Scan-Response — wir brauchen aber beide (Temp/Humidity in Manufacturer Data, Batterie in Service Data der Scan-Response). Filterlos empfangen und selbst nach MAC matchen.
- Führt Scan-Bursts durch (konfigurierbare Dauer, Standard 10 s)
- Filtert empfangene Advertisements nach MAC-Adressen aus der Config
- Übergibt pro Treffer **beide** Datenquellen (`advertisement_data.manufacturer_data` und `advertisement_data.service_data`) an `device_parser.parse()`
- Hält In-Memory-Cache: `dict[mac_address → SensorReading]`, Zugriff über `threading.Lock` geschützt (Schreiben aus BLE-Thread, Lesen aus Main-Thread)
- Manueller Scan-Trigger ("Aktualisieren") wird via `asyncio.run_coroutine_threadsafe()` in den BLE-Loop gepostet
- Exponentielles Backoff bei Adapter-Fehlern

### `device_parser.py`
- Zustandslos, reine Funktion: `parse(manufacturer_data: dict[int, bytes], service_data: dict[str, bytes]) → SensorReading | None`
- **SwitchBot Outdoor Meter (W3400010) — korrektes Advertisement-Layout.** Die Werte sind auf **zwei** AD-Strukturen verteilt, nicht in einem zusammenhängenden Block:

  **Manufacturer Data — Company ID `0x0969`** (Temperatur + Luftfeuchtigkeit):
  ```
  byte[8]  & 0x0F   : Temperatur Dezimal-Anteil (× 0.1)
  byte[9]  & 0x7F   : Temperatur Integer (°C)
  byte[9]  & 0x80   : Vorzeichen-Bit (gesetzt = positiv)
  byte[10] & 0x7F   : Luftfeuchtigkeit (%)
  ```
  (Indizes sind die Offsets innerhalb des Manufacturer-Data-Byte-Arrays; Company-ID-Bytes werden von bleak bereits abgetrennt.)

  **Service Data — UUID `0000fd3d-0000-1000-8000-00805f9b34fb`** (Batterie + Device-Typ):
  ```
  byte[0]  & 0x7F   : Device-Typ (0x54 = Meter/Thermometer)
  byte[2]  & 0x7F   : Batterie (%)
  ```
- Gibt `None` zurück, wenn Manufacturer ID `0x0969` oder die SwitchBot-Service-UUID fehlt (kein passendes Gerät).
- **Hinweis:** Das frühere Layout (Service UUID `0x181A`, alle Felder Byte 0–5) war falsch und ist hiermit ersetzt. Offsets vor Implementierung mit echtem Gerät verifizieren (DEBUG-Log der Roh-Bytes).
- Plattformunabhängig — keine Windows- oder bleak-Abhängigkeit (erhält reine `dict`/`bytes`)

### `config_service.py`
- Liest `config.json` beim Start
- Gibt Liste von `DeviceConfig(name, mac_address)` zurück
- Wirft `ConfigError` bei fehlender/ungültiger Datei

### `log_service.py`
- Konfiguriert Python `logging`
- `RotatingFileHandler`: `switchbot_wetter.log`, max 1 MB, 3 Backups
- DEBUG-Level für BLE-Parsing, INFO für Scan-Events, ERROR für Fehler

### `ui/popup_window.py`
- `tkinter.Toplevel`-Fenster ohne Taskbar-Eintrag (`wm_overrideredirect(True)`)
- Wird **nur im Main-Thread** erzeugt/aktualisiert (Aufruf aus Tray-Callback via `root.after(0, ...)`)
- Positioniert sich automatisch neben dem Tray-Icon (rechts unten)
- Zeigt pro Sensor: Name, Temperatur, Luftfeuchtigkeit, Batterie (optional)
- Zeigt Timestamp der letzten Aktualisierung
- **„Klick außerhalb schließt Popup"** (kritisch): Ein `overrideredirect`-Fenster erhält unter Windows keinen regulären Fokus, daher feuert `<FocusOut>` nicht zuverlässig. Lösung: nach Anzeige `focus_force()`, dann globaler Grab (`grab_set()`/`grab_global`) und ein `<Button>`-Binding, das prüft, ob der Klick außerhalb der Fenstergrenzen liegt → dann schließen. Alternativ Schließen via Fokuswechsel des Tray-Icons.

---

## Nebenläufigkeit (Threading-Modell)

Drei Komponenten mit eigenem Loop/Blocking-Verhalten müssen sauber getrennt werden:

| Thread | Aufgabe | Begründung |
|--------|---------|------------|
| **Main-Thread** | `tk.Tk()` (versteckt) + `root.mainloop()` | tkinter ist nicht thread-safe, Widgets nur im Erzeuger-Thread |
| **pystray-Thread** (Daemon) | `icon.run()` | blockiert — darf nicht den Main-Thread belegen |
| **BLE-Thread** (Daemon) | eigener asyncio-Loop für bleak | bleak ist asyncio-basiert |

**Cross-Thread-Regeln (verbindlich):**
- Tray-Callbacks (pystray-Thread) → UI immer via `root.after(0, callback)` an den Main-Thread reichen. Nie direkt tkinter-Widgets aus dem Callback-Thread anfassen.
- Manueller Scan-Trigger → `asyncio.run_coroutine_threadsafe(scan_coro, ble_loop)`.
- Mess-Cache `dict[mac → SensorReading]` mit `threading.Lock` schützen (Schreiben BLE-Thread, Lesen Main-Thread). Alternativ: Snapshot per `queue.Queue` an den Main-Thread übergeben.

**Shutdown-Reihenfolge** ("Beenden"):
1. BLE-Scan-Loop stoppen (`loop.call_soon_threadsafe(loop.stop)`, Tasks canceln)
2. `icon.stop()` (pystray)
3. `root.quit()` / `root.destroy()` (Main-Thread)

Falsche Reihenfolge → hängender Prozess / Zombie.

---

## Datenfluss

```
Windows BT-Adapter
  → BleakScanner (Advertisement-Empfang, filterlos, MAC-Match)
    → device_parser.parse(manufacturer_data[0x0969], service_data[0xFD3D])
        → SensorReading(temp, humidity, battery, timestamp)
      → In-Memory-Cache [mac → SensorReading]   (Lock-geschützt)
        ↑                                          │
        └── BLE-Thread (asyncio, alle 300 s Burst) │ Lesen
        └── Manuell: run_coroutine_threadsafe()    │ (Main-Thread)
                                                    ▼
          Tray-Callback → root.after(0) → popup_window zeigt Cache an
```

---

## Konfiguration

**config.json:**
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

"Einstellungen öffnen" im Kontextmenü öffnet `config.json` im Standard-Editor (Notepad). Kein separates Einstellungs-UI.

---

## UI-Design

**Tray-Icon:**
- Thermometer-Icon (16×16 / 32×32 PNG)
- Tooltip: erste Sensor-Kurzinfo oder "Keine Daten"

**Popup (Linksklick):**
```
┌─────────────────────────┐
│  🌡 SwitchBot Wetter    │
├─────────────────────────┤
│  Wohnzimmer             │
│  22,3 °C  •  48 %      │
│                         │
│  Terrasse               │
│  18,1 °C  •  61 %      │
├─────────────────────────┤
│  Aktualisiert: 14:32    │
└─────────────────────────┘
```

**Kontextmenü (Rechtsklick):**
- Aktualisieren
- Einstellungen öffnen
- Log anzeigen
- Beenden

---

## Fehlerbehandlung

| Fehler | Verhalten |
|--------|-----------|
| Kein BT-Adapter | Popup zeigt Fehlermeldung, Log-Eintrag |
| Gerät nicht gefunden | Letzte bekannte Werte + Timestamp anzeigen |
| config.json fehlt | Fehlermeldung beim Start + Beispiel-Config anlegen |
| Adapter-Fehler | Exponentielles Backoff, erneuter Versuch |
| WinRT passiver Scan ohne `or_patterns` | Fehler abfangen → Fallback auf aktiven Scan, Log-Warnung |
| Unvollständiges Advertisement (nur Manuf. ODER Service Data) | Teilwerte cachen, fehlende Felder aus letztem Reading übernehmen |

---

## Abhängigkeiten

**requirements.txt:**
```
bleak>=0.21.0
pystray>=0.19.0
Pillow>=10.0.0
```

`tkinter` ist Python-Standardbibliothek (kein separates Paket nötig).

---

## Portierbarkeit (LilyGo T5 4.7" / MicroPython)

`device_parser.py` ist bewusst ohne Python-spezifische Imports geschrieben und erhält nur `dict`/`bytes` (Manufacturer + Service Data). Die Parsing-Logik ist direkt auf MicroPython übertragbar. Der BLE-Teil wird auf dem ESP32 durch das eingebaute `bluetooth`-Modul (passive Scan-Callbacks) ersetzt — dort liefert der `IRQ_SCAN_RESULT`-Callback die rohen Adv-Bytes, aus denen Manufacturer Data (`0x0969`) und Service Data (`0xFD3D`) gemäß demselben Offset-Schema extrahiert werden.

---

## Out of Scope

- Autostart bei Windows-Anmeldung (kann manuell über Aufgabenplaner eingerichtet werden)
- Historisierung / Datenbank
- SwitchBot Cloud API
- Einstellungs-UI (config.json direkt editieren)
