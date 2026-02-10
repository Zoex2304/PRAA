"""
Processor Domain — Orchestrator Service

Coordinates the cleaner → detector → chunker pipeline.
Subscribes to TextCaptured events, publishes TextProcessed events.
"""

from __future__ import annotations

import logging

from src.domain.config.models import AppConfig
from src.domain.processor.cleaner import TextCleaner
from src.domain.processor.chunker import TextChunker
from src.domain.processor.detector import LanguageDetector
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import ConfigChanged, DetectedLanguage, TextCaptured, TextProcessed

logger = logging.getLogger(__name__)


class ProcessorService:
    """
    Orchestrates the text processing pipeline.

    Flow: raw text → clean → detect language → chunk → publish TextProcessed

    Each sub-component (cleaner, detector, chunker) is an independent
    class with its own responsibility (SRP). This service only coordinates.
    """

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        cleaner: TextCleaner | None = None,
        detector: LanguageDetector | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._cleaner = cleaner or TextCleaner()
        self._detector = detector or LanguageDetector()
        self._chunker = chunker or TextChunker()

    async def handle_text_captured(self, event: TextCaptured) -> None:
        """
        Process captured text through the full pipeline.

        Args:
            event: TextCaptured event with raw clipboard text.
        """
        raw_text = event.raw_text
        logger.info("Processing text: %d characters", len(raw_text))

        # Step 1: Clean
        clean_text = self._cleaner.clean(raw_text)
        if not clean_text:
            logger.warning("Text is empty after cleaning, skipping")
            return

        # Step 2: Detect language
        language = self._detect_language(clean_text)

        # Step 3: Select voice based on language
        voice_id = self._config.get_voice_for_language(language.value)

        # Step 4: Chunk for TTS
        chunks = self._chunker.chunk(clean_text, self._config.max_chunk_length)
        if not chunks:
            logger.warning("No chunks produced, skipping")
            return

        logger.info(
            "Text processed: lang=%s, voice=%s, chunks=%d",
            language.value,
            voice_id,
            len(chunks),
        )

        # Publish result
        await self._event_bus.publish(
            TextProcessed(
                chunks=chunks,
                language=language,
                voice_id=voice_id,
                speed_rate=self._config.speed_rate,
            )
        )

    def _detect_language(self, text: str) -> DetectedLanguage:
        """Detect language, respecting user's language preference override."""
        from src.domain.config.models import LanguagePreference

        if self._config.language_preference == LanguagePreference.INDONESIAN:
            return DetectedLanguage.INDONESIAN
        elif self._config.language_preference == LanguagePreference.ENGLISH:
            return DetectedLanguage.ENGLISH
        else:
            # Auto-detect
            return self._detector.detect(text)

    async def handle_config_changed(self, event: ConfigChanged) -> None:
        """
        React to runtime config changes.

        Reloads the config reference so subsequent text processing
        uses the latest speed_rate, voice_id, and language_preference.
        """
        # Re-read the config from the config service's current state
        # The config object is mutable at the service level, so we need
        # to accept a fresh reference. For simplicity, we update individual
        # fields based on what changed.
        if event.key in ("speed_rate", "voice_id", "voice_en",
                         "voice_gender", "language_preference", "max_chunk_length"):
            # Update our config reference with the new value
            updated_data = self._config.model_dump()
            updated_data[event.key] = event.new_value
            try:
                self._config = AppConfig(**updated_data)
                logger.info(
                    "Processor config updated: %s = %s", event.key, event.new_value
                )
            except Exception:
                logger.exception("Failed to update processor config for %s", event.key)

