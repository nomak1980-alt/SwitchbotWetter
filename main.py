import logging
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

APP_DIR = Path(__file__).parent

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
    setup_logging(log_path=APP_DIR / "switchbot_wetter.log", debug="--debug" in sys.argv)

    root = tk.Tk()
    root.withdraw()
    root.title("SwitchBot Wetter")

    try:
        config = load_config(APP_DIR / "config.json")
    except ConfigError as exc:
        logger.error("Konfigurationsfehler: %s", exc)
        messagebox.showerror("SwitchBot Wetter — Konfigurationsfehler", str(exc))
        root.destroy()
        sys.exit(1)

    scanner = BleScanner(config)
    popup = PopupWindow(root)

    # Mutable Referenz damit on_refresh die Config neu laden kann
    active_config = [config]

    # --- Tray-Callbacks (laufen im pystray-Thread) ---

    def _show_popup() -> None:
        readings = scanner.get_readings()
        error = scanner.get_last_error()
        devices = active_config[0].devices
        root.after(0, lambda: popup.show(devices, readings, error))

    def on_left_click(icon: pystray.Icon, item: object = None) -> None:
        _show_popup()

    def on_refresh(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        try:
            new_config = load_config(APP_DIR / "config.json")
            active_config[0] = new_config
            scanner.reload_config(new_config)
            logger.info("Config neu geladen — %d Geräte", len(new_config.devices))
        except ConfigError as exc:
            logger.error("Config-Reload fehlgeschlagen: %s", exc)
        scanner.trigger_scan()

    def on_settings(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        os.startfile(str(APP_DIR / "config.json"))

    def on_show_log(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        log_path = APP_DIR / "switchbot_wetter.log"
        if log_path.exists():
            os.startfile(str(log_path))  # Windows-only, intentional
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
        pystray.MenuItem("Anzeigen", on_left_click, default=True),
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
