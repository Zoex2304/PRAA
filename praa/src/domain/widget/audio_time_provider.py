"""
AudioTimeProvider - Single Source of Truth for Playback Time

SINGLE RESPONSIBILITY:
- Provide accurate audio playback position
- Abstract away audio player implementation details
- Guarantee monotonic time progression during playback

GUARANTEES:
- Time only advances when audio is actually playing
- Pause/resume handled correctly
- Latency compensation built-in
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybackPosition:
    """Immutable playback position snapshot."""
    chunk_index: int
    position_ms: float  # Position within current chunk
    is_playing: bool
    system_timestamp: float  # When this position was captured


class ITimeProvider(ABC):
    """
    Interface for audio playback time providers.
    
    Allows SyncController to work with any audio player implementation.
    """
    
    @abstractmethod
    def get_position(self) -> Optional[PlaybackPosition]:
        """
        Get current playback position.
        
        Returns None if no audio is loaded or player is stopped.
        """
        pass
    
    @abstractmethod
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        pass


class CalibratedTimeProvider(ITimeProvider):
    """
    Time provider with automatic latency compensation.
    
    Measures the offset between start_sync() call and actual audio output,
    then compensates all subsequent time queries.
    
    ARCHITECTURE:
    - Wraps actual audio player
    - Maintains calibration offset
    - Provides corrected playback position
    """
    
    def __init__(
        self,
        get_player_position_ms: Callable[[], float],  # Callback to get player position
        get_player_state: Callable[[], bool],  # Callback to check if playing
        latency_compensation_ms: float = 0.0,
    ) -> None:
        """
        Args:
            get_player_position_ms: fn() -> float (current position in ms)
            get_player_state: fn() -> bool (is playing)
            latency_compensation_ms: Known system latency to compensate
        """
        self._get_position_raw = get_player_position_ms
        self._get_state = get_player_state
        
        # Calibration data
        self._base_offset_ms = latency_compensation_ms
        self._calibration_offset_ms = 0.0
        self._is_calibrated = False
        
        # Current chunk tracking
        self._current_chunk = -1
        self._chunk_start_position_ms = 0.0
    
    def calibrate(self, expected_start_ms: float = 0.0) -> None:
        """
        Calibrate time offset between command and actual playback.
        
        Call this immediately after starting playback, passing the
        expected start position (usually 0.0 for new chunk).
        """
        try:
            actual_pos = self._get_position_raw()
            self._calibration_offset_ms = expected_start_ms - actual_pos
            self._is_calibrated = True
            
            total_offset = self._base_offset_ms + self._calibration_offset_ms
            logger.info(
                "Time calibration: offset=%.1fms (base=%.1fms, measured=%.1fms)",
                total_offset, self._base_offset_ms, self._calibration_offset_ms
            )
        except Exception:
            logger.exception("Calibration failed, using base offset only")
            self._is_calibrated = False
    
    def set_chunk(self, chunk_index: int, chunk_start_ms: float = 0.0) -> None:
        """
        Notify provider of chunk change.
        
        Args:
            chunk_index: Index of current chunk
            chunk_start_ms: Position where this chunk starts in player timeline
        """
        self._current_chunk = chunk_index
        self._chunk_start_position_ms = chunk_start_ms
        logger.debug("TimeProvider: chunk=%d, start_ms=%.1f", chunk_index, chunk_start_ms)
    
    def get_position(self) -> Optional[PlaybackPosition]:
        """Get calibrated playback position."""
        if self._current_chunk < 0:
            return None
        
        try:
            # Get raw position from player
            raw_position = self._get_position_raw()
            is_playing = self._get_state()
            
            # Apply calibration
            # Logic: Corrected = Raw + Offset
            # If Raw is 500, and Offset is -50 (latency), Corrected = 450.
            total_offset = self._base_offset_ms + self._calibration_offset_ms
            calibrated = raw_position + total_offset
            
            # Calculate position within current chunk
            chunk_position = calibrated - self._chunk_start_position_ms
            
            return PlaybackPosition(
                chunk_index=self._current_chunk,
                position_ms=max(0.0, chunk_position),
                is_playing=is_playing,
                system_timestamp=time.time(),
            )
        except Exception:
            logger.exception("Failed to get playback position")
            return None
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        try:
            return self._get_state()
        except Exception:
            return False


class FallbackTimeProvider(ITimeProvider):
    """
    Fallback time provider using system clock (original behavior).
    
    Use this when audio player doesn't expose position API.
    Less accurate but better than nothing.
    """
    
    def __init__(self) -> None:
        self._playback_start_time = 0.0
        self._pause_start_time = 0.0
        self._accumulated_pause_duration = 0.0
        self._current_chunk = -1
        self._is_playing = False
    
    def start(self, chunk_index: int) -> None:
        """Start timing for a chunk."""
        self._current_chunk = chunk_index
        self._playback_start_time = time.time()
        self._accumulated_pause_duration = 0.0
        self._is_playing = True
    
    def pause(self) -> None:
        """Pause timing."""
        if self._is_playing:
            self._pause_start_time = time.time()
            self._is_playing = False
    
    def resume(self) -> None:
        """Resume timing."""
        if not self._is_playing and self._pause_start_time > 0:
            pause_duration = time.time() - self._pause_start_time
            self._accumulated_pause_duration += pause_duration
            self._is_playing = True
    
    def stop(self) -> None:
        """Stop timing."""
        self._is_playing = False
        self._current_chunk = -1
    
    def get_position(self) -> Optional[PlaybackPosition]:
        """Get position based on elapsed system time."""
        if self._current_chunk < 0:
            return None
        
        if self._is_playing:
            elapsed = time.time() - self._playback_start_time - self._accumulated_pause_duration
        else:
            # Return last position when paused
            elapsed = self._pause_start_time - self._playback_start_time - self._accumulated_pause_duration
        
        return PlaybackPosition(
            chunk_index=self._current_chunk,
            position_ms=max(0.0, elapsed * 1000),
            is_playing=self._is_playing,
            system_timestamp=time.time(),
        )
    
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._is_playing
