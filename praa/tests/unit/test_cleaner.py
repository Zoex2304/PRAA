"""
Unit Tests — TextCleaner

Validates text cleaning for TTS: URL removal, emoji stripping,
markdown cleanup, and whitespace normalization.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.domain.processor.cleaner import TextCleaner


def test_url_removal():
    """URLs should be stripped from text."""
    cleaner = TextCleaner()
    result = cleaner.clean("Check https://example.com for details")
    assert "https" not in result
    assert "example.com" not in result
    assert "Check" in result
    assert "details" in result


def test_email_removal():
    """Email addresses should be stripped."""
    cleaner = TextCleaner()
    result = cleaner.clean("Contact user@example.com for info")
    assert "user@example.com" not in result
    assert "Contact" in result


def test_emoji_removal():
    """Emojis should be stripped."""
    cleaner = TextCleaner()
    result = cleaner.clean("Hello 😊👍 World")
    assert "😊" not in result
    assert "👍" not in result
    assert "Hello" in result
    assert "World" in result


def test_markdown_removal():
    """Markdown symbols should be stripped."""
    cleaner = TextCleaner()
    result = cleaner.clean("**bold** and _italic_ and `code`")
    assert "**" not in result
    assert "_" not in result
    assert "`" not in result
    assert "bold" in result


def test_whitespace_normalization():
    """Multiple spaces/newlines should be collapsed."""
    cleaner = TextCleaner()
    result = cleaner.clean("Hello     World\n\n\n\nFoo")
    assert "     " not in result
    assert "\n\n\n\n" not in result


def test_empty_input():
    """Empty or whitespace-only input should return empty string."""
    cleaner = TextCleaner()
    assert cleaner.clean("") == ""
    assert cleaner.clean("   ") == ""
    assert cleaner.clean("\n\n") == ""


def test_clean_text_passthrough():
    """Clean text without noise should pass through mostly unchanged."""
    cleaner = TextCleaner()
    text = "This is a normal clean sentence."
    result = cleaner.clean(text)
    assert "This is a normal clean sentence." in result


def test_mixed_noise():
    """Mixed noise (URLs + emojis + markdown) should all be cleaned."""
    cleaner = TextCleaner()
    result = cleaner.clean("Check https://example.com 😊 this is **great** stuff")
    assert "https" not in result
    assert "😊" not in result
    assert "great" in result
    assert "stuff" in result
