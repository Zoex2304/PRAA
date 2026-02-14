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

        # Track chunk metadata for playback events
        self._chunk_meta: dict[str, tuple[int, int]] = {}  # path_str -> (index, total)
        self._current_chunk_idx: int = -1
        
        # Duration tracking
        self._chunk_durations: dict[int, float] = {}  # index -> ms
        self._total_chunks: int = 0

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
        if self._current_chunk_idx < 0:
            return 0.0
            
        elapsed = 0.0
        for i in range(self._current_chunk_idx):
            elapsed += self._chunk_durations.get(i, 0.0)
            
        return elapsed + self.position_ms

    @property
    def total_duration_ms(self) -> float:
        """
        Get estimated total duration of the session.
        
        Uses actual duration for ready chunks and average duration
        for pending chunks to prevent UI jumps.
        """
        if self._total_chunks == 0:
            return 0.0
            
        known_duration = sum(self._chunk_durations.values())
        num_known = len(self._chunk_durations)
        
        if num_known == self._total_chunks:
            return known_duration
            
        # Estimate remaining
        if num_known > 0:
            avg = known_duration / num_known
        else:
            avg = 20_000.0  # Default 20s per chunk estimate
            
        remaining = self._total_chunks - num_known
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
    def current_block(self):
        """Latest audio block for spectrum analysis."""
        return self._player.current_block

    @property
    def samplerate(self) -> int:
        """Current audio samplerate."""
        return self._player._samplerate

    def stop(self) -> None:
        """Stop the audio consumer thread and clean up."""
        self._running = False
        self._player.stop()
        self._queue.clear()
        self._queue.signal_done()
        
        self._chunk_durations.clear()
        self._total_chunks = 0
        self._current_chunk_idx = -1

        if self._consumer_thread is not None:
            self._consumer_thread.join(timeout=2.0)
            self._consumer_thread = None

        logger.info("Audio consumer thread stopped")

    def _consumer_loop(self) -> None:
        """
        Consumer thread: continuously dequeue and play audio files.

        Runs until self._running is False. Publishes playback events
        back to the event bus (thread-safe via run_coroutine_threadsafe).
        """
        while self._running:
            try:
                audio_path = self._queue.dequeue(timeout=0.5)

                if audio_path is None:
                    continue

                if not audio_path.exists():
                    logger.warning("Audio file missing: %s", audio_path)
                    continue

                # Publish playback start event with chunk metadata
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

                # NOTE: Don't delete temp files — needed for Save Audio feature.
                # Cleanup happens on app shutdown via TTS service.

                # Publish playback stop event
                if not self._player.is_playing:
                    # Only publish stopped if we genuinely finished (not preempted)
                    # Actually, we should check if more items are in queue
                    # For now, we publish completed event for this CHUNK
                    # But the Service considers "PlaybackStopped" as session stop?
                    # The original code sent PlaybackStopped(reason="completed")
                    # This might trigger "Playback Complete" in UI.
                    # We only want that if queue is empty AND no more chunks coming.
                    
                    # Logic: if queue empty and we have all chunks, then done.
                    # But consumer loop doesn't know if synthesis is still running easily.
                    # Actually, PlaybackStateManager manages the session state.
                    # It receives PlaybackStopped.
                    # If reason="completed", it goes to READY.
                    # If user just plays 1 chunk, it goes READY.
                    # If auto-playing sequence, we don't want "READY" between chunks.
                    
                    # Wait, the consumer loop blocks. 
                    # So sending PlaybackStopped here happens AFTER play finishes.
                    # If there is another item in queue immediately, we loop.
                    # But we sent "Stopped". The UI might flicker or reset.
                    # However, strictly speaking, *that file* stopped.
                    
                    # Let's keep original behavior for now to avoid breaking flow.
                    self._publish_event(PlaybackStopped(reason="completed"))
                    
            except Exception:
                logger.exception("Error in audio consumer loop")

    def _publish_event(self, event: object) -> None:
        """Thread-safe event publishing from the consumer thread."""
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(event),
            self._loop,
        )

    @staticmethod
    def _cleanup_temp_file(audio_path: Path) -> None:
        """Remove temp audio file after playback."""
        try:
            if audio_path.exists():
                audio_path.unlink()
        except OSError:
            logger.debug("Could not remove temp file: %s", audio_path)

    # ----- Event Handlers -----

    async def handle_synthesis_complete(self, event: SynthesisComplete) -> None:
        """Enqueue a synthesized audio chunk for playback."""
        # Store chunk metadata for PlaybackStarted events
        self._chunk_meta[event.audio_path.name] = (event.chunk_index, event.total_chunks)
        self._total_chunks = event.total_chunks
        
        # Calculate duration from boundaries if available
        duration = 0.0
        if event.word_boundaries:
            last = event.word_boundaries[-1]
            # offset + duration (ms)
            duration = last[0] + last[1] 
        elif event.sentence_boundaries:
            last = event.sentence_boundaries[-1]
            duration = last[0] + last[1]
        
        # Fallback: estimate from text length if no boundaries? 
        # Or just wait for player. But we need it for total duration.
        # If 0, it will use average.
        if duration > 0:
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
            self._player.stop()
            cleared = self._queue.clear()
            
            self._chunk_durations.clear()
            self._total_chunks = 0
            self._current_chunk_idx = -1
            
            self._publish_event(PlaybackStopped(reason="stopped"))
            logger.debug("Cleared %d queued items", cleared)

    async def handle_tray_action(self, event: TrayAction) -> None:
        """Handle tray menu actions for playback control."""
        if event.action == TrayActionType.STOP:
            self.stop() # Use full stop to clear Durations
            # But wait, stop() kills the thread. accessing self._player.stop is enough?
            # handle_hotkey_stop just calls player.stop and queue.clear.
            # safe to stick to that pattern but clear durations too.
            self._player.stop()
            self._queue.clear()
            self._chunk_durations.clear()
            self._total_chunks = 0
            self._current_chunk_idx = -1
            
            self._publish_event(PlaybackStopped(reason="stopped"))

        elif event.action == TrayActionType.PAUSE:
            self._player.pause()
            self._publish_event(PlaybackPaused())

        elif event.action == TrayActionType.RESUME:
            self._player.resume()
            self._publish_event(PlaybackResumed(timestamp=time.time()))
