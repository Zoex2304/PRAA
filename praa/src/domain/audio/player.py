"""
Audio Domain — sounddevice + soundfile Player

Low-level audio playback using sounddevice for output and soundfile
for reading audio files. Runs on a dedicated thread to avoid blocking
the async event loop.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger(__name__)


class SoundDevicePlayer:
    """
    Audio player using sounddevice for precise buffer-level control.

    Playback runs on a dedicated thread. Supports stop, pause, and resume
    through threading events. The player reads the entire file into memory
    for responsive pause/stop behavior.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._playing = False
        self._paused = False
        self._current_thread: threading.Thread | None = None
        self._current_position_frames = 0
        self._samplerate = 24000  # Default, updated on play
        self._current_block: np.ndarray | None = None  # Latest audio block for spectrum
        self._duration_ms = 0.0

    @property
    def position_ms(self) -> float:
        """Get current playback position in milliseconds."""
        if self._samplerate <= 0:
            return 0.0
        return (self._current_position_frames / self._samplerate) * 1000.0

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently playing (including paused state)."""
        return self._playing

    @property
    def current_block(self) -> np.ndarray | None:
        """Latest audio block being played (for spectrum analysis)."""
        return self._current_block

    @property
    def is_paused(self) -> bool:
        """Whether audio is currently paused."""
        return self._paused

    @property
    def duration_ms(self) -> float:
        """Total duration of current track in milliseconds."""
        return self._duration_ms

    def play(self, audio_path: Path, on_start: Optional[Callable[[], None]] = None) -> None:
        """
        Play an audio file. Blocks until playback completes or is stopped.

        Args:
            audio_path: Path to the audio file (.mp3, .wav, etc.).
            on_start: Optional callback invoked immediately after stream starts.
        """
        try:
            # Read audio file
            data, samplerate = sf.read(str(audio_path), dtype="float32")
            self._samplerate = samplerate
            self._current_position_frames = 0
            
            # Calculate duration
            if samplerate > 0:
                self._duration_ms = (len(data) / samplerate) * 1000.0
            else:
                self._duration_ms = 0.0

            with self._lock:
                self._stop_event.clear()
                self._pause_event.set()
                self._playing = True
                self._paused = False

            logger.debug(
                "Playing: %s (rate=%d, samples=%d)",
                audio_path.name,
                samplerate,
                len(data),
            )

            # Play using sounddevice blocking mode with callback for stop/pause
            block_size = 1024
            position = 0

            stream = sd.OutputStream(
                samplerate=samplerate,
                channels=data.ndim if data.ndim > 1 else 1,
                dtype="float32",
            )
            stream.start()
            if on_start:
                on_start()

            try:
                while position < len(data):
                    # Check stop
                    if self._stop_event.is_set():
                        logger.debug("Playback stopped by user")
                        break

                    # Check pause (blocks here while paused)
                    self._pause_event.wait()

                    # Write next block
                    end_pos = min(position + block_size, len(data))
                    block = data[position:end_pos]

                    if data.ndim == 1:
                        block = block.reshape(-1, 1)

                    stream.write(block)
                    position = end_pos
                    self._current_position_frames = position
                    self._current_block = block  # Expose for spectrum analyzer

            finally:
                stream.stop()
                stream.close()

            with self._lock:
                self._playing = False
                self._paused = False
                self._current_block = None

        except Exception:
            logger.exception("Playback error for %s", audio_path)
            with self._lock:
                self._playing = False
                self._paused = False
                self._current_block = None

    def stop(self) -> None:
        """Stop current playback immediately."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        logger.debug("Stop signal sent")

    def pause(self) -> None:
        """Pause current playback."""
        if self._playing and not self._paused:
            self._pause_event.clear()
            self._paused = True
            logger.debug("Playback paused")

    def resume(self) -> None:
        """Resume paused playback."""
        if self._paused:
            self._pause_event.set()
            self._paused = False
            logger.debug("Playback resumed")
