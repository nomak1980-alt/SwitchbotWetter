# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Tests ausführen
pytest -v

# Einzelnen Test ausführen
pytest tests/test_device_parser.py::test_parses_positive_temperature_and_humidity -v

# App starten (mit Debug-Logging)
python main.py --debug

# App starten (ohne CMD-Fenster, wie Endnutzer)
wscript start.vbs

# Syntax prüfen
python -m py_compile main.py
```

## Architektur

**Drei Threads** — strikte Trennung, nie vermischen:

| Thread | Verantwortlich für |
|--------|-------------------|
| Main-Thread | `tk.Tk()` + `root.mainloop()` — alle tkinter-Widgets |
| pystray-Thread (Daemon) | `icon.run()` — Tray-Callbacks |
| BLE-Thread (Daemon) | eigener `asyncio`-Loop für bleak |

**Goldene Regeln:**
- Tray-Callbacks → tkinter immer via `root.after(0, ...)`, nie direkt
- Manueller Scan-Trigger → `asyncio.run_coroutine_threadsafe()` in den BLE-Loop
- `BleScanner._cache` → immer unter `threading.Lock` lesen/schreiben
- `BleScanner.get_readings()` gibt `dict(self._cache)` zurück (Kopie, nicht Referenz)
- Shutdown-Reihenfolge: `scanner.stop()` → `icon.stop()` → `root.after(0, root.quit)` — andere Reihenfolge ergibt hängenden Prozess

## Modulverantwortlichkeiten

**`device_parser.py`** — plattformunabhängig, keine bleak-Imports. Erhält nur `dict[int, bytes]` (Manufacturer Data) und `dict[str, bytes]` (Service Data). Direkt auf MicroPython portierbar für LilyGo T5 4,7" (ESP32). Byte-Offsets für SwitchBot W3400010:
- Manufacturer Data Company ID `0x0969`: `[8]&0x0F` = Temp-Dezimal, `[9]&0x7F` = Temp-Int, `[9]&0x80` = Vorzeichen, `[10]&0x7F` = Humidity
- Service Data UUID `0000fd3d-...`: `[2]&0x7F` = Batterie

**`ble_scanner.py`** — besitzt den asyncio-Loop und `threading.Event` (`_loop_ready`) damit `stop()` nicht vor Loop-Start feuert. `_advertisement_callback` läuft im asyncio-Thread; schreibt in Cache unter Lock. Battery-Merge: fehlt Service Data in neuem Advertisement, wird Batterie aus vorherigem Cache-Eintrag übernommen (`dataclasses.replace`). `set_update_callback()` wird nach jedem Cache-Update aufgerufen (für Tooltip-Updates).
- **Zwei Scan-Modi** (`config.scan_mode`): `"continuous"` (PC-Default) → `_continuous_scan()` hält den Scanner dauerhaft an und startet ihn nur alle `scan_interval_seconds` kurz neu (gegen WinRT-„Einschlafen"); maximale Empfangschance für schwache/entfernte Sensoren. `"interval"` → `_scan_burst()` + `_periodic_scan()`: sparsamer Burst (`scan_duration_seconds` lang) je `scan_interval_seconds`, dazwischen Funk aus — das Muster für die geplante ESP32-Portierung (Deep-Sleep).
- `_advertisement_callback` loggt `advertisement.rssi` (Signalstärke in dBm) auf DEBUG — nur sichtbar mit `--debug`, nicht über `start.vbs`. Diagnose für „weit entfernte Sensoren kommen nicht an".

**`main.py`** — `active_config = [config]` ist ein List-Wrapper damit `on_refresh` die Config-Referenz ersetzen kann ohne Closure-Probleme. `icon_ref = [icon]` analog für den Tooltip-Callback. `APP_DIR = Path(__file__).parent` — alle Pfade (config.json, log) relativ zum Skriptverzeichnis, nicht zum CWD.

**`ui/popup_window.py`** — `show()`, `update_data()` und `close()` dürfen nur im Main-Thread aufgerufen werden. `is_open()` ist thread-safe (liest nur `_window is not None`). Kein `grab_set()` — Popup bleibt offen bis ✕ oder erneuter Tray-Klick.
- `show()` baut das Fenster neu auf und speichert Label-Referenzen in `_device_labels` (MAC → `{temp, info}`) sowie die Menge `_macs_with_data`.
- `update_data()` aktualisiert Labels in-place ohne Fenster-Neuaufbau (kein Flicker). Einzige Ausnahme: ändert sich `_macs_with_data` (Sensor erstmals empfangen), ruft es `show()` auf.
- Jeder Sensor zeigt Batterie + Timestamp in einer Zeile (`_info_text()`). Es gibt keinen globalen Footer-Timestamp mehr.
- `_on_scanner_update()` in `main.py` ruft nach jedem BLE-Cache-Update sowohl `_update_tooltip()` als auch (wenn Popup offen) `popup.update_data()` via `root.after(0, ...)` auf — so aktualisiert sich das Panel live.

## BLE-Hinweis

`scanning_mode="active"` läuft auf WinRT fehlerfrei (2026-06-20 empirisch verifiziert), bringt hier aber nichts: SwitchBot liefert Temp+Batterie bereits im passiven Advertisement, und Sensoren die gerade nicht broadcasten reagieren auch auf aktiven Scan nicht (active vs. passive = identisch). Passiv lassen. Kein `service_uuids`-Filter setzen: WinRT liefert sonst nur Advertisement *oder* Scan-Response, nicht beides (Temp und Batterie wären in verschiedenen Paketen).

## Konfiguration zur Laufzeit ändern

`on_refresh` in `main.py` lädt `config.json` neu und ruft `scanner.reload_config()` auf — MACs werden dadurch ohne Neustart übernommen.
