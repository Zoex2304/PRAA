from __future__ import annotations

import logging

from src.domain.audio.service import AudioService
from src.domain.clipboard.service import TkinterClipboardService
from src.domain.config.service import ConfigService
from src.domain.ocr.service import OcrService
from src.domain.processor.service import ProcessorService
from src.domain.tray.service import PystrayTrayService
from src.domain.tts.service import EdgeTTSService
from src.domain.upload.service import UploadService
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    ConfigChanged,
    FileTextReady,
    FileUploadFailed,
    FileUploadRequested,
    HotkeyAction,
    HotkeyPressed,
    OcrCaptureFailed,
    OcrCaptureRequested,
    OcrTextExtracted,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SplashCompleted,
    SynthesisComplete,
    SynthesisStarted,
    TextCaptured,
    TextProcessed,
    TrayAction,
)
from src.presentation.controllers.widget_controller import WidgetController

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        event_bus: EventBus,
        clipboard_service: TkinterClipboardService,
        config_service: ConfigService,
        processor_service: ProcessorService,
        tts_service: EdgeTTSService,
        audio_service: AudioService,
        tray_service: PystrayTrayService,
        ocr_service: OcrService | None = None,
        upload_service: UploadService | None = None,
        widget_controller: WidgetController | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._clipboard = clipboard_service
        self._config = config_service
        self._processor = processor_service
        self._tts = tts_service
        self._audio = audio_service
        self._tray = tray_service
        self._ocr = ocr_service
        self._upload = upload_service
        self._widget = widget_controller

    def wire(self) -> None:
        bus = self._event_bus

        if self._widget is not None:
            bus.subscribe(HotkeyPressed, self._widget.on_hotkey_pressed)
            bus.subscribe(SplashCompleted, self._widget.on_splash_completed)
            bus.subscribe(TextCaptured, self._widget.on_text_captured)
            bus.subscribe(SynthesisStarted, self._widget.on_synthesis_started)
            bus.subscribe(SynthesisComplete, self._widget.on_synthesis_complete)
            bus.subscribe(TextProcessed, self._widget.on_text_processed)
            bus.subscribe(PlaybackStarted, self._widget.on_playback_started)
            bus.subscribe(PlaybackPaused, self._widget.on_playback_paused)
            bus.subscribe(PlaybackResumed, self._widget.on_playback_resumed)
            bus.subscribe(PlaybackStopped, self._widget.on_playback_stopped)
            bus.subscribe(TrayAction, self._widget.on_tray_action)
            bus.subscribe(ConfigChanged, self._widget.on_config_changed)

        bus.subscribe(HotkeyPressed, self._handle_hotkey)
        bus.subscribe(TextCaptured, self._processor.handle_text_captured)

        bus.subscribe(TextProcessed, self._tts.handle_text_processed)

        bus.subscribe(SynthesisComplete, self._audio.handle_synthesis_complete)

        bus.subscribe(HotkeyPressed, self._audio.handle_hotkey_stop)
        bus.subscribe(TrayAction, self._audio.handle_tray_action)

        bus.subscribe(TrayAction, self._config.handle_tray_action)

        bus.subscribe(ConfigChanged, self._processor.handle_config_changed)

        bus.subscribe(PlaybackStarted, self._tray.handle_playback_started)
        bus.subscribe(PlaybackStopped, self._tray.handle_playback_stopped)
        bus.subscribe(PlaybackPaused, self._tray.handle_playback_paused)
        bus.subscribe(PlaybackResumed, self._tray.handle_playback_resumed)

        if self._ocr is not None:
            bus.subscribe(OcrCaptureRequested, self._ocr.handle_ocr_requested)
            bus.subscribe(OcrTextExtracted, self._handle_ocr_text_extracted)
            if self._widget is not None:
                bus.subscribe(OcrCaptureFailed, self._widget.on_ocr_failed)

        if self._upload is not None:
            bus.subscribe(
                FileUploadRequested, self._upload.handle_file_upload_requested
            )
            if self._widget is not None:
                bus.subscribe(FileTextReady, self._widget.on_file_text_ready)
                bus.subscribe(FileUploadFailed, self._widget.on_file_upload_failed)

        logger.info(
            "Orchestrator wired: %d subscriptions registered",
            bus.subscriber_count,
        )

    async def _handle_hotkey(self, event: HotkeyPressed) -> None:
        if self._widget is not None and self._widget.is_splash_active():
            return  # Block all hotkey actions while onboarding splash is shown
        if event.action == HotkeyAction.READ:
            await self._clipboard.capture_and_publish()
        elif event.action == HotkeyAction.OCR:
            await self._event_bus.publish(OcrCaptureRequested())

    async def _handle_ocr_text_extracted(self, event: OcrTextExtracted) -> None:
        """Bridge OCR extracted text into the standard TTS pipeline."""
        await self._event_bus.publish(
            TextCaptured(raw_text=event.text, source_type="OCR")
        )
