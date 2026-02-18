from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

from src.domain.config.constants import AUDIO_DEQUEUE_TIMEOUT_S

logger = logging.getLogger(__name__)


class AudioQueue:
    def __init__(self) -> None:
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._lock = threading.Lock()

    def enqueue(self, audio_path: Path) -> None:
        self._queue.put(audio_path)
        logger.debug(
            "Enqueued: %s (queue size: ~%d)",
            audio_path.name,
            self._queue.qsize(),
        )

    def dequeue(self, timeout: float = AUDIO_DEQUEUE_TIMEOUT_S) -> Path | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> int:
        count = 0
        with self._lock:
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item is not None and item.exists():
                        try:
                            item.unlink()
                        except OSError:
                            pass
                    count += 1
                except queue.Empty:
                    break

        if count > 0:
            logger.debug("Queue cleared: %d items removed", count)
        return count

    def signal_done(self) -> None:
        self._queue.put(None)

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        return self._queue.empty()