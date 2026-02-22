from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LogEntry:
    level: int
    level_name: str
    thread_name: str
    module: str
    message: str
    timestamp: float

    @property
    def formatted_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")


class FletLogHandler(logging.Handler):
    def __init__(self, max_records: int = 300) -> None:
        super().__init__()
        self._records: list[LogEntry] = []
        self._max_records = max_records
        self._drain_idx: int = 0
        self._thread_activity: dict[str, str] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(
                level=record.levelno,
                level_name=record.levelname,
                thread_name=record.threadName,
                module=record.name,
                message=record.getMessage(),
                timestamp=record.created,
            )
            self._records.append(entry)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
                self._drain_idx = max(0, self._drain_idx - (len(self._records) - self._max_records))
            self._thread_activity[record.threadName] = record.getMessage()[:120]
        except Exception:
            self.handleError(record)

    def drain_new_entries(self) -> list[LogEntry]:
        new = self._records[self._drain_idx:]
        self._drain_idx = len(self._records)
        return new

    def get_thread_activity(self) -> dict[str, str]:
        return dict(self._thread_activity)

    @property
    def records(self) -> list[LogEntry]:
        return list(self._records)
