"""
Audio Domain — FIFO Audio Queue Manager

Manages sequential playback of multiple audio chunks.
Supports rapid trigger buffering (F11) — if a new read is triggered
while playing, chunks are enqueued for sequential playback.
"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioQueue:
    """
    FIFO queue for sequential audio chunk playback.

    Thread-safe queue that accepts audio file paths and yields them
    in order. Supports clearing (for stop commands) and draining.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._lock = threading.Lock()

    def enqueue(self, audio_path: Path) -> None:
        """
        Add an audio file to the playback queue.

        Args:
            audio_path: Path to the synthesized audio file.
        """
        self._queue.put(audio_path)
        logger.debug(
            "Enqueued: %s (queue size: ~%d)",
            audio_path.name,
            self._queue.qsize(),
        )

    def dequeue(self, timeout: float = 0.5) -> Path | None:
        """
        Get the next audio file from the queue.

        Args:
            timeout: Seconds to wait for an item.

        Returns:
            Path to the next audio file, or None if queue is empty/timeout.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> int:
        """
        Remove all items from the queue.

        Returns:
            Number of items removed.
        """
        count = 0
        with self._lock:
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    # Clean up temp files
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
        """Signal that no more items will be added (sentinel value)."""
        self._queue.put(None)

    @property
    def size(self) -> int:
        """Approximate current queue size."""
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        """Whether the queue is empty."""
        return self._queue.empty()
