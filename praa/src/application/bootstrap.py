from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import flet as ft

from src.application.orchestrator import Orchestrator
from src.domain.audio.service import AudioService
from src.domain.clipboard.service import TkinterClipboardService
from src.domain.config.models import UIMode
from src.domain.config.service import ConfigService
from src.domain.config.theme_config import ThemeConfig
from src.domain.dbmanager.service import DbManagerService
from src.domain.hotkey.service import PynputHotkeyService
from src.domain.ocr.capture import ScreenCaptureService
from src.domain.ocr.config import DEBUG_OUTPUT_DIR
from src.domain.ocr.debug_writer import OcrDebugWriter
from src.domain.ocr.overlay import OverlayController
from src.domain.ocr.reader import OcrReaderService
from src.domain.ocr.service import OcrService
from src.domain.processor.service import ProcessorService
from src.domain.session.service import SessionService
from src.domain.tray.service import PystrayTrayService
from src.domain.tts.service import EdgeTTSService
from src.domain.upload.service import UploadService
from src.domain.widget.tips import TipsManager
from src.infrastructure.activity_tracker import ActivityTracker
from src.infrastructure.database.engine import build_engine, build_session_factory
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    AppShutdown,
    AppStarted,
    TrayAction,
    TrayActionType,
)
from src.infrastructure.flet_log_handler import FletLogHandler
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

        self._activity_tracker = ActivityTracker()
        self._hotkey_service: PynputHotkeyService | None = None
        self._clipboard_service: TkinterClipboardService | None = None
        self._processor_service: ProcessorService | None = None
        self._tts_service: EdgeTTSService | None = None
        self._audio_service: AudioService | None = None
        self._tray_service: PystrayTrayService | None = None
        self._ocr_service: OcrService | None = None
        self._upload_service: UploadService | None = None
        self._widget_controller: WidgetController | None = None
        self._orchestrator: Orchestrator | None = None
        self._engine = None  # SQLAlchemy Engine; disposed on shutdown
        self._session_service: SessionService | None = None
        self._db_manager_service: DbManagerService | None = None
        self._log_handler: FletLogHandler | None = None

    def _init_services(self, loop: asyncio.AbstractEventLoop) -> None:
        config = self._config

        db_path = self._base_dir / "praa_v3.db"
        cache_dir = self._base_dir / "cache"

        # Build SQLAlchemy engine (creates schema + runs migrations internally)
        engine = build_engine(db_path)
        self._engine = engine
        session_factory = build_session_factory(engine)
        uow_factory = lambda: UnitOfWork(session_factory)  # noqa: E731

        # First-run check: if app_state has no "first_run" key AND no sessions exist
        # this is a brand-new user; show splash.  Existing users are silently marked done.
        with uow_factory() as uow:
            first_run_val = uow.app_state.get("first_run")
            if first_run_val is None:
                if uow.sessions.count() > 0:
                    uow.app_state.set("first_run", "done")
                    uow.commit()
                    is_first_run = False
                else:
                    is_first_run = True
            else:
                is_first_run = False

        self._session_service = SessionService(uow_factory, cache_dir)
        self._db_manager_service = DbManagerService(
            uow_factory, cache_dir, ocr_debug_dir=Path(DEBUG_OUTPUT_DIR)
        )

        self._clipboard_service = TkinterClipboardService(self._event_bus)
        self._processor_service = ProcessorService(config, self._event_bus)
        self._tts_service = EdgeTTSService(self._event_bus)
        self._audio_service = AudioService(self._event_bus, loop)
        self._hotkey_service = PynputHotkeyService(config, self._event_bus, loop)

        ocr_debug_writer = OcrDebugWriter(DEBUG_OUTPUT_DIR)
        ocr_reader = OcrReaderService(debug_writer=ocr_debug_writer)
        self._ocr_service = OcrService(
            event_bus=self._event_bus,
            loop=loop,
            capture_service=ScreenCaptureService(debug_writer=ocr_debug_writer),
            overlay=OverlayController(),
            reader_service=ocr_reader,
            debug_writer=ocr_debug_writer,
        )
        self._upload_service = UploadService(
            event_bus=self._event_bus,
            loop=loop,
            ocr_reader=ocr_reader,
        )

        icon_path = self._base_dir / "assets" / "icon.png"
        self._tray_service = PystrayTrayService(
            config,
            self._event_bus,
            loop,
            icon_path=icon_path if icon_path.exists() else None,
        )

        if config.ui_mode == UIMode.WIDGET:
            db_svc = self._db_manager_service
            tips_manager = TipsManager(uow_factory)

            def mark_first_run_done():
                with uow_factory() as uow:
                    uow.app_state.set("first_run", "done")
                    uow.commit()

            self._widget_controller = WidgetController(
                config=config,
                theme=self._theme,
                event_bus=self._event_bus,
                loop=loop,
                session_service=self._session_service,
                audio_service=self._audio_service,
                config_service=self._config_service,
                activity_tracker=self._activity_tracker,
                is_first_run=is_first_run,
                on_first_run_complete=mark_first_run_done,
                tips_manager=tips_manager,
            )
            # Wire DB manager callbacks into FletApp
            if self._widget_controller and self._widget_controller.app:
                app = self._widget_controller.app
                app._get_db_stats = db_svc.get_stats
                app._on_clear_cache = db_svc.clear_cache
                app._on_flush_all = db_svc.flush_all

        self._orchestrator = Orchestrator(
            event_bus=self._event_bus,
            clipboard_service=self._clipboard_service,
            config_service=self._config_service,
            processor_service=self._processor_service,
            tts_service=self._tts_service,
            audio_service=self._audio_service,
            tray_service=self._tray_service,
            ocr_service=self._ocr_service,
            upload_service=self._upload_service,
            widget_controller=self._widget_controller,
        )

    async def _flet_main(self, page: ft.Page):
        self._loop = asyncio.get_running_loop()

        self._log_handler = FletLogHandler(max_records=300)
        logging.getLogger().addHandler(self._log_handler)

        self._init_services(self._loop)

        if self._widget_controller:
            self._widget_controller.app.setup(page)
            self._widget_controller.start()
            self._widget_controller.set_log_handler(self._log_handler)

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
        logger.info("  PRAA is running — listening for hotkeys")
        logger.info("  READ: %s", self._config.hotkey_read)
        logger.info("  STOP: %s", self._config.hotkey_stop)
        logger.info("  Voice: %s", self._config.voice_id)
        logger.info("  Speed: %.1fx", self._config.speed_rate)
        logger.info("  UI Mode: %s", self._config.ui_mode.value)
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
        if self._engine:
            self._engine.dispose()
            logger.info("SQLAlchemy engine disposed")
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
