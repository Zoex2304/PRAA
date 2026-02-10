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

    def stop(self) -> None:
        """Stop the audio consumer thread and clean up."""
        self._running = False
        self._player.stop()
        self._queue.clear()
        self._queue.signal_done()

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
        self._queue.enqueue(event.audio_path)
        logger.debug(
            "Audio enqueued: chunk %d/%d",
            event.chunk_index + 1,
            event.total_chunks,
        )

    async def handle_hotkey_stop(self, event: HotkeyPressed) -> None:
        """Handle stop hotkey: stop playback and clear queue."""
        if event.action == HotkeyAction.STOP:
            logger.info("Stop hotkey pressed — stopping playback")
            self._player.stop()
            cleared = self._queue.clear()
            self._publish_event(PlaybackStopped(reason="stopped"))
            logger.debug("Cleared %d queued items", cleared)

    async def handle_tray_action(self, event: TrayAction) -> None:
        """Handle tray menu actions for playback control."""
        if event.action == TrayActionType.STOP:
            self._player.stop()
            self._queue.clear()
            self._publish_event(PlaybackStopped(reason="stopped"))

        elif event.action == TrayActionType.PAUSE:
            self._player.pause()
            self._publish_event(PlaybackPaused())

        elif event.action == TrayActionType.RESUME:
            self._player.resume()
        elif event.action == TrayActionType.RESUME:
            self._player.resume()
            self._publish_event(PlaybackResumed(timestamp=time.time()))
