"""
Unit Tests — LanguageDetector

Validates Indonesian vs English detection.
Note: These tests require lingua-language-detector to be installed.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.domain.processor.detector import LanguageDetector
from src.infrastructure.events import DetectedLanguage


@pytest.fixture
def detector():
    return LanguageDetector()


def test_detect_indonesian(detector):
    """Indonesian text should be detected as Indonesian."""
    result = detector.detect(
        "Selamat pagi, apa kabar hari ini? Saya ingin membaca artikel ini."
    )
    assert result == DetectedLanguage.INDONESIAN


def test_detect_english(detector):
    """English text should be detected as English."""
    result = detector.detect(
        "Good morning, how are you today? I want to read this article."
    )
    assert result == DetectedLanguage.ENGLISH


def test_detect_empty_text(detector):
    """Empty text should default to Indonesian."""
    result = detector.detect("")
    assert result == DetectedLanguage.INDONESIAN


def test_detect_whitespace(detector):
    """Whitespace-only text should default to Indonesian."""
    result = detector.detect("   \n\t  ")
    assert result == DetectedLanguage.INDONESIAN
