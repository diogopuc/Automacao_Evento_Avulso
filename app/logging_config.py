from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_dir: Path, execution_id: str, callback=None) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"eventos_avulsos.{execution_id}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_dir / f"execucao_{execution_id}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if callback:
        class UiHandler(logging.Handler):
            def emit(self, record):
                callback(self.format(record))
        ui_handler = UiHandler()
        ui_handler.setLevel(logging.INFO)
        ui_handler.setFormatter(formatter)
        logger.addHandler(ui_handler)
    return logger
