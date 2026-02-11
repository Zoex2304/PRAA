"""
TTS Domain — edge-tts Async Synthesis Service

Concrete implementation using Microsoft's edge-tts.
Uses streaming API to capture word boundary timing data
for Spotify-like synchronized transcript highlighting.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import edge_tts

from src.domain.processor.text_offset_mapper import calculate_text_offsets
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

    Uses streaming API to capture word boundary events for precise
    transcript synchronization during playback.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._temp_dir = Path(tempfile.mkdtemp(prefix="praa_tts_"))
        self._last_audio_paths: list[Path] = []
        logger.info("TTS temp directory: %s", self._temp_dir)

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: float,
    ) -> tuple[Path | None, list[tuple[float, float, str, int, int]], list[tuple[float, float, str]]]:
        """
        Synthesize a single text chunk to a temp audio file.

        Uses streaming API to capture word boundary timing data.

        Returns:
            Tuple of (audio_path, word_boundaries) where word_boundaries
            is a list of (offset, duration, word, text_offset, word_len).
        """
        try:
            rate_str = self._format_rate(rate)
            output_path = self._temp_dir / f"chunk_{id(text)}_{len(self._last_audio_paths)}.mp3"

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate_str,
            )

            # Stream audio AND capture word/sentence boundaries
            word_boundaries: list[tuple[float, float, str]] = []
            sentence_boundaries: list[tuple[float, float, str]] = []

            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        # Convert from 100-ns to milliseconds
                        offset_ms = chunk["offset"] / 10_000
                        duration_ms = chunk["duration"] / 10_000
                        word = chunk["text"]
                        word_boundaries.append((offset_ms, duration_ms, word))
                        # logger.debug("Word boundary: %s", word) 
                    elif chunk["type"] == "SentenceBoundary":
                        # Capture sentences as fallback
                        offset_ms = chunk["offset"] / 10_000
                        duration_ms = chunk["duration"] / 10_000
                        text_chunk = chunk["text"]
                        sentence_boundaries.append((offset_ms, duration_ms, text_chunk))
                        logger.debug("Sentence boundary captured: %s", text_chunk[:20])
            
            logger.info("Stream finished. Audio: %s bytes. Words: %d. Sentences: %d", output_path.stat().st_size, len(word_boundaries), len(sentence_boundaries))
            self._last_audio_paths.append(output_path)

            # Post-process to add text offsets (only for existing word boundaries)
            enhanced_boundaries = calculate_text_offsets(text, word_boundaries)

            logger.debug(
                "Synthesized %d chars → %s (%d word boundaries, %d sentences)",
                len(text), output_path.name, len(enhanced_boundaries), len(sentence_boundaries)
            )
            return output_path, enhanced_boundaries, sentence_boundaries

        except Exception:
            logger.exception("TTS synthesis failed for chunk: %s...", text[:50])
            return None, [], []

    async def handle_text_processed(self, event: TextProcessed) -> None:
        """
        Handle TextProcessed event: synthesize all chunks sequentially.

        Publishes SynthesisStarted and SynthesisComplete for each chunk,
        including word boundary timing data for transcript sync.
        """
        total = len(event.chunks)
        logger.info(
            "Starting synthesis: %d chunks, voice=%s, rate=%s",
            total, event.voice_id, event.speed_rate,
        )

        # Clear previous audio paths for new session
        self._last_audio_paths.clear()

        for index, chunk_text in enumerate(event.chunks):
            await self._event_bus.publish(
                SynthesisStarted(chunk_index=index, total_chunks=total)
            )

            audio_path, word_boundaries, sentence_boundaries = await self.synthesize(
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
                        chunk_text=chunk_text,
                        word_boundaries=word_boundaries,
                        sentence_boundaries=sentence_boundaries,
                    )
                )
            else:
                logger.error(
                    "Synthesis failed for chunk %d/%d, skipping", index + 1, total
                )

    def get_all_audio_paths(self) -> list[Path]:
        """Return all synthesized audio paths from the last session."""
        return [p for p in self._last_audio_paths if p.exists()]

    @staticmethod
    def _format_rate(rate: float) -> str:
        """Format speed rate for edge-tts (+0%, +25%, -25%)."""
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


