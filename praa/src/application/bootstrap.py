"""
PRAA Bootstrap — Dependency Injection and Application Lifecycle

Single place where all concrete implementations are instantiated and wired.
Manages the full application lifecycle: init → run → shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.application.orchestrator import Orchestrator
from src.domain.audio.service import AudioService
from src.domain.clipboard.service import TkinterClipboardService
from src.domain.config.models import AppConfig
from src.domain.config.service import ConfigService
from src.domain.hotkey.service import PynputHotkeyService
from src.domain.processor.service import ProcessorService
from src.domain.tray.service import PystrayTrayService
from src.domain.tts.service import EdgeTTSService
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import AppShutdown, AppStarted, TrayAction, TrayActionType
from src.infrastructure.logging import setup_logging

logger = logging.getLogger(__name__)


class Application:
    """
    PRAA Application — orchestrates the full lifecycle.

    Dependency injection happens here: all services are instantiated
    with their concrete dependencies, then wired through the orchestrator.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._loop: asyncio.AbstractEventLoop | None = None

        # Infrastructure
        self._event_bus = EventBus()

        # Config
        config_path = base_dir / "config.json"
        self._config_service = ConfigService(config_path, self._event_bus)
        self._config = self._config_service.config

        # Services (initialized in start())
        self._hotkey_service: PynputHotkeyService | None = None
        self._clipboard_service: TkinterClipboardService | None = None
        self._processor_service: ProcessorService | None = None
        self._tts_service: EdgeTTSService | None = None
        self._audio_service: AudioService | None = None
        self._tray_service: PystrayTrayService | None = None
        self._orchestrator: Orchestrator | None = None

    def _init_services(self, loop: asyncio.AbstractEventLoop) -> None:
        """Instantiate all domain services with their dependencies."""
        config = self._config

        # Domain services — each gets only what it needs (DIP)
        self._clipboard_service = TkinterClipboardService(self._event_bus)
        self._processor_service = ProcessorService(config, self._event_bus)
        self._tts_service = EdgeTTSService(self._event_bus)
        self._audio_service = AudioService(self._event_bus, loop)
        self._hotkey_service = PynputHotkeyService(config, self._event_bus, loop)

        # Tray service with optional icon
        icon_path = self._base_dir / "assets" / "icon.png"
        self._tray_service = PystrayTrayService(
            config, self._event_bus, loop,
            icon_path=icon_path if icon_path.exists() else None,
        )

        # Orchestrator — wires all event subscriptions
        self._orchestrator = Orchestrator(
            event_bus=self._event_bus,
            clipboard_service=self._clipboard_service,
            config_service=self._config_service,
            processor_service=self._processor_service,
            tts_service=self._tts_service,
            audio_service=self._audio_service,
            tray_service=self._tray_service,
        )

    async def _run(self) -> None:
        """Main async application loop."""
        self._loop = asyncio.get_running_loop()
        self._init_services(self._loop)

        # Wire event subscriptions
        assert self._orchestrator is not None
        self._orchestrator.wire()

        # Subscribe to shutdown events
        self._event_bus.subscribe(AppShutdown, self._handle_shutdown)
        self._event_bus.subscribe(TrayAction, self._handle_tray_exit)

        # Start all services
        assert self._audio_service is not None
        assert self._hotkey_service is not None
        assert self._tray_service is not None

        self._audio_service.start()
        self._hotkey_service.start()
        self._tray_service.start()

        await self._event_bus.publish(AppStarted())

        logger.info("-" * 50)
        logger.info("  PRAA is running — listening for hotkeys")
        logger.info("  READ: %s", self._config.hotkey_read)
        logger.info("  STOP: %s", self._config.hotkey_stop)
        logger.info("  Voice: %s", self._config.voice_id)
        logger.info("  Speed: %.1fx", self._config.speed_rate)
        logger.info("-" * 50)

        # Keep running until shutdown
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def _handle_shutdown(self, event: AppShutdown) -> None:
        """Handle graceful shutdown."""
        logger.info("Shutting down: %s", event.reason)
        self._shutdown()

    async def _handle_tray_exit(self, event: TrayAction) -> None:
        """Handle exit from tray menu."""
        if event.action == TrayActionType.EXIT:
            self._shutdown()

    def _shutdown(self) -> None:
        """Clean up all services and stop the event loop."""
        logger.info("PRAA shutting down...")

        if self._hotkey_service:
            self._hotkey_service.stop()
        if self._audio_service:
            self._audio_service.stop()
        if self._tray_service:
            self._tray_service.stop()
        if self._tts_service:
            self._tts_service.cleanup()
        if self._clipboard_service:
            self._clipboard_service.cleanup()

        self._event_bus.clear()

        # Stop the event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        logger.info("PRAA shutdown complete")

    def run(self) -> None:
        """Entry point: configure logging and start the async loop."""
        setup_logging(level=logging.INFO)
        logger.info("PRAA starting from %s", self._base_dir)

        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            logger.info("Interrupted by user (Ctrl+C)")
            self._shutdown()
        except Exception:
            logger.exception("Unexpected fatal error")
            sys.exit(1)
