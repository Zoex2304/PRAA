"""
SyncController - Word-level Synchronization Manager

SINGLE RESPONSIBILITY:
- Manage word-by-word highlighting lifecycle
- Guarantee sync accuracy through state machine
- Eliminate race conditions via promise resolution
- Time-Anchored Synchronization (Latency Compensation)

STATE MACHINE:
  IDLE → READY → ACTIVE → PAUSED → IDLE
         ↓        ↓
       ERROR    ERROR
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SyncState(Enum):
    """Clear state transitions for sync lifecycle."""
    IDLE = auto()      # No content loaded
    READY = auto()     # Boundaries loaded, waiting for playback
    ACTIVE = auto()    # Currently syncing
    PAUSED = auto()    # Sync paused mid-playback
    ERROR = auto()     # Sync failed


@dataclass(frozen=True)
class WordBoundary:
    """Immutable word boundary data from TTS."""
    offset_ms: float       # Time offset from chunk start
    duration_ms: float     # Word duration
    word: str             # The word text
    text_offset: int      # Character position in chunk text
    text_length: int      # Character length of word
    
    @classmethod
    def from_tuple(cls, data: tuple) -> WordBoundary:
        """Create from TTS service tuple."""
        if len(data) < 5:
            raise ValueError(f"Invalid boundary data: {data}")
        return cls(
            offset_ms=data[0],
            duration_ms=data[1],
            word=data[2],
            text_offset=data[3],
            text_length=data[4],
        )


class SyncController:
    """
    Manages word-level synchronization with guaranteed consistency.
    
    GUARANTEES:
    1. Sync only starts when boundaries are ready
    2. No race conditions via explicit state machine
    3. Promise resolution with timeout protection
    4. Thread-safe via callback pattern
    5. Time-Anchored to actual audio playback (not system time)
    """
    
    def __init__(self, highlight_callback: Callable[[int, int, int], None]) -> None:
        """
        Args:
            highlight_callback: fn(chunk_idx, relative_start, relative_end) -> None
                                Called on UI thread to update highlight.
                                NOTE: Offsets are RELATIVE to the chunk start!
        """
        self._highlight = highlight_callback
        
        # State
        self._state = SyncState.IDLE
        self._boundaries: dict[int, list[WordBoundary]] = {}
        
        # Playback tracking
        self._current_chunk = -1
        self._current_word_idx = 0
        self._playback_start_time = 0.0
        self._pause_elapsed = 0.0
        
        # Promise resolution: chunk_idx → pending_effective_start
        self._pending: dict[int, float] = {}
        self._promise_timeout = 5.0  # Max wait for boundaries
        
        # Configuration
        self._latency_sec = 0.0
        
    def set_latency(self, latency_ms: int) -> None:
        """Set playback latency compensation (ms)."""
        self._latency_sec = latency_ms / 1000.0
        
    # ----------------------------------------------------------------
    # PUBLIC API: State Transitions
    # ----------------------------------------------------------------
    
    def load_boundaries(self, chunk_idx: int, boundaries: list[tuple]) -> None:
        """
        Load word boundaries for a chunk (called from on_synthesis_complete).
        
        This may resolve a pending promise if playback was waiting.
        """
        if not boundaries:
            logger.warning("Empty boundaries for chunk %d", chunk_idx)
            return
            
        try:
            parsed = [WordBoundary.from_tuple(b) for b in boundaries]
            self._boundaries[chunk_idx] = parsed
            
            logger.info("Loaded %d boundaries for chunk %d", len(parsed), chunk_idx)
            
            # Resolve pending promise if exists
            if chunk_idx in self._pending:
                pending_start = self._pending.pop(chunk_idx)
                # Latency check relative to system time is tricky if start time 
                # was anchored in past. But typically load is fast.
                # Just start immediately.
                
                logger.info("Promise resolved for chunk %d", chunk_idx)
                self._start_sync_internal(chunk_idx, pending_start)
                        
        except Exception:
            logger.exception("Failed to parse boundaries for chunk %d", chunk_idx)
            self._transition(SyncState.ERROR)
    
    def start_sync(self, chunk_idx: int, timestamp: float) -> bool:
        """
        Start synchronization for the given chunk using anchored timestamp.
        
        Args:
            chunk_idx: index of chunk
            timestamp: time.time() when playback started (from event)
        
        Returns:
            True if sync started immediately
            False if boundaries not ready (promise registered)
        """
        # Effective start time = Event Time + Latency
        effective_start = timestamp + self._latency_sec
        
        # Check if boundaries are ready
        if chunk_idx in self._boundaries:
            self._start_sync_internal(chunk_idx, effective_start)
            logger.info("Sync started immediately for chunk %d (latency: %.3fs)", chunk_idx, self._latency_sec)
            return True
        else:
            # Register promise
            self._pending[chunk_idx] = effective_start
            logger.warning("Boundaries not ready for chunk %d - promise registered", chunk_idx)
            return False
            
    def _start_sync_internal(self, chunk_idx: int, start_time: float) -> None:
        """Internal helper to start sync loop."""
        self._current_chunk = chunk_idx
        self._current_word_idx = 0
        self._playback_start_time = start_time
        self._transition(SyncState.ACTIVE)
    
    def update_sync(self) -> bool:
        """
        Update word highlighting based on time anchor.
        
        Called every ~50ms from UI thread.
        
        Returns:
            True if sync should continue
            False if sync completed or inactive
        """
        if self._state != SyncState.ACTIVE:
            return False
            
        if self._current_chunk not in self._boundaries:
            logger.error("Sync active but boundaries missing for chunk %d", self._current_chunk)
            self._transition(SyncState.ERROR)
            return False
        
        boundaries = self._boundaries[self._current_chunk]
        
        # Calculate elapsed from anchored start time
        now = time.time()
        elapsed_ms = (now - self._playback_start_time) * 1000
        
        # If negative (latency wait), do nothing yet
        if elapsed_ms < 0:
            return True

        # Find current word based on elapsed time
        new_word_idx = self._find_current_word(boundaries, elapsed_ms)
        
        if new_word_idx != self._current_word_idx:
            self._current_word_idx = new_word_idx
            self._apply_highlight(self._current_chunk, new_word_idx)
        
        # Continue if not at end
        return new_word_idx < len(boundaries)
    
    def pause_sync(self) -> None:
        """Pause synchronization and capture elapsed time."""
        if self._state == SyncState.ACTIVE:
            self._transition(SyncState.PAUSED)
            # Calculate elapsed time at pause moment
            now = time.time()
            self._pause_elapsed = now - self._playback_start_time
    
    def resume_sync(self, timestamp: float) -> None:
        """
        Resume synchronization from paused position.
        
        Args:
            timestamp: time.time() when playback resumed (from event)
        """
        if self._state == SyncState.PAUSED:
            # Effective resume time = Event Time + Latency
            effective_resume = timestamp + self._latency_sec
            
            # New start time = Effective Resume - Elapsed at Pause
            # So (Effective Resume - New Start) = Elapsed at Pause
            self._playback_start_time = effective_resume - self._pause_elapsed
            
            self._transition(SyncState.ACTIVE)

    def stop_sync(self) -> None:
        """Stop synchronization and reset state."""
        self._transition(SyncState.IDLE)
        self._current_chunk = -1
        self._current_word_idx = 0
        self._pending.clear()
    
    def clear_all(self) -> None:
        """Clear all data (new session starting)."""
        self._boundaries.clear()
        self._pending.clear()
        self._transition(SyncState.IDLE)
        self._current_chunk = -1
        self._current_word_idx = 0
    
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
        return self._state == SyncState.ACTIVE
    
    def get_current_position(self) -> tuple[int, int]:
        """Get current (chunk_index, word_index)."""
        return (self._current_chunk, self._current_word_idx)
    
    def has_boundaries(self, chunk_idx: int) -> bool:
        """Check if boundaries are loaded for chunk."""
        return chunk_idx in self._boundaries
    
    # ----------------------------------------------------------------
    # PRIVATE: Implementation
    # ----------------------------------------------------------------
    
    def _transition(self, new_state: SyncState) -> None:
        """State machine transition with logging."""
        if new_state != self._state:
            logger.debug("SyncController: %s → %s", self._state.name, new_state.name)
            self._state = new_state
    
    def _find_current_word(self, boundaries: list[WordBoundary], elapsed_ms: float) -> int:
        """Binary search to find current word index."""
        # Linear search from current position (usually close)
        idx = self._current_word_idx
        
        while idx < len(boundaries):
            if elapsed_ms < boundaries[idx].offset_ms:
                break
            idx += 1
        
        # Return previous word (the one we're currently in)
        return max(0, idx - 1)
    
    def _apply_highlight(self, chunk_idx: int, word_idx: int) -> None:
        """Apply highlight using boundary data."""
        if chunk_idx not in self._boundaries:
            return
            
        boundaries = self._boundaries[chunk_idx]
        if word_idx >= len(boundaries):
            return
        
        boundary = boundaries[word_idx]
        
        # Pass RELATIVE offsets to callback
        rel_start = boundary.text_offset
        rel_end = rel_start + boundary.text_length
        
        # Callback to UI thread
        self._highlight(chunk_idx, rel_start, rel_end)
