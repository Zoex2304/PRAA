from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

class TextChunker:
    _SENTENCE_END = re.compile(
        r'(?<=[.!?;:])\s+|(?<=\n)\s*',
        re.MULTILINE,
    )

    def chunk(self, text: str, max_length: int = 2000) -> list[str]:
        if not text or not text.strip():
            return []
        
        text = text.strip()
        
        if len(text) <= max_length:
            return [text]
        
        sentences = self._split_sentences(text)
        if not sentences:
            return [text[:max_length]]
        
        chunks = self._pack_sentences(sentences, max_length)
        
        logger.debug(
            "Text chunked: %d chars → %d chunks (max %d chars each)",
            len(text),
            len(chunks),
            max_length,
        )
        
        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        raw_sentences = self._SENTENCE_END.split(text)
        return [s.strip() for s in raw_sentences if s.strip()]

    def _pack_sentences(
        self, sentences: list[str], max_length: int
    ) -> list[str]:
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)
            
            if sentence_length > max_length:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                chunks.extend(self._split_by_words(sentence, max_length))
                continue
            
            needed = sentence_length + (1 if current_chunk else 0)
            
            if current_length + needed > max_length:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += needed
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks

    def _split_by_words(self, text: str, max_length: int) -> list[str]:
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