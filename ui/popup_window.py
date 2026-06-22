import tkinter as tk
from typing import Optional

from config_service import DeviceConfig
from device_parser import SensorReading

# --- Farbpalette (Catppuccin Mocha — identisch mit MerossSteckdosen) ---
BG        = "#1e1e2e"
CARD_BG   = "#27273d"
SEPARATOR = "#313244"
FG_TITLE  = "#cdd6f4"
FG_NAME   = "#cdd6f4"
FG_VALUE  = "#cdd6f4"
FG_INFO   = "#fab387"
FG_NODATA = "#45475a"
FG_ERROR  = "#f38ba8"
FG_ONLINE = "#a6e3a1"
FG_NOCON  = "#585b70"
CLOSE_FG  = "#585b70"
MIN_W     = 300


class PopupWindow:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._window: Optional[tk.Toplevel] = None
        self._device_labels: dict[str, dict] = {}
        self._macs_with_data: set[str] = set()

    def show(
        self,
        devices: list[DeviceConfig],
        readings: dict[str, SensorReading],
        error: str | None = None,
    ) -> None:
        if self._window is not None:
            self._window.destroy()
            self._window = None
        self._device_labels = {}
        self._macs_with_data = set()

        win = tk.Toplevel(self._root)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)

        # --- Titelzeile ---
        title_bar = tk.Frame(win, bg=BG)
        title_bar.pack(fill=tk.X, padx=16, pady=(14, 10))
        tk.Label(
            title_bar, text="🌡  SwitchBot Wetter",
            bg=BG, fg=FG_TITLE, font=("Segoe UI", 12, "bold"),
        ).pack(side=tk.LEFT)
        close = tk.Label(
            title_bar, text="✕", bg=BG, fg=CLOSE_FG,
            font=("Segoe UI", 11), cursor="hand2",
        )
        close.pack(side=tk.RIGHT)
        close.bind("<Button-1>", lambda e: self.close())
        close.bind("<Enter>",    lambda e: close.configure(fg=FG_TITLE))
        close.bind("<Leave>",    lambda e: close.configure(fg=CLOSE_FG))

        tk.Frame(win, bg=SEPARATOR, height=1).pack(fill=tk.X)
        tk.Frame(win, bg=BG, height=4).pack()

        # --- Globaler Fehler (noch keine Messdaten) ---
        if error and not readings:
            err_card = tk.Frame(win, bg=CARD_BG)
            err_card.pack(fill=tk.X, padx=10)
            tk.Label(
                err_card, text=error,
                bg=CARD_BG, fg=FG_ERROR, font=("Segoe UI", 9),
                padx=14, pady=12, wraplength=260,
            ).pack()
            tk.Frame(win, bg=BG, height=4).pack()
        else:
            for device in devices:
                mac = device.mac_address.upper()
                self._build_card(win, device, mac, readings.get(mac))
                tk.Frame(win, bg=BG, height=4).pack()

        tk.Frame(win, bg=SEPARATOR, height=1).pack(fill=tk.X)

        # --- Positionierung: rechts unten ---
        win.update_idletasks()
        w = max(win.winfo_reqwidth(), MIN_W)
        h = win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{sw - w - 14}+{sh - h - 50}")
        self._window = win

    def _build_card(
        self,
        win: tk.Toplevel,
        device: DeviceConfig,
        mac: str,
        reading: Optional[SensorReading],
    ) -> None:
        card = tk.Frame(win, bg=CARD_BG)
        card.pack(fill=tk.X, padx=10)

        # Kopfzeile: Name links, Dot rechts
        hdr = tk.Frame(card, bg=CARD_BG)
        hdr.pack(fill=tk.X, padx=14, pady=(12, 6))
        tk.Label(
            hdr, text=device.name,
            bg=CARD_BG, fg=FG_NAME, font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT)
        dot = tk.Label(
            hdr,
            text="● ONLINE" if reading else "● —",
            bg=CARD_BG,
            fg=FG_ONLINE if reading else FG_NOCON,
            font=("Segoe UI", 8),
        )
        dot.pack(side=tk.RIGHT)

        labels: dict = {"dot": dot}

        if reading:
            self._macs_with_data.add(mac)
            val_lbl = tk.Label(
                card,
                text=f"{reading.temperature:.1f} °C  •  {reading.humidity} %",
                bg=CARD_BG, fg=FG_VALUE, font=("Segoe UI", 18, "bold"),
            )
            val_lbl.pack(anchor=tk.W, padx=14)
            info_lbl = tk.Label(
                card, text=self._info_text(reading),
                bg=CARD_BG, fg=FG_INFO, font=("Segoe UI", 8),
            )
            info_lbl.pack(anchor=tk.W, padx=14, pady=(3, 12))
            labels["val"] = val_lbl
            labels["info"] = info_lbl
        else:
            tk.Label(
                card, text="— keine Daten —",
                bg=CARD_BG, fg=FG_NODATA, font=("Segoe UI", 10),
            ).pack(anchor=tk.W, padx=14, pady=(0, 12))

        self._device_labels[mac] = labels

    def update_data(
        self,
        devices: list[DeviceConfig],
        readings: dict[str, SensorReading],
        error: str | None = None,
    ) -> None:
        if self._window is None:
            return

        new_macs_with_data = {
            d.mac_address.upper() for d in devices
            if readings.get(d.mac_address.upper()) is not None
        }
        if new_macs_with_data != self._macs_with_data:
            self.show(devices, readings, error)
            return

        for device in devices:
            mac = device.mac_address.upper()
            reading = readings.get(mac)
            labels = self._device_labels.get(mac)
            if labels is None:
                continue
            labels["dot"].configure(
                text="● ONLINE" if reading else "● —",
                fg=FG_ONLINE if reading else FG_NOCON,
            )
            if reading and "val" in labels:
                labels["val"].configure(
                    text=f"{reading.temperature:.1f} °C  •  {reading.humidity} %"
                )
                labels["info"].configure(text=self._info_text(reading))

    @staticmethod
    def _info_text(reading: SensorReading) -> str:
        ts = reading.timestamp.strftime("%H:%M:%S")
        if reading.battery is not None:
            return f"Batterie: {reading.battery} %   •   {ts}"
        return ts

    def is_open(self) -> bool:
        return self._window is not None

    def close(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None
