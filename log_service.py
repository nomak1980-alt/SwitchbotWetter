import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_path: Path = Path("switchbot_wetter.log"), debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    )
    logging.basicConfig(level=level, handlers=[handler])
