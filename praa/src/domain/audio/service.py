"""
Audio Domain — Audio Service (Coordinator)

Coordinates the player and queue. Subscribes to SynthesisComplete,
HotkeyPressed(STOP), and TrayAction events. Publishes PlaybackStarted,
PlaybackStopped, PlaybackPaused, PlaybackResumed events.

Runs the playback consumer on a dedicated thread to avoid blocking the async loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

from src.domain.audio.player import SoundDevicePlayer
from src.domain.audio.queue import AudioQueue
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    HotkeyAction,
    HotkeyPressed,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SynthesisComplete,
    TrayAction,
    TrayActionType,
)
from src.domain.config.constants import AUDIO_DEQUEUE_TIMEOUT_S, AUDIO_THREAD_JOIN_TIMEOUT_S

logger = logging.getLogger(__name__)


class AudioService:
    """
    Coordinates audio playback: queue management + player control.

    The service runs a consumer thread that continuously dequeues
    audio files and plays them sequentially. Events control the
    lifecycle (stop, pause, resume).
    """

    def __init__(self, event_bus: EventBus, loop: asyncio.AbstractEventLoop) -> None:
        self._event_bus = event_bus
        self._loop = loop
        self._player = SoundDevicePlayer()
        self._queue = AudioQueue()
        self._consumer_thread: threading.Thread | None = None
        self._running = False

        # Thread-safe lock for shared chunk metadata
        # WHY: _chunk_meta, _chunk_durations, _total_chunks, and _current_chunk_idx
        # are written by async handlers (main loop) and read by the consumer thread.
        # Without synchronization, dict mutation during iteration can corrupt state.
        self._meta_lock = threading.Lock()

        # Track chunk metadata for playback events
        self._chunk_meta: dict[str, tuple[int, int]] = {}  # path_str -> (index, total)
        self._current_chunk_idx: int = -1
        
        # Duration tracking
        self._chunk_durations: dict[int, float] = {}  # index -> ms
        self._total_chunks: int = 0

    @property
    def current_chunk_index(self) -> int:
        """Get the index of the currently playing chunk."""
        return self._current_chunk_idx

    def start(self) -> None:
        """Start the audio consumer thread."""
        if self._consumer_thread is not None:
            return

        self._running = True
        self._consumer_thread = threading.Thread(
            target=self._consumer_loop,
            name="audio-consumer",
            daemon=True,
        )
        self._consumer_thread.start()
        logger.info("Audio consumer thread started")

    # ----------------------------------------------------------------
    # PUBLIC PROPERTIES
    # ----------------------------------------------------------------

    @property
    def position_ms(self) -> float:
        """Get current playback position in milliseconds (current file)."""
        return self._player.position_ms

    @property
    def duration_ms(self) -> float:
        """Get total duration of current track in milliseconds."""
        return self._player.duration_ms
        
    @property
    def current_position_global_ms(self) -> float:
        """Get global playback position across all chunks."""
        with self._meta_lock:
            chunk_idx = self._current_chunk_idx
            durations = dict(self._chunk_durations)

        if chunk_idx < 0:
            return 0.0
            
        elapsed = 0.0
        for i in range(chunk_idx):
            elapsed += durations.get(i, 0.0)
            
        return elapsed + self.position_ms

    @property
    def total_duration_ms(self) -> float:
        """
        Get estimated total duration of the session.
        
        Uses actual duration for ready chunks and average duration
        for pending chunks to prevent UI jumps.
        """
        with self._meta_lock:
            total = self._total_chunks
            durations = dict(self._chunk_durations)

        if total == 0:
            return 0.0
            
        known_duration = sum(durations.values())
        num_known = len(durations)
        
        if num_known == total:
            return known_duration
            
        # Estimate remaining
        if num_known > 0:
            avg = known_duration / num_known
        else:
            avg = 20_000.0  # Default 20s per chunk estimate
            
        remaining = total - num_known
        return known_duration + (remaining * avg)

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing (may be paused)."""
        return self._player.is_playing

    @property
    def is_actively_playing(self) -> bool:
        """Check if audio is actively playing (not paused)."""
        return self._player.is_playing and not self._player.is_paused

    @property
    def is_running(self) -> bool:
        """Whether the consumer thread is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Current number of items in the playback queue."""
        return self._queue.size

    @property
    def current_block(self):
        """Latest audio block for spectrum analysis."""
        return self._player.current_block

    @property
    def samplerate(self) -> int:
        """Current audio samplerate."""
        return self._player._samplerate

    # ----------------------------------------------------------------
    # LIFECYCLE
    # ----------------------------------------------------------------

    def stop(self) -> None:
        """Stop the audio consumer thread and clean up."""
        self._running = False
        self._player.stop()
        self._queue.clear()
        self._queue.signal_done()
        
        self._reset_chunk_state()

        if self._consumer_thread is not None:
            self._consumer_thread.join(timeout=AUDIO_THREAD_JOIN_TIMEOUT_S)
            self._consumer_thread = None

        logger.info("Audio consumer thread stopped")

    # ----------------------------------------------------------------
    # PRIVATE: Consumer Thread
    # ----------------------------------------------------------------

    def _consumer_loop(self) -> None:
        """
        Consumer thread: continuously dequeue and play audio files.

        Runs until self._running is False. Publishes playback events
        back to the event bus (thread-safe via run_coroutine_threadsafe).
        """
        while self._running:
            try:
                audio_path = self._queue.dequeue(timeout=AUDIO_DEQUEUE_TIMEOUT_S)

                if audio_path is None:
                    continue

                if not audio_path.exists():
                    logger.warning("Audio file missing: %s", audio_path)
                    continue

                # Read chunk metadata under lock
                with self._meta_lock:
                    meta = self._chunk_meta.get(audio_path.name, (0, 1))
                    self._current_chunk_idx = meta[0]
                
                logger.debug("Starting playback for chunk %s/%s: %s", meta[0], meta[1], audio_path.name)
                
                # Define callback to capture exact start time
                def on_start() -> None:
                    self._publish_event(PlaybackStarted(
                        chunk_index=meta[0],
                        total_chunks=meta[1],
                        timestamp=time.time()
                    ))

                # Play the audio (blocks until done or stopped)
                self._player.play(audio_path, on_start=on_start)

                # Publish completed event only if playback finished naturally
                if not self._player.is_playing:
                    self._publish_event(PlaybackStopped(reason="completed"))
                    
            except Exception:
                logger.exception("Error in audio consumer loop")

    def _publish_event(self, event: object) -> None:
        """Thread-safe event publishing from the consumer thread."""
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(event),
            self._loop,
        )

    def play_from_chunk(self, chunk_index: int, audio_paths: list[Path]) -> None:
        """Stop current playback and restart from the given chunk index.

        Allows independent or interrupted chunk playback from the Queue UI.
        Emits PlaybackStopped then PlaybackStarted (via consumer thread) in sequence.
        """
        self._player.stop()
        self._queue.clear()
        total = len(audio_paths)
        with self._meta_lock:
            self._chunk_meta.clear()
            self._total_chunks = total
            self._current_chunk_idx = -1
        self._publish_event(PlaybackStopped(reason="stopped"))
        for idx in range(chunk_index, total):
            path = audio_paths[idx]
            with self._meta_lock:
                self._chunk_meta[path.name] = (idx, total)
            self._queue.enqueue(path)
        logger.debug("Seek: playing from chunk %d/%d", chunk_index, total)

    def _stop_playback(self) -> None:
        """
        Stop current playback and clear the queue without killing the consumer thread.

        This is the single, canonical stop implementation used by both
        hotkey and tray stop handlers. Eliminates the duplicated stop logic
        that previously existed across handle_hotkey_stop and handle_tray_action.
        """
        self._player.stop()
        cleared = self._queue.clear()
        self._reset_chunk_state()
        self._publish_event(PlaybackStopped(reason="stopped"))
        logger.debug("Playback stopped, cleared %d queued items", cleared)

    def _reset_chunk_state(self) -> None:
        """Reset all chunk tracking state under lock."""
        with self._meta_lock:
            self._chunk_durations.clear()
            self._total_chunks = 0
            self._current_chunk_idx = -1

    @staticmethod
    def _cleanup_temp_file(audio_path: Path) -> None:
        """Remove temp audio file after playback."""
        try:
            if audio_path.exists():
                audio_path.unlink()
        except OSError:
            logger.debug("Could not remove temp file: %s", audio_path)

    # ----------------------------------------------------------------
    # EVENT HANDLERS
    # ----------------------------------------------------------------

    async def handle_synthesis_complete(self, event: SynthesisComplete) -> None:
        """Enqueue a synthesized audio chunk for playback."""
        # Store chunk metadata under lock
        with self._meta_lock:
            self._chunk_meta[event.audio_path.name] = (event.chunk_index, event.total_chunks)
            self._total_chunks = event.total_chunks
        
        # Calculate duration from boundaries if available
        duration = 0.0
        if event.word_boundaries:
            last = event.word_boundaries[-1]
            duration = last[0] + last[1] 
        elif event.sentence_boundaries:
            last = event.sentence_boundaries[-1]
            duration = last[0] + last[1]
        
        if duration > 0:
            with self._meta_lock:
                self._chunk_durations[event.chunk_index] = duration
            
        self._queue.enqueue(event.audio_path)
        logger.debug(
            "Audio enqueued: chunk %d/%d (dur=%.2fs)",
            event.chunk_index + 1,
            event.total_chunks,
            duration / 1000
        )

    async def handle_hotkey_stop(self, event: HotkeyPressed) -> None:
        """Handle stop hotkey: stop playback and clear queue."""
        if event.action == HotkeyAction.STOP:
            logger.info("Stop hotkey pressed — stopping playback")
            self._stop_playback()

    def seek_within_chunk(self, fraction: float) -> None:
        """Seek to a position within the currently playing chunk."""
        self._player.seek(fraction)

    async def handle_tray_action(self, event: TrayAction) -> None:
        """Handle tray menu actions for playback control."""
        if event.action == TrayActionType.STOP:
            self._stop_playback()

        elif event.action == TrayActionType.PAUSE:
            self._player.pause()
            self._publish_event(PlaybackPaused())

        elif event.action == TrayActionType.RESUME:
            self._player.resume()
            self._publish_event(PlaybackResumed(timestamp=time.time()))
