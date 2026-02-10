"""
Unit Tests — TextChunker

Validates sentence-boundary chunking for TTS with max length constraints.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.domain.processor.chunker import TextChunker


def test_short_text_no_split():
    """Text shorter than max_length should return as single chunk."""
    chunker = TextChunker()
    result = chunker.chunk("Hello world.", max_length=100)
    assert result == ["Hello world."]


def test_empty_text():
    """Empty text should return empty list."""
    chunker = TextChunker()
    assert chunker.chunk("", max_length=100) == []
    assert chunker.chunk("   ", max_length=100) == []


def test_sentence_boundary_split():
    """Text should be split at sentence boundaries."""
    chunker = TextChunker()
    text = "First sentence. Second sentence. Third sentence."
    result = chunker.chunk(text, max_length=35)
    assert len(result) >= 2
    # Each chunk should be within limit
    for chunk in result:
        assert len(chunk) <= 35


def test_long_sentence_word_split():
    """A single long sentence should fall back to word-level splitting."""
    chunker = TextChunker()
    text = " ".join(["word"] * 100)  # 100 words, ~500 chars
    result = chunker.chunk(text, max_length=50)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk) <= 50


def test_respects_max_length():
    """No chunk should exceed max_length."""
    chunker = TextChunker()
    text = "This is a test. " * 50
    result = chunker.chunk(text, max_length=100)
    for chunk in result:
        assert len(chunk) <= 100


def test_preserves_content():
    """Chunking should not lose any words."""
    chunker = TextChunker()
    text = "Hello world. Foo bar. Baz qux."
    result = chunker.chunk(text, max_length=20)
    combined = " ".join(result)
    assert "Hello" in combined
    assert "Foo" in combined
    assert "Baz" in combined


def test_single_chunk_for_exact_length():
    """Text exactly at max_length should return as one chunk."""
    chunker = TextChunker()
    text = "A" * 100
    result = chunker.chunk(text, max_length=100)
    assert len(result) == 1
