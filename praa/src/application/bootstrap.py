from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import flet as ft

from src.application.orchestrator import Orchestrator
from src.domain.audio.service import AudioService
from src.domain.clipboard.service import TkinterClipboardService
from src.domain.config.models import AppConfig, UIMode
from src.domain.config.service import ConfigService
from src.domain.config.theme_config import ThemeConfig
from src.domain.hotkey.service import PynputHotkeyService
from src.domain.processor.service import ProcessorService
from src.domain.tray.service import PystrayTrayService
from src.domain.tts.service import EdgeTTSService
from src.domain.session.service import SessionService
from src.infrastructure.database import DatabaseManager
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import AppShutdown, AppStarted, TrayAction, TrayActionType
from src.infrastructure.logging import setup_logging
from src.presentation.controllers.widget_controller import WidgetController

logger = logging.getLogger(__name__)


class Application:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_bus = EventBus()

        config_path = base_dir / "config.json"
        self._config_service = ConfigService(config_path, self._event_bus)
        self._config = self._config_service.config
        self._theme = ThemeConfig.load_from_base(base_dir)

        self._hotkey_service: PynputHotkeyService | None = None
        self._clipboard_service: TkinterClipboardService | None = None
        self._processor_service: ProcessorService | None = None
        self._tts_service: EdgeTTSService | None = None
        self._audio_service: AudioService | None = None
        self._tray_service: PystrayTrayService | None = None
        self._widget_controller: WidgetController | None = None
        self._orchestrator: Orchestrator | None = None
        self._db_manager: DatabaseManager | None = None
        self._session_service: SessionService | None = None

    def _init_services(self, loop: asyncio.AbstractEventLoop) -> None:
        config = self._config

        db_path = self._base_dir / "praa_v3.db"
        cache_dir = self._base_dir / "cache"
        self._db_manager = DatabaseManager(db_path)
        self._db_manager.connect()
        self._session_service = SessionService(self._db_manager, cache_dir)

        self._clipboard_service = TkinterClipboardService(self._event_bus)
        self._processor_service = ProcessorService(config, self._event_bus)
        self._tts_service = EdgeTTSService(self._event_bus)
        self._audio_service = AudioService(self._event_bus, loop)
        self._hotkey_service = PynputHotkeyService(config, self._event_bus, loop)

        icon_path = self._base_dir / "assets" / "icon.png"
        self._tray_service = PystrayTrayService(
            config, self._event_bus, loop,
            icon_path=icon_path if icon_path.exists() else None,
        )

        if config.ui_mode == UIMode.WIDGET:
            self._widget_controller = WidgetController(
                config=config,
                theme=self._theme,
                event_bus=self._event_bus,
                loop=loop,
                session_service=self._session_service,
                audio_service=self._audio_service,
            )

        self._orchestrator = Orchestrator(
            event_bus=self._event_bus,
            clipboard_service=self._clipboard_service,
            config_service=self._config_service,
            processor_service=self._processor_service,
            tts_service=self._tts_service,
            audio_service=self._audio_service,
            tray_service=self._tray_service,
            widget_controller=self._widget_controller,
        )

    async def _flet_main(self, page: ft.Page):
        self._loop = asyncio.get_running_loop()
        self._init_services(self._loop)

        if self._widget_controller:
            self._widget_controller.app.setup(page)
            self._widget_controller.start()

        assert self._orchestrator is not None
        self._orchestrator.wire()

        self._event_bus.subscribe(AppShutdown, self._handle_shutdown)
        self._event_bus.subscribe(TrayAction, self._handle_tray_exit)

        assert self._audio_service is not None
        assert self._hotkey_service is not None
        assert self._tray_service is not None

        self._audio_service.start()
        self._hotkey_service.start()
        self._tray_service.start()

        await self._event_bus.publish(AppStarted())

        logger.info("-" * 50)
        logger.info("  [bold]PRAA is running[/] — listening for hotkeys")
        logger.info("  READ: [cyan]%s[/]", self._config.hotkey_read)
        logger.info("  STOP: [cyan]%s[/]", self._config.hotkey_stop)
        logger.info("  Voice: [cyan]%s[/]", self._config.voice_id)
        logger.info("  Speed: [cyan]%.1fx[/]", self._config.speed_rate)
        logger.info("  UI Mode: [cyan]%s[/]", self._config.ui_mode.value)
        logger.info("-" * 50)

    async def _handle_shutdown(self, event: AppShutdown):
        logger.info("Shutting down: %s", event.reason)
        self._shutdown()

    async def _handle_tray_exit(self, event: TrayAction):
        if event.action == TrayActionType.EXIT:
            self._shutdown()

    def _shutdown(self):
        logger.info("PRAA shutting down...")

        if self._hotkey_service:
            self._hotkey_service.stop()
        if self._audio_service:
            self._audio_service.stop()
        if self._tray_service:
            self._tray_service.stop()
        if self._widget_controller:
            self._widget_controller.stop()
        if self._db_manager:
            self._db_manager.close()
        if self._tts_service:
            self._tts_service.cleanup()
        if self._clipboard_service:
            self._clipboard_service.cleanup()

        self._event_bus.clear()

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        logger.info("PRAA shutdown complete")

    def run(self) -> None:
        setup_logging(level=logging.INFO)
        logger.info("PRAA starting from %s", self._base_dir)

        try:
            ft.app(target=self._flet_main)
        except KeyboardInterrupt:
            logger.info("Interrupted by user (Ctrl+C)")
            self._shutdown()
        except Exception:
            logger.exception("Unexpected fatal error")
            sys.exit(1)
