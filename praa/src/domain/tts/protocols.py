"""
TTS Domain — Protocols (Interface Segregation)

Defines the contract for any TTS engine implementation.
Swappable via DIP — could be edge-tts today, offline TTS tomorrow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ITTSEngine(Protocol):
    """
    Contract for a text-to-speech synthesis engine.

    Implementations must:
    - Accept text, voice ID, and speed rate
    - Return a path to the synthesized audio file
    - Handle network/synthesis errors gracefully
    """

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: float,
    ) -> Path | None:
        """
        Synthesize text to an audio file.

        Args:
            text: Text to synthesize.
            voice: Voice ID (e.g., 'id-ID-ArdiNeural').
            rate: Speed multiplier (1.0 = normal).

        Returns:
            Path to the synthesized audio file, or None on failure.
        """
        ...
