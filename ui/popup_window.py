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
SEPARATOR = "#444444"


class PopupWindow:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._window: tk.Toplevel | None = None
        self._device_labels: dict[str, dict] = {}
        self._macs_with_data: set[str] = set()

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

        self._device_labels = {}
        self._macs_with_data = set()

        win = tk.Toplevel(self._root)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)

        # Titelzeile mit X-Button
        title_bar = tk.Frame(win, bg=BG)
        title_bar.pack(fill=tk.X)
        tk.Label(
            title_bar, text="🌡 SwitchBot Wetter",
            bg=BG, fg=FG_TITLE, font=("Segoe UI", 11, "bold"),
            padx=14, pady=10,
        ).pack(side=tk.LEFT)
        close_btn = tk.Label(
            title_bar, text="✕",
            bg=BG, fg=FG_LABEL, font=("Segoe UI", 11),
            padx=10, pady=10, cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=FG_TITLE))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=FG_LABEL))
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
                    self._macs_with_data.add(mac)
                    temp_label = tk.Label(
                        frame, text=f"{reading.temperature:.1f} °C  •  {reading.humidity} %",
                        bg=BG, fg=FG_VALUE, font=("Segoe UI", 14, "bold"),
                    )
                    temp_label.pack(anchor=tk.W)
                    info_label = tk.Label(
                        frame, text=self._info_text(reading),
                        bg=BG, fg=FG_BATTERY, font=("Segoe UI", 8),
                    )
                    info_label.pack(anchor=tk.W)
                    self._device_labels[mac] = {"temp": temp_label, "info": info_label}
                else:
                    nodata_label = tk.Label(
                        frame, text="— keine Daten —",
                        bg=BG, fg=FG_NODATA, font=("Segoe UI", 10),
                    )
                    nodata_label.pack(anchor=tk.W)
                    self._device_labels[mac] = {"nodata": nodata_label}

        tk.Frame(win, bg=SEPARATOR, height=1).pack(fill=tk.X)

        # Positionieren: rechts unten
        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = sw - w - 14
        y = sh - h - 50
        win.geometry(f"{w}x{h}+{x}+{y}")

        self._window = win

    def update_data(
        self,
        devices: list[DeviceConfig],
        readings: dict[str, SensorReading],
        error: str | None = None,
    ) -> None:
        """Aktualisiert Messwerte im offenen Popup ohne Neuaufbau. Muss im Main-Thread aufgerufen werden."""
        if self._window is None:
            return

        new_macs_with_data = {
            d.mac_address.upper() for d in devices
            if readings.get(d.mac_address.upper()) is not None
        }
        if new_macs_with_data != self._macs_with_data:
            # Struktur hat sich geändert (z.B. Sensor erstmals empfangen) → neu aufbauen
            self.show(devices, readings, error)
            return

        for device in devices:
            mac = device.mac_address.upper()
            reading = readings.get(mac)
            labels = self._device_labels.get(mac)
            if labels is None or reading is None:
                continue
            labels["temp"].configure(text=f"{reading.temperature:.1f} °C  •  {reading.humidity} %")
            labels["info"].configure(text=self._info_text(reading))

    def _info_text(self, reading: SensorReading) -> str:
        ts = reading.timestamp.strftime("%H:%M:%S")
        if reading.battery is not None:
            return f"Batterie: {reading.battery} %  •  {ts}"
        return ts

    def is_open(self) -> bool:
        return self._window is not None

    def close(self) -> None:
        """Schließt das Popup. Muss im Main-Thread aufgerufen werden."""
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None
