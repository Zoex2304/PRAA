from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler

LOG_FORMAT = "%(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()

    # Rich console handler — colorized, structured output
    rich_handler = RichHandler(
        level=level,
        show_time=True,
        show_level=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        log_time_format=LOG_DATE_FORMAT,
    )
    root_logger.addHandler(rich_handler)

    # File handler — optional, for debug mode (plain text)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s",
                datefmt=LOG_DATE_FORMAT,
            )
        )
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("pynput").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
