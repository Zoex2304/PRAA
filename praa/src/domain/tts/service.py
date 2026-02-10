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
    ) -> tuple[Path | None, list[tuple[float, float, str, int, int]]]:
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

            # Fallback: If no word boundaries but sentences exist (e.g. Indonesian voices)
            if not word_boundaries and sentence_boundaries:
                logger.info("No WordBoundary events. Interpolating from %d SentenceBoundary events.", len(sentence_boundaries))
                word_boundaries = self._interpolate_words_from_sentences(sentence_boundaries)
            
            # Post-process to add text offsets
            enhanced_boundaries = self._calculate_text_offsets(text, word_boundaries)

            logger.debug(
                "Synthesized %d chars → %s (%d word boundaries)",
                len(text), output_path.name, len(enhanced_boundaries),
            )
            return output_path, enhanced_boundaries
    


        except Exception:
            logger.exception("TTS synthesis failed for chunk: %s...", text[:50])
            return None, []

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

            audio_path, word_boundaries = await self.synthesize(
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

    def _calculate_text_offsets(
        self,
        text: str,
        boundaries: list[tuple[float, float, str]]
    ) -> list[tuple[float, float, str, int, int]]:
        """
        Map word events to character offsets in the text.
        Returns list of (offset, duration, word, text_offset, word_len).
        """
        enhanced = []
        current_pos = 0
        text_lower = text.lower()
        
        for offset, duration, word in boundaries:
            word_clean = word.strip()
            if not word_clean:
                continue
                
            # Try exact match first
            idx = text.find(word_clean, current_pos)
            if idx == -1:
                # Try case-insensitive
                idx = text_lower.find(word_clean.lower(), current_pos)
            
            if idx != -1:
                enhanced.append((offset, duration, word_clean, idx, len(word_clean)))
                current_pos = idx + len(word_clean)
            else:
                # Fallback: keep existing without offset
                enhanced.append((offset, duration, word_clean, current_pos, len(word_clean)))
                
        return enhanced

    def _interpolate_words_from_sentences(
        self,
        sentences: list[tuple[float, float, str]]
    ) -> list[tuple[float, float, str]]:
        """
        Generate estimated word boundaries by splitting sentences and distributing duration.
        Accounts for punctuation pauses to improve sync accuracy.
        """
        estimated = []
        
        # Heuristic pause durations (ms)
        PAUSE_COMMA = 250.0 
        PAUSE_SENTENCE = 500.0
        
        for s_offset, s_duration, s_text in sentences:
            words = s_text.split()
            if not words:
                continue
                
            # 1. Analyze words for punctuation pauses
            word_pauses = []
            total_pause_duration = 0.0
            total_chars = 0
            
            for word in words:
                pause = 0.0
                clean_word = word.strip()
                if clean_word.endswith(",") or clean_word.endswith(";") or clean_word.endswith(":"):
                    pause = PAUSE_COMMA
                elif clean_word.endswith(".") or clean_word.endswith("?") or clean_word.endswith("!"):
                    pause = PAUSE_SENTENCE
                
                word_pauses.append(pause)
                total_pause_duration += pause
                total_chars += len(clean_word)
            
            if total_chars == 0:
                continue
                
            # 2. Calculate active speech duration
            # Ensure we don't subtract more than available (clamp to 10% of duration minimum)
            max_pause = s_duration * 0.9
            actual_pause_total = min(total_pause_duration, max_pause)
            
            # Scale pauses if they exceed limit
            pause_scale = 1.0
            if total_pause_duration > max_pause:
                 pause_scale = max_pause / total_pause_duration
            
            active_duration = s_duration - actual_pause_total
            
            current_offset = s_offset
            
            for i, word in enumerate(words):
                # Proportional duration based on length
                word_ratio = len(word) / total_chars
                word_duration = active_duration * word_ratio
                
                estimated.append((current_offset, word_duration, word))
                
                # Advance offset by word + pause
                pause = word_pauses[i] * pause_scale
                current_offset += word_duration + pause
                
        return estimated
