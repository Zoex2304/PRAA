"""
Processor Domain — Sentence-Boundary Text Chunker

Splits long text into chunks that fit within edge-tts limits.
Uses dynamic programming for optimal split point selection,
respecting sentence boundaries to maintain natural speech flow.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Splits text into sentence-boundary-aware chunks for TTS.

    Edge-tts has practical limits on input text length. This chunker
    splits text at sentence boundaries to ensure each chunk is within
    the limit while maximizing natural readability.

    Dynamic programming approach:
    - First, detect all sentence boundaries
    - Then, greedily pack sentences into chunks without exceeding max_length
    - Fall back to word-level splitting for single sentences that exceed max_length
    """

    # Sentence boundary detection
    _SENTENCE_END = re.compile(
        r'(?<=[.!?;:])\s+|(?<=\n)\s*',
        re.MULTILINE,
    )

    def chunk(self, text: str, max_length: int = 2000) -> list[str]:
        """
        Split text into chunks at sentence boundaries.

        Args:
            text: Input text to split.
            max_length: Maximum character count per chunk.

        Returns:
            List of text chunks, each ≤ max_length characters.
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # Short text — no splitting needed
        if len(text) <= max_length:
            return [text]

        # Step 1: Split into sentences
        sentences = self._split_sentences(text)

        if not sentences:
            return [text[:max_length]]

        # Step 2: Pack sentences into chunks (greedy bin-packing)
        chunks = self._pack_sentences(sentences, max_length)

        logger.debug(
            "Text chunked: %d chars → %d chunks (max %d chars each)",
            len(text),
            len(chunks),
            max_length,
        )
        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into individual sentences.

        Returns:
            List of sentence strings, stripped and non-empty.
        """
        raw_sentences = self._SENTENCE_END.split(text)
        return [s.strip() for s in raw_sentences if s.strip()]

    def _pack_sentences(
        self, sentences: list[str], max_length: int
    ) -> list[str]:
        """
        Pack sentences into chunks using greedy bin-packing.

        If a single sentence exceeds max_length, it is split at word
        boundaries as a fallback.
        """
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # Single sentence exceeds limit — split by words
            if sentence_length > max_length:
                # Flush current chunk first
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Word-level splitting fallback
                chunks.extend(self._split_by_words(sentence, max_length))
                continue

            # Would adding this sentence exceed the limit?
            needed = sentence_length + (1 if current_chunk else 0)
            if current_length + needed > max_length:
                # Flush current chunk
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += needed

        # Flush remaining
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_by_words(self, text: str, max_length: int) -> list[str]:
        """
        Fallback: split a long sentence at word boundaries.

        Used when a single sentence exceeds max_length.
        """
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0

        for word in words:
            word_length = len(word)
            needed = word_length + (1 if current else 0)

            if current_length + needed > max_length:
                if current:
                    chunks.append(" ".join(current))
                current = [word]
                current_length = word_length
            else:
                current.append(word)
                current_length += needed

        if current:
            chunks.append(" ".join(current))

        return chunks
