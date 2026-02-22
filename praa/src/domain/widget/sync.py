"""
SyncController v2 - Calibrated Word-Level Synchronization

SINGLE RESPONSIBILITY:
- Map audio playback time to word positions
- Apply highlights based on external time provider
- Maintain word boundary index for efficient lookup

KEY IMPROVEMENTS vs v1:
1. Uses ITimeProvider instead of time.time() - eliminates timing drift
2. No internal pause/resume state - delegates to time provider
3. Binary search for large boundary sets (O(log n) vs O(n))
4. Explicit calibration step for latency compensation
"""

from __future__ import annotations

import logging
from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from src.domain.widget.time_provider import ITimeProvider, PlaybackPosition

logger = logging.getLogger(__name__)


class SyncState(Enum):
    """Sync lifecycle states."""
    IDLE = auto()      # No content loaded
    READY = auto()     # Boundaries loaded, waiting
    ACTIVE = auto()    # Currently syncing
    ERROR = auto()     # Sync failed
    PAUSED = auto()    # Legacy state mapping (provider handles pause)


@dataclass(frozen=True)
class WordBoundary:
    """Immutable word boundary with timing and text position."""
    offset_ms: float       # Time offset from chunk start
    duration_ms: float     # Word duration
    word: str             # The word text
    text_offset: int      # Character position in chunk
    text_length: int      # Character length
    
    @property
    def end_ms(self) -> float:
        """End time of word."""
        return self.offset_ms + self.duration_ms
    
    @classmethod
    def from_tuple(cls, data: tuple) -> WordBoundary:
        """Create from TTS service tuple."""
        if len(data) < 5:
            raise ValueError(f"Invalid boundary data: {data}")
        return cls(
            offset_ms=float(data[0]),
            duration_ms=float(data[1]),
            word=str(data[2]),
            text_offset=int(data[3]),
            text_length=int(data[4]),
        )


