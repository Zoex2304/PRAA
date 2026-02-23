from __future__ import annotations

import logging

from src.infrastructure.events import DetectedLanguage

logger = logging.getLogger(__name__)

# Lazy import to avoid slow startup — lingua loads language models on init
_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        try:
            from lingua import Language, LanguageDetectorBuilder

            _detector = (
                LanguageDetectorBuilder.from_languages(
                    Language.INDONESIAN, Language.ENGLISH
                )
                .with_preloaded_language_models()
                .build()
            )
            logger.info("Language detector initialized (ID + EN)")
        except ImportError:
            logger.warning(
                "lingua-language-detector not installed, "
                "defaulting to Indonesian for all text"
            )
    return _detector


class LanguageDetector:
    def detect(self, text: str) -> DetectedLanguage:
        if not text or not text.strip():
            return DetectedLanguage.INDONESIAN

        detector = _get_detector()
        if detector is None:
            return DetectedLanguage.INDONESIAN

        try:
            from lingua import Language

            result = detector.detect_language_of(text)

            if result == Language.ENGLISH:
                logger.debug("Language detected: English")
                return DetectedLanguage.ENGLISH
            elif result == Language.INDONESIAN:
                logger.debug("Language detected: Indonesian")
                return DetectedLanguage.INDONESIAN
            else:
                logger.debug("Language uncertain, defaulting to Indonesian")
                return DetectedLanguage.INDONESIAN

        except Exception:
            logger.exception("Language detection failed, defaulting to Indonesian")
            return DetectedLanguage.INDONESIAN
