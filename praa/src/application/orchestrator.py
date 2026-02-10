"""
PRAA Orchestrator — Event Subscription Registry

The ONLY file that knows about all domains. Wires event subscriptions
so that publishing an event in one domain triggers handlers in others.
Contains zero business logic — pure wiring.
"""

from __future__ import annotations

import logging

from src.domain.audio.service import AudioService
from src.domain.clipboard.service import TkinterClipboardService
from src.domain.config.service import ConfigService
from src.domain.processor.service import ProcessorService
from src.domain.tray.service import PystrayTrayService
from src.domain.tts.service import EdgeTTSService
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    ConfigChanged,
    HotkeyAction,
    HotkeyPressed,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SynthesisComplete,
    TextCaptured,
    TextProcessed,
    TrayAction,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Event subscription registry.

    Wires domain services together through the EventBus.
    This is the single place where cross-domain event routing is defined.

    No business logic lives here — only subscribe() calls.
    """

    def __init__(
        self,
        event_bus: EventBus,
        clipboard_service: TkinterClipboardService,
        config_service: ConfigService,
        processor_service: ProcessorService,
        tts_service: EdgeTTSService,
        audio_service: AudioService,
        tray_service: PystrayTrayService,
    ) -> None:
        self._event_bus = event_bus
        self._clipboard = clipboard_service
        self._config = config_service
        self._processor = processor_service
        self._tts = tts_service
        self._audio = audio_service
        self._tray = tray_service

    def wire(self) -> None:
        """
        Register all event subscriptions.

        Event flow:
            HotkeyPressed(READ) → clipboard.capture_and_publish()
            TextCaptured → processor.handle_text_captured()
            TextProcessed → tts.handle_text_processed()
            SynthesisComplete → audio.handle_synthesis_complete()
            HotkeyPressed(STOP) → audio.handle_hotkey_stop()
            TrayAction → audio.handle_tray_action()
            PlaybackStarted/Stopped/Paused/Resumed → tray.handle_*()
        """
        bus = self._event_bus

        # --- Input → Processing pipeline ---
        bus.subscribe(HotkeyPressed, self._handle_hotkey)
        bus.subscribe(TextCaptured, self._processor.handle_text_captured)

        # --- Processing → TTS pipeline ---
        bus.subscribe(TextProcessed, self._tts.handle_text_processed)

        # --- TTS → Audio pipeline ---
        bus.subscribe(SynthesisComplete, self._audio.handle_synthesis_complete)

        # --- Control events ---
        bus.subscribe(HotkeyPressed, self._audio.handle_hotkey_stop)
        bus.subscribe(TrayAction, self._audio.handle_tray_action)

        # --- Tray → Config (speed/voice changes) ---
        bus.subscribe(TrayAction, self._config.handle_tray_action)

        # --- Config → Processor (reactive updates) ---
        bus.subscribe(ConfigChanged, self._processor.handle_config_changed)

        # --- Playback state → Tray updates ---
        bus.subscribe(PlaybackStarted, self._tray.handle_playback_started)
        bus.subscribe(PlaybackStopped, self._tray.handle_playback_stopped)
        bus.subscribe(PlaybackPaused, self._tray.handle_playback_paused)
        bus.subscribe(PlaybackResumed, self._tray.handle_playback_resumed)

        logger.info(
            "Orchestrator wired: %d subscriptions registered",
            bus.subscriber_count,
        )

    async def _handle_hotkey(self, event: HotkeyPressed) -> None:
        """Route READ hotkey to clipboard capture."""
        if event.action == HotkeyAction.READ:
            await self._clipboard.capture_and_publish()
