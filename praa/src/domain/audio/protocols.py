"""
Audio Domain — Protocols (Interface Segregation)

Defines contracts for audio playback and queue management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class IAudioPlayer(Protocol):
    """
    Contract for audio playback implementations.

    Implementations must support play, stop, pause, and resume operations.
    Playback should run on a dedicated thread to avoid blocking the async loop.
    """

    def play(self, audio_path: Path) -> None:
        """Play an audio file. Blocks until playback completes or is stopped."""
        ...

    def stop(self) -> None:
        """Stop current playback immediately."""
        ...

    def pause(self) -> None:
        """Pause current playback."""
        ...

    def resume(self) -> None:
        """Resume paused playback."""
        ...

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently playing."""
        ...

    @property
    def is_paused(self) -> bool:
        """Whether audio is currently paused."""
        ...
