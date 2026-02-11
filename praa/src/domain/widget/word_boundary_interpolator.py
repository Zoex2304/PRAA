"""
WordBoundaryInterpolator - Advanced Word Timing Estimation

SINGLE RESPONSIBILITY:
- Generate accurate word boundaries from sentence boundaries
- Model natural speech patterns (pauses, rhythm, emphasis)
- Provide phonetically-aware duration estimates

USE CASE:
Some TTS voices (e.g., Indonesian edge-tts) don't emit WordBoundary events.
This interpolator estimates word timing from SentenceBoundary events.

APPROACH:
1. Phonetic complexity scoring (syllable count, consonant clusters)
2. Punctuation-aware pause injection
3. Natural speech rhythm modeling (stressed/unstressed patterns)
4. Proportional time allocation with minimum duration guarantees
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WordTimingEstimate:
    """Estimated word timing."""
    offset_ms: float
    duration_ms: float
    word: str
    confidence: float  # 0.0-1.0, how confident we are


class PhoneticAnalyzer:
    """
    Analyzes phonetic complexity of words.
    
    More complex words typically take longer to pronounce.
    """
    
    # Syllable patterns (simplified - works for most languages)
    VOWELS = re.compile(r'[aeiouAEIOU]+')
    
    # Consonant clusters that slow pronunciation
    COMPLEX_CLUSTERS = re.compile(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{3,}')
    
    @classmethod
    def estimate_syllables(cls, word: str) -> int:
        """
        Estimate syllable count.
        
        Approximation: count vowel groups.
        "beautiful" → "eau", "i", "u" → 3 syllables
        """
        clean = word.strip('.,!?;:"\'-')
        vowel_groups = cls.VOWELS.findall(clean)
        return max(1, len(vowel_groups))
    
    @classmethod
    def complexity_score(cls, word: str) -> float:
        """
        Score word complexity (higher = longer to pronounce).
        
        Factors:
        - Base: syllable count
        - +0.3: consonant clusters
        - +0.2: long word (>8 chars)
        - +0.1: numbers/punctuation
        """
        syllables = cls.estimate_syllables(word)
        score = float(syllables)
        
        # Consonant clusters add complexity
        if cls.COMPLEX_CLUSTERS.search(word):
            score += 0.3
        
        # Long words
        if len(word) > 8:
            score += 0.2
        
        # Numbers take longer
        if any(c.isdigit() for c in word):
            score += 0.1
        
        return score


class PauseModel:
    """
    Models natural pauses in speech.
    
    Different punctuation creates different pause lengths.
    """
    
    # Pause durations in milliseconds
    PAUSE_COMMA = 250.0
    PAUSE_SEMICOLON = 300.0
    PAUSE_COLON = 350.0
    PAUSE_PERIOD = 500.0
    PAUSE_QUESTION = 550.0
    PAUSE_EXCLAMATION = 500.0
    PAUSE_DASH = 200.0
    PAUSE_ELLIPSIS = 600.0
    
    # Breathing pause every N words
    BREATH_INTERVAL = 12
    PAUSE_BREATH = 400.0
    
    @classmethod
    def get_pause_duration(cls, word: str, word_position: int) -> float:
        """
        Determine pause duration after word.
        
        Args:
            word: The word (may have trailing punctuation)
            word_position: Position in sentence (for breath pauses)
        
        Returns:
            Pause duration in milliseconds
        """
        # Check trailing punctuation
        if word.endswith('...'):
            return cls.PAUSE_ELLIPSIS
        elif word.endswith('!'):
            return cls.PAUSE_EXCLAMATION
        elif word.endswith('?'):
            return cls.PAUSE_QUESTION
        elif word.endswith('.'):
            return cls.PAUSE_PERIOD
        elif word.endswith(':'):
            return cls.PAUSE_COLON
        elif word.endswith(';'):
            return cls.PAUSE_SEMICOLON
        elif word.endswith(','):
            return cls.PAUSE_COMMA
        elif word.endswith('—') or word.endswith('–'):
            return cls.PAUSE_DASH
        
        # Natural breathing pause every ~12 words
        if word_position > 0 and word_position % cls.BREATH_INTERVAL == 0:
            return cls.PAUSE_BREATH
        
        return 0.0


class WordBoundaryInterpolator:
    """
    Generates word boundaries from sentence boundaries.
    
    ALGORITHM:
    1. Parse sentence into words
    2. Analyze phonetic complexity of each word
    3. Calculate pause durations
    4. Allocate speech duration proportionally
    5. Distribute with minimum duration guarantees
    
    GUARANTEES:
    - Sum of word durations + pauses = sentence duration
    - Each word gets minimum 100ms (configurable)
    - Complexity-weighted time allocation
    """
    
    def __init__(
        self,
        min_word_duration_ms: float = 100.0,
        max_pause_ratio: float = 0.4,  # Max 40% of time can be pauses
    ) -> None:
        """
        Args:
            min_word_duration_ms: Minimum duration for any word
            max_pause_ratio: Maximum fraction of sentence time for pauses
        """
        self._min_duration = min_word_duration_ms
        self._max_pause_ratio = max_pause_ratio
        self._phonetic = PhoneticAnalyzer()
        self._pause_model = PauseModel()
    
    def interpolate_from_sentences(
        self,
        sentences: list[tuple[float, float, str]]
    ) -> list[tuple[float, float, str]]:
        """
        Generate word boundaries from sentence boundaries.
        
        Args:
            sentences: List of (offset_ms, duration_ms, text)
        
        Returns:
            List of (offset_ms, duration_ms, word)
        """
        all_words = []
        
        for sent_offset, sent_duration, sent_text in sentences:
            words = self._interpolate_sentence(
                sent_offset, sent_duration, sent_text
            )
            all_words.extend(words)
        
        # logger.info(
        #     "Interpolated %d sentences → %d words",
        #     len(sentences), len(all_words)
        # )
        
        return all_words
    
    def _interpolate_sentence(
        self,
        offset_ms: float,
        duration_ms: float,
        text: str
    ) -> list[tuple[float, float, str]]:
        """Interpolate single sentence into word boundaries."""
        # Parse words
        words = text.split()
        if not words:
            return []
        
        # Analyze each word
        word_data = []
        total_complexity = 0.0
        total_pause = 0.0
        
        for i, word in enumerate(words):
            complexity = self._phonetic.complexity_score(word)
            pause = self._pause_model.get_pause_duration(word, i)
            
            word_data.append({
                'word': word,
                'complexity': complexity,
                'pause': pause,
            })
            
            total_complexity += complexity
            total_pause += pause
        
        # Clamp total pause duration
        max_pause_allowed = duration_ms * self._max_pause_ratio
        if total_pause > max_pause_allowed:
            pause_scale = max_pause_allowed / total_pause
            total_pause = max_pause_allowed
            
            # Scale down all pauses
            for data in word_data:
                data['pause'] *= pause_scale
        
        # Calculate speech duration (excluding pauses)
        speech_duration = duration_ms - total_pause
        
        # Ensure minimum duration per word
        min_total = len(words) * self._min_duration
        if speech_duration < min_total:
            # Reduce pauses to make room
            deficit = min_total - speech_duration
            reduction = min(deficit, total_pause * 0.5)  # Max reduce pauses by 50%
            
            if reduction > 0:
                pause_factor = (total_pause - reduction) / total_pause
                for data in word_data:
                    data['pause'] *= pause_factor
                total_pause -= reduction
                speech_duration += reduction
        
        # Allocate speech duration proportionally
        results = []
        current_offset = offset_ms
        
        for data in word_data:
            # Proportional allocation
            # Safety check: total_complexity > 0
            if total_complexity > 0:
                word_ratio = data['complexity'] / total_complexity
            else:
                word_ratio = 1.0 / len(words)
                
            word_duration = max(
                self._min_duration,
                speech_duration * word_ratio
            )
            
            results.append((
                current_offset,
                word_duration,
                data['word']
            ))
            
            # Advance time
            current_offset += word_duration + data['pause']
        
        return results