class SyncController:
    """
    Maps audio playback position to word highlights.
    
    ARCHITECTURE:
    - Depends on ITimeProvider for playback position
    - Maintains sorted word boundaries per chunk
    - Provides efficient time → word lookup
    - Stateless sync logic (state lives in time provider)
    
    GUARANTEES:
    - No race conditions (single-threaded UI updates)
    - Accurate sync via calibrated time provider
    - Efficient lookup even with 1000+ words
    """
    
    def __init__(
        self,
        time_provider: ITimeProvider,
        highlight_callback: Callable[[int, int, int], None],
    ) -> None:
        """
        Args:
            time_provider: Source of audio playback position
            highlight_callback: fn(chunk_idx, rel_start, rel_end) -> None
        """
        self._time_provider = time_provider
        self._highlight = highlight_callback
        
        # State
        self._state = SyncState.IDLE
        
        # Word boundaries: chunk_idx → sorted list of boundaries
        self._boundaries: dict[int, list[WordBoundary]] = {}
        
        # Offset cache for efficient binary search
        # chunk_idx → list of offset_ms values
        self._offset_cache: dict[int, list[float]] = {}
        
        # Current highlight position
        self._last_highlighted_word: tuple[int, int] = (-1, -1)  # (chunk, word_idx)
        
        # Promise tracking for async boundary loading
        self._pending_chunks: set[int] = set()
    
    # ----------------------------------------------------------------
    # PUBLIC API: Boundary Management
    # ----------------------------------------------------------------
    
    def load_boundaries(self, chunk_idx: int, boundaries: list[tuple]) -> None:
        """
        Load word boundaries for a chunk.
        
        Can be called before or after playback starts.
        """
        if not boundaries:
            logger.warning("Empty boundaries for chunk %d", chunk_idx)
            return
        
        try:
            # Parse and sort by offset
            parsed = [WordBoundary.from_tuple(b) for b in boundaries]
            parsed.sort(key=lambda w: w.offset_ms)
            
            self._boundaries[chunk_idx] = parsed
            
            # Build offset cache for binary search
            self._offset_cache[chunk_idx] = [w.offset_ms for w in parsed]
            
            # Resolve pending promise
            if chunk_idx in self._pending_chunks:
                self._pending_chunks.remove(chunk_idx)
                logger.info(
                    "Boundaries loaded for pending chunk %d (%d words)",
                    chunk_idx, len(parsed)
                )
            else:
                logger.debug(
                    "Boundaries loaded for chunk %d (%d words)",
                    chunk_idx, len(parsed)
                )
            
            if self._state == SyncState.IDLE:
                self._state = SyncState.READY
                
        except Exception:
            logger.exception("Failed to parse boundaries for chunk %d", chunk_idx)
            self._state = SyncState.ERROR
    
    def has_boundaries(self, chunk_idx: int) -> bool:
        """Check if boundaries are ready for chunk."""
        return chunk_idx in self._boundaries
    
    def wait_for_boundaries(self, chunk_idx: int) -> None:
        """
        Register that we're waiting for boundaries.
        
        Use this when starting playback before boundaries arrive.
        """
        if chunk_idx not in self._boundaries:
            self._pending_chunks.add(chunk_idx)
            logger.info("Registered promise for chunk %d boundaries", chunk_idx)
    
    # ----------------------------------------------------------------
    # PUBLIC API: Synchronization
    # ----------------------------------------------------------------
    
    def tick(self) -> bool:
        return self.update_sync()

    def update_sync(self) -> bool:
        """
        Update word highlight based on current playback position.
        
        Call this from UI thread timer (every 50-100ms).
        
        Returns:
            True if sync is active and should continue
            False if playback stopped or no position available
        """
        # Get current position from audio player
        position = self._time_provider.get_position()
        
        if position is None:
            return False
        
        if not position.is_playing:
            # Keep last highlight when paused
            return True
        
        # Check if boundaries are available
        chunk_idx = position.chunk_index
        if chunk_idx not in self._boundaries:
            if chunk_idx not in self._pending_chunks:
                # Only log periodically or once per chunk to avoid spam? 
                # For now just log (assuming update rate 50ms is manageable log volume or rely on log level)
                # Better: only log if we haven't warned recently.
                pass
            return True  # Keep trying
        
        # Find current word
        word_idx = self._find_word_at_time(chunk_idx, position.position_ms)
        
        if word_idx is None:
            # Position before first word or after last word
            return True
        
        # Update highlight if word changed
        if (chunk_idx, word_idx) != self._last_highlighted_word:
            self._apply_highlight(chunk_idx, word_idx)
            self._last_highlighted_word = (chunk_idx, word_idx)
        
        self._state = SyncState.ACTIVE
        return True
    
    def clear_highlight(self) -> None:
        """Remove current highlight."""
        self._last_highlighted_word = (-1, -1)
        # Delegate to renderer via callback with invalid indices if needed
        # Or let renderer handle clear separately 
    
    def reset(self) -> None:
        """Reset all sync state (new session)."""
        self._boundaries.clear()
        self._offset_cache.clear()
        self._pending_chunks.clear()
        self._last_highlighted_word = (-1, -1)
        self._state = SyncState.IDLE
        logger.info("SyncController reset")
    
    # ----------------------------------------------------------------
    # QUERY API
    # ----------------------------------------------------------------
    
    @property
    def state(self) -> SyncState:
        """Current sync state."""
        return self._state
    
    @property
    def is_active(self) -> bool:
        """Is sync currently active?"""
        return self._state == SyncState.ACTIVE and self._time_provider.is_playing()
    
    def get_current_position(self) -> tuple[int, int]:
        """Get (chunk_index, word_idx) of last highlight."""
        return self._last_highlighted_word
    
    def get_word_count(self, chunk_idx: int) -> int:
        """Get number of words in chunk."""
        return len(self._boundaries.get(chunk_idx, []))
    
    # ----------------------------------------------------------------
    # PRIVATE: Implementation
    # ----------------------------------------------------------------
    
    def _find_word_at_time(self, chunk_idx: int, position_ms: float) -> Optional[int]:
        """
        Find word index at given playback position.
        
        Uses binary search for O(log n) complexity.
        
        Returns:
            Word index if position is within word boundaries
            None if position is outside all words
        """
        if chunk_idx not in self._offset_cache:
            return None
        
        offsets = self._offset_cache[chunk_idx]
        boundaries = self._boundaries[chunk_idx]
        
        if not offsets:
            return None
        
        # Binary search for word containing position_ms
        idx = bisect_right(offsets, position_ms)
        
        if idx == 0:
            # Before first word
            return None
        
        word_idx = idx - 1
        
        # Verify position is within word duration (including some tolerance)
        word = boundaries[word_idx]
        tolerance_ms = 100.0  # Allow 100ms slop for timing drift
        
        if position_ms <= word.end_ms + tolerance_ms:
            return word_idx
        
        # Position is between words
        return None
    
    def _apply_highlight(self, chunk_idx: int, word_idx: int) -> None:
        """Apply highlight for specified word."""
        if chunk_idx not in self._boundaries:
            return
        
        boundaries = self._boundaries[chunk_idx]
        if word_idx >= len(boundaries):
            return
        
        word = boundaries[word_idx]
        
        # Callback with relative offsets
        self._highlight(chunk_idx, word.text_offset, word.text_offset + word.text_length)
        
        # logger.debug(
        #     "Highlight: chunk=%d, word=%d/%d, text='%s', offset=%.1fms",
        #     chunk_idx, word_idx, len(boundaries), word.word, word.offset_ms
        # )


# ----------------------------------------------------------------
# DIAGNOSTIC UTILITIES
# ----------------------------------------------------------------

class SyncDiagnostics:
    """
    Diagnostic tool for analyzing sync accuracy.
    
    Use this to debug timing issues.
    """
    
    def __init__(self, controller: SyncController, time_provider: ITimeProvider) -> None:
        self._controller = controller
        self._time_provider = time_provider
        self._samples: list[tuple[float, int, int]] = []  # (timestamp, chunk, word)
    
    def sample(self) -> None:
        """Take a diagnostic sample of current sync state."""
        position = self._time_provider.get_position()
        if position:
            chunk, word = self._controller.get_current_position()
            self._samples.append((position.system_timestamp, chunk, word))
    
    def report(self) -> dict:
        """Generate diagnostic report."""
        if not self._samples:
            return {"error": "No samples collected"}
        
        # Calculate timing stats
        intervals = []
        for i in range(1, len(self._samples)):
            delta = self._samples[i][0] - self._samples[i-1][0]
            intervals.append(delta)
        
        return {
            "total_samples": len(self._samples),
            "avg_interval_ms": sum(intervals) / len(intervals) * 1000 if intervals else 0,
            "min_interval_ms": min(intervals) * 1000 if intervals else 0,
            "max_interval_ms": max(intervals) * 1000 if intervals else 0,
            "word_changes": len(set(s[2] for s in self._samples)),
        }
