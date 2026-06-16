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
