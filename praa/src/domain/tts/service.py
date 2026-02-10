"""
TTS Domain — edge-tts Async Synthesis Service

Concrete implementation of ITTSEngine using Microsoft's edge-tts.
Handles temp file management, rate formatting, and per-chunk synthesis.
Publishes SynthesisStarted/SynthesisComplete events.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import edge_tts

from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    SynthesisComplete,
    SynthesisStarted,
    TextProcessed,
)

logger = logging.getLogger(__name__)


class EdgeTTSService:
    """
    Text-to-speech synthesis using Microsoft Neural voices via edge-tts.

    Processes each chunk independently, writing to temp files that the
    audio player will consume. Temp files are managed here but cleanup
    responsibility belongs to the audio player after playback.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._temp_dir = Path(tempfile.mkdtemp(prefix="praa_tts_"))
        logger.info("TTS temp directory: %s", self._temp_dir)

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: float,
    ) -> Path | None:
        """
        Synthesize a single text chunk to a temp audio file.

        Args:
            text: Text to synthesize.
            voice: Voice ID (e.g., 'id-ID-ArdiNeural').
            rate: Speed multiplier (1.0 = normal).

        Returns:
            Path to the synthesized .mp3 file, or None on failure.
        """
        try:
            rate_str = self._format_rate(rate)
            output_path = self._temp_dir / f"chunk_{id(text)}.mp3"

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate_str,
            )
            await communicate.save(str(output_path))

            logger.debug(
                "Synthesized %d chars → %s (voice=%s, rate=%s)",
                len(text),
                output_path.name,
                voice,
                rate_str,
            )
            return output_path

        except Exception:
            logger.exception("TTS synthesis failed for chunk: %s...", text[:50])
            return None

    async def handle_text_processed(self, event: TextProcessed) -> None:
        """
        Handle TextProcessed event: synthesize all chunks sequentially.

        Publishes SynthesisStarted and SynthesisComplete for each chunk,
        allowing the audio player to begin playback as soon as the first
        chunk is ready (streaming behavior).
        """
        total = len(event.chunks)
        logger.info(
            "Starting synthesis: %d chunks, voice=%s, rate=%s",
            total,
            event.voice_id,
            event.speed_rate,
        )

        for index, chunk_text in enumerate(event.chunks):
            # Notify synthesis start
            await self._event_bus.publish(
                SynthesisStarted(chunk_index=index, total_chunks=total)
            )

            # Synthesize
            audio_path = await self.synthesize(
                text=chunk_text,
                voice=event.voice_id,
                rate=event.speed_rate,
            )

            if audio_path and audio_path.exists():
                await self._event_bus.publish(
                    SynthesisComplete(
                        audio_path=audio_path,
                        chunk_index=index,
                        total_chunks=total,
                    )
                )
            else:
                logger.error(
                    "Synthesis failed for chunk %d/%d, skipping", index + 1, total
                )

    @staticmethod
    def _format_rate(rate: float) -> str:
        """
        Format speed rate for edge-tts.

        edge-tts expects rate as a percentage string like '+0%', '+25%', '-25%'.
        A rate of 1.0 = '+0%', 1.25 = '+25%', 0.75 = '-25%'.
        """
        percentage = int((rate - 1.0) * 100)
        if percentage >= 0:
            return f"+{percentage}%"
        return f"{percentage}%"

    def cleanup(self) -> None:
        """Remove all temp audio files."""
        try:
            import shutil
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.info("TTS temp directory cleaned up")
        except Exception:
            logger.exception("Failed to clean up TTS temp directory")
