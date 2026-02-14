"""
PlaybackStateManager - Deterministic Playback State Machine

SINGLE RESPONSIBILITY:
- Manage playback state transitions
- Coordinate sync lifecycle with audio playback
- Eliminate race conditions via explicit state guards
- Provide clear query API for UI

STATE MACHINE:
  IDLE → PROCESSING → READY → PLAYING → PAUSED → IDLE
         ↓            ↓        ↓         ↓
       ERROR        ERROR    ERROR     ERROR

GUARANTEES:
- All state transitions are logged
- Invalid transitions are prevented
- State queries are thread-safe (immutable)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class PlaybackState(Enum):
    """Application playback states."""
    IDLE = auto()          # No content, waiting for input
    PROCESSING = auto()    # TTS synthesis in progress
    READY = auto()         # Content ready, not playing
    PLAYING = auto()       # Audio playing
    PAUSED = auto()        # Playback paused
    ERROR = auto()         # Error occurred


@dataclass(frozen=True)
class StateInfo:
    """Immutable state information for UI."""
    state: PlaybackState
    status_text: str
    status_color: str
    can_play: bool
    can_pause: bool
    can_stop: bool
    can_resume: bool
    background_processing: bool = False


# Status colors
STATUS_IDLE = "#64748b"
STATUS_PROCESSING = "#f59e0b"
STATUS_PLAYING = "#22c55e"
STATUS_ERROR = "#ef4444"
ACCENT = "#0f9d9a"


class PlaybackStateManager:
    """
    Manages application playback state with deterministic transitions.
    
    PRINCIPLES:
    - Single source of truth for playback state
    - Guard clauses prevent invalid transitions
    - Immutable state info for thread-safety
    - Clear separation from audio/sync controllers
    """
    
    def __init__(self) -> None:
        self._state = PlaybackState.IDLE
        self._has_content = False
        self._total_chunks = 0
        self._current_chunk = 0
        self._is_processing = False
        
    # ----------------------------------------------------------------
    # PUBLIC API: State Transitions
    # ----------------------------------------------------------------
    
    def start_processing(self, total_chunks: int) -> None:
        """Start TTS processing."""
        if self._state not in (PlaybackState.IDLE, PlaybackState.READY):
            logger.warning("Cannot start processing from state %s", self._state.name)
            return
        
        self._total_chunks = total_chunks
        self._has_content = True
        self._transition(PlaybackState.PROCESSING)
    
    def processing_complete(self) -> None:
        """TTS processing finished successfully."""
        if self._state != PlaybackState.PROCESSING:
            logger.warning("Processing complete called from state %s", self._state.name)
            return
        
        self._transition(PlaybackState.READY)
    
    def start_playback(self, chunk_idx: int = 0) -> bool:
        """
        Start playback.
        
        Returns:
            True if playback started
            False if not allowed from current state
        """
        if self._state not in (PlaybackState.READY, PlaybackState.PAUSED):
            logger.warning("Cannot start playback from state %s", self._state.name)
            return False
        
        if not self._has_content:
            logger.warning("Cannot start playback: no content loaded")
            return False
        
        self._current_chunk = chunk_idx
        self._transition(PlaybackState.PLAYING)
        return True
    
    def pause_playback(self) -> bool:
        """
        Pause playback.
        
        Returns:
            True if paused
            False if not allowed from current state
        """
        if self._state != PlaybackState.PLAYING:
            logger.warning("Cannot pause from state %s", self._state.name)
            return False
        
        self._transition(PlaybackState.PAUSED)
        return True
    
    def resume_playback(self) -> bool:
        """
        Resume playback from paused state.
        
        Returns:
            True if resumed
            False if not allowed from current state
        """
        if self._state != PlaybackState.PAUSED:
            logger.warning("Cannot resume from state %s", self._state.name)
            return False
        
        self._transition(PlaybackState.PLAYING)
        return True
    
    def stop_playback(self) -> None:
        """Stop playback and return to ready state."""
        if self._state not in (PlaybackState.PLAYING, PlaybackState.PAUSED):
            logger.warning("Cannot stop from state %s", self._state.name)
            return
        
        self._transition(PlaybackState.READY if self._has_content else PlaybackState.IDLE)
    
    def complete_playback(self) -> None:
        """Mark playback as completed."""
        if self._state != PlaybackState.PLAYING:
            logger.warning("Playback complete called from state %s", self._state.name)
            return
        
        self._transition(PlaybackState.READY)
    
    def error_occurred(self, message: str = "") -> None:
        """Transition to error state."""
        logger.error("Playback error: %s (from state %s)", message, self._state.name)
        self._transition(PlaybackState.ERROR)
    
    def reset(self) -> None:
        """Reset to idle state (new session)."""
        self._has_content = False
        self._total_chunks = 0
        self._current_chunk = 0
        self._transition(PlaybackState.IDLE)
    
    # ----------------------------------------------------------------
    # QUERY API: Thread-Safe State Queries
    # ----------------------------------------------------------------
    
    @property
    def state(self) -> PlaybackState:
        """Current playback state."""
        return self._state
    
    @property
    def is_playing(self) -> bool:
        """Is audio currently playing?"""
        return self._state == PlaybackState.PLAYING
    
    @property
    def is_paused(self) -> bool:
        """Is playback paused?"""
        return self._state == PlaybackState.PAUSED
    
    @property
    def is_idle(self) -> bool:
        """Is system idle (no content)?"""
        return self._state == PlaybackState.IDLE
    
    @property
    def has_content(self) -> bool:
        """Is content loaded and ready?"""
        return self._has_content
    
    def get_state_info(self) -> StateInfo:
        """
        Get immutable state information for UI.
        
        Thread-safe: Returns frozen dataclass.
        """
        state_map = {
            PlaybackState.IDLE: ("Idle", STATUS_IDLE, False, False, False, False),
            PlaybackState.PROCESSING: ("Processing...", STATUS_PROCESSING, False, False, False, False),
            PlaybackState.READY: ("Ready", ACCENT, True, False, False, False),
            PlaybackState.PLAYING: ("Playing...", STATUS_PLAYING, False, True, True, False),
            PlaybackState.PAUSED: ("Paused", STATUS_PROCESSING, False, False, True, True),
            PlaybackState.ERROR: ("Error", STATUS_ERROR, False, False, False, False),
        }
        
        text, color, play, pause, stop, resume = state_map[self._state]
        
        return StateInfo(
            state=self._state,
            status_text=text,
            status_color=color,
            can_play=play,
            can_pause=pause,
            can_stop=stop,
            can_resume=resume,
        )
    
    # ----------------------------------------------------------------
    # PRIVATE: Implementation
    # ----------------------------------------------------------------
    
    def _transition(self, new_state: PlaybackState) -> None:
        """State transition with logging."""
        if new_state != self._state:
            logger.info("Playback: %s → %s", self._state.name, new_state.name)
            self._state = new_state
            
            # Auto-update background processing flag if we leave processing but haven't finished?
            # actually we handle that via separate flags now.
            
    def set_processing(self, is_processing: bool) -> None:
        """Update background processing status."""
        self._is_processing = is_processing
        # If we are IDLE and start processing, we go to PROCESSING
        if self._state == PlaybackState.IDLE and is_processing:
            self._transition(PlaybackState.PROCESSING)
        # If we stop processing and are in PROCESSING state, we go to READY
        elif self._state == PlaybackState.PROCESSING and not is_processing:
            self._transition(PlaybackState.READY)

    def start_processing(self, total_chunks: int) -> None:
        """Start TTS processing."""
        self._total_chunks = total_chunks
        self._has_content = True
        self.set_processing(True)
    
    def processing_complete(self) -> None:
        """TTS processing finished successfully."""
        self.set_processing(False)
    
    def start_playback(self, chunk_idx: int = 0) -> bool:
        """
        Start playback.
        
        Returns:
            True if playback started
            False if not allowed from current state
        """
        # Allow start if READY or PAUSED or PROCESSING (if we have content)
        if self._state not in (PlaybackState.READY, PlaybackState.PAUSED, PlaybackState.PROCESSING):
            logger.warning("Cannot start playback from state %s", self._state.name)
            return False
        
        if not self._has_content:
            logger.warning("Cannot start playback: no content loaded")
            return False
        
        self._current_chunk = chunk_idx
        self._transition(PlaybackState.PLAYING)
        return True
    
    def pause_playback(self) -> bool:
        """
        Pause playback.
        
        Returns:
            True if paused
            False if not allowed from current state
        """
        if self._state != PlaybackState.PLAYING:
            logger.warning("Cannot pause from state %s", self._state.name)
            return False
        
        self._transition(PlaybackState.PAUSED)
        return True
    
    def resume_playback(self) -> bool:
        """
        Resume playback from paused state.
        
        Returns:
            True if resumed
            False if not allowed from current state
        """
        if self._state != PlaybackState.PAUSED:
            logger.warning("Cannot resume from state %s", self._state.name)
            return False
        
        self._transition(PlaybackState.PLAYING)
        return True
    
    def stop_playback(self) -> None:
        """Stop playback and return to ready (or processing) state."""
        if self._state not in (PlaybackState.PLAYING, PlaybackState.PAUSED):
            logger.warning("Cannot stop from state %s", self._state.name)
            return
        
        # Return to PROCESSING if we are still processing, otherwise READY
        next_state = PlaybackState.PROCESSING if self._is_processing else PlaybackState.READY
        if not self._has_content:
            next_state = PlaybackState.IDLE
            
        self._transition(next_state)
    
    def complete_playback(self) -> None:
        """Mark playback as completed."""
        if self._state != PlaybackState.PLAYING:
            logger.warning("Playback complete called from state %s", self._state.name)
            return
        
        # Return to PROCESSING if still processing, else READY
        next_state = PlaybackState.PROCESSING if self._is_processing else PlaybackState.READY
        self._transition(next_state)
    
    def error_occurred(self, message: str = "") -> None:
        """Transition to error state."""
        logger.error("Playback error: %s (from state %s)", message, self._state.name)
        self._transition(PlaybackState.ERROR)
    
    def reset(self) -> None:
        """Reset to idle state (new session)."""
        self._has_content = False
        self._total_chunks = 0
        self._current_chunk = 0
        self._is_processing = False
        self._transition(PlaybackState.IDLE)
    
    # ----------------------------------------------------------------
    # QUERY API: Thread-Safe State Queries
    # ----------------------------------------------------------------
    
    @property
    def state(self) -> PlaybackState:
        """Current playback state."""
        return self._state
    
    @property
    def is_playing(self) -> bool:
        """Is audio currently playing?"""
        return self._state == PlaybackState.PLAYING
    
    @property
    def is_paused(self) -> bool:
        """Is playback paused?"""
        return self._state == PlaybackState.PAUSED
    
    @property
    def is_idle(self) -> bool:
        """Is system idle (no content)?"""
        return self._state == PlaybackState.IDLE
    
    @property
    def has_content(self) -> bool:
        """Is content loaded and ready?"""
        return self._has_content

    @property
    def is_processing(self) -> bool:
        """Is synthesis running in background?"""
        return self._is_processing
    
    def get_state_info(self) -> StateInfo:
        """
        Get immutable state information for UI.
        
        Thread-safe: Returns frozen dataclass.
        """
        # Base state info
        state_map = {
            PlaybackState.IDLE: ("Idle", STATUS_IDLE, False, False, False, False),
            PlaybackState.PROCESSING: ("Processing...", STATUS_PROCESSING, False, False, False, False),
            PlaybackState.READY: ("Ready", ACCENT, True, False, False, False),
            PlaybackState.PLAYING: ("Playing", STATUS_PLAYING, False, True, True, False),
            PlaybackState.PAUSED: ("Paused", STATUS_PROCESSING, False, False, True, True),
            PlaybackState.ERROR: ("Error", STATUS_ERROR, False, False, False, False),
        }
        
        text, color, play, pause, stop, resume = state_map[self._state]
        
        # Dynamic overrides based on background processing
        if self._state == PlaybackState.PLAYING and self._is_processing:
            text = "Playing (Processing...)"
        elif self._state == PlaybackState.PAUSED and self._is_processing:
            text = "Paused (Processing...)"
        
        return StateInfo(
            state=self._state,
            status_text=text,
            status_color=color,
            can_play=play,
            can_pause=pause,
            can_stop=stop,
            can_resume=resume,
            background_processing=self._is_processing
        )
