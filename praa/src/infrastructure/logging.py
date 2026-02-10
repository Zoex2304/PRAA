"""
PRAA Logging — Structured Logger Configuration

Centralizes log configuration so all domain modules use a consistent
format and output destination. Import setup_logging() once at bootstrap.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> None:
    """
    Configure the root logger for PRAA.

    Args:
        level: Minimum log level (default: INFO).
        log_file: Optional path to a log file for debug output.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()

    # Console handler — always active
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    )
    root_logger.addHandler(console_handler)

    # File handler — optional, for debug mode
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        )
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("pynput").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
