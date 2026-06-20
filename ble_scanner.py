import asyncio
import dataclasses
import logging
import threading

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from config_service import AppConfig
from device_parser import SensorReading, parse

logger = logging.getLogger(__name__)


class BleScanner:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._mac_set = {d.mac_address.upper() for d in config.devices}
        self._cache: dict[str, SensorReading] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._periodic_task: asyncio.Task | None = None
        self._last_error: str | None = None
        self._backoff: float = 1.0
        self._loop_ready = threading.Event()
        self._on_update: "Callable[[], None] | None" = None

    def set_update_callback(self, callback: "Callable[[], None]") -> None:
        self._on_update = callback

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BLE-Thread")
        self._thread.start()

    def stop(self) -> None:
        if self._loop is None:
            return
        self._loop_ready.wait(timeout=5.0)
        if self._periodic_task is not None:
            self._loop.call_soon_threadsafe(self._periodic_task.cancel)
        self._loop.call_soon_threadsafe(self._loop.stop)

    def trigger_scan(self) -> None:
        if self._loop is None or not self._loop.is_running():
            return
        fut = asyncio.run_coroutine_threadsafe(self._scan_burst(), self._loop)
        fut.add_done_callback(
            lambda f: logger.error("trigger_scan Fehler: %s", f.exception(), exc_info=f.exception())
            if f.exception() else None
        )

    def get_readings(self) -> dict[str, SensorReading]:
        with self._lock:
            return dict(self._cache)

    def get_last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def reload_config(self, config: AppConfig) -> None:
        self._config = config
        with self._lock:
            self._mac_set = {d.mac_address.upper() for d in config.devices}

    # --- Internes Threading ---

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self) -> None:
        self._loop_ready.set()
        if self._config.scan_mode == "interval":
            # ESP32-Variante: sparsamer Burst-Scan, dazwischen Funk aus
            await self._scan_burst()
            self._periodic_task = asyncio.create_task(self._periodic_scan())
        else:
            # PC-Variante: Funk dauerhaft an, maximale Empfangschance
            self._periodic_task = asyncio.create_task(self._continuous_scan())
        try:
            await self._periodic_task
        except asyncio.CancelledError:
            pass

    async def _periodic_scan(self) -> None:
        while True:
            await asyncio.sleep(self._config.scan_interval_seconds)
            await self._scan_burst()

    async def _continuous_scan(self) -> None:
        """PC-Variante: Scanner dauerhaft aktiv. Alle scan_interval_seconds kurz
        neu starten, damit der WinRT-Scanner nicht 'einschläft'. Der Cache wird
        die ganze Zeit live über _advertisement_callback aktualisiert."""
        logger.info(
            "BLE-Dauerscan gestartet (Scanner-Refresh alle %ds)",
            self._config.scan_interval_seconds,
        )
        while True:
            try:
                scanner = BleakScanner(detection_callback=self._advertisement_callback)
                await scanner.start()
                try:
                    await asyncio.sleep(self._config.scan_interval_seconds)
                finally:
                    await scanner.stop()
                with self._lock:
                    self._last_error = None
                self._backoff = 1.0
            except Exception as exc:
                error_msg = str(exc)
                with self._lock:
                    self._last_error = f"BLE-Fehler: {error_msg}"
                logger.exception("BLE-Dauerscan-Fehler, Retry in %.0fs", self._backoff)
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, 60.0)

    async def _scan_burst(self) -> None:
        logger.info("BLE-Scan gestartet (Dauer: %ds)", self._config.scan_duration_seconds)
        try:
            scanner = BleakScanner(
                detection_callback=self._advertisement_callback,
            )
            await scanner.start()
            try:
                await asyncio.sleep(self._config.scan_duration_seconds)
            finally:
                await scanner.stop()
            with self._lock:
                self._last_error = None
            self._backoff = 1.0
            logger.info("BLE-Scan abgeschlossen")
        except Exception as exc:
            error_msg = str(exc)
            with self._lock:
                self._last_error = f"BLE-Fehler: {error_msg}"
            logger.exception("BLE-Scan-Fehler, Retry in %.0fs", self._backoff)
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, 60.0)

    # --- Advertisement-Callback (aus bleak asyncio-Thread) ---

    def _advertisement_callback(self, device: BLEDevice, advertisement: AdvertisementData) -> None:
        mac = device.address.upper()
        if mac not in self._mac_set:
            return
        logger.debug(
            "Advertisement von %s (RSSI %s dBm): mfr=%s svc=%s",
            mac,
            advertisement.rssi,
            dict(advertisement.manufacturer_data),
            dict(advertisement.service_data),
        )
        reading = parse(mac, advertisement.manufacturer_data, advertisement.service_data)
        if reading is None:
            return
        with self._lock:
            existing = self._cache.get(mac)
            if reading.battery is None and existing is not None and existing.battery is not None:
                reading = dataclasses.replace(reading, battery=existing.battery)
            self._cache[mac] = reading
        if self._on_update:
            self._on_update()
