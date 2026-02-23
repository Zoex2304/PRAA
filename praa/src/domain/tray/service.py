"""
Tray Domain — pystray-based System Tray Service

System tray icon with right-click context menu for playback control.
Publishes TrayAction events — never calls other services directly (SRP).
Subscribes to playback events to update tooltip status.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

import pystray
from PIL import Image
from pystray import Menu, MenuItem

from src.domain.config.models import AppConfig
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    AppShutdown,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackState,
    PlaybackStopped,
    TrayAction,
    TrayActionType,
)

logger = logging.getLogger(__name__)

# Default icon: a simple colored square if no icon file exists
_DEFAULT_ICON_SIZE = 64
_DEFAULT_ICON_COLOR = (0, 150, 136)  # Teal


class PystrayTrayService:
    """
    System tray icon using pystray.

    Provides a right-click menu with playback controls and settings.
    All user interactions are translated into TrayAction events published
    to the EventBus. This service never directly calls any other domain
    service — pure event-driven decoupling.
    """

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        icon_path: Path | None = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._loop = loop
        self._icon_path = icon_path
        self._icon: pystray.Icon | None = None
        self._state = PlaybackState.IDLE
        self._thread: threading.Thread | None = None

    def _create_icon_image(self) -> Image.Image:
        """Load icon from file or create a default colored square."""
        if self._icon_path and self._icon_path.exists():
            try:
                return Image.open(self._icon_path)
            except Exception:
                logger.warning("Failed to load icon from %s", self._icon_path)

        # Create a default teal square icon
        img = Image.new(
            "RGB", (_DEFAULT_ICON_SIZE, _DEFAULT_ICON_SIZE), _DEFAULT_ICON_COLOR
        )
        return img

    def _create_menu(self) -> Menu:
        """Build the right-click context menu."""
        return Menu(
            MenuItem("🖥 Show/Hide Widget", self._on_toggle_widget, default=True),
            pystray.Menu.SEPARATOR,
            MenuItem(
                "▶ Resume",
                self._on_resume,
                visible=lambda _: self._state == PlaybackState.PAUSED,
            ),
            MenuItem(
                "⏸ Pause",
                self._on_pause,
                visible=lambda _: self._state == PlaybackState.PLAYING,
            ),
            MenuItem("⏹ Stop", self._on_stop),
            pystray.Menu.SEPARATOR,
            MenuItem(
                "Speed",
                Menu(
                    MenuItem("0.75x", lambda: self._on_change_speed("0.75")),
                    MenuItem("1.0x", lambda: self._on_change_speed("1.0")),
                    MenuItem("1.25x", lambda: self._on_change_speed("1.25")),
                    MenuItem("1.5x", lambda: self._on_change_speed("1.5")),
                    MenuItem("2.0x", lambda: self._on_change_speed("2.0")),
                ),
            ),
            MenuItem(
                "Voice",
                Menu(
                    MenuItem("Ardi (Male ID)", lambda: self._on_change_voice("male")),
                    MenuItem(
                        "Gadis (Female ID)", lambda: self._on_change_voice("female")
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            MenuItem("Exit", self._on_exit),
        )

    def _on_toggle_widget(self, icon=None, item=None) -> None:
        self._publish_event(
            TrayAction(action=TrayActionType.TOGGLE_MODE, value="toggle_window")
        )

    # _on_show_widget removed in favor of toggle

    def _get_tooltip(self) -> str:
        """Generate tooltip text based on current state."""
        state_labels = {
            PlaybackState.IDLE: "Idle",
            PlaybackState.PLAYING: "Playing...",
            PlaybackState.PAUSED: "Paused",
            PlaybackState.STOPPED: "Stopped",
        }
        return f"PRAA — {state_labels.get(self._state, 'Ready')}"

    # ----- Menu action handlers (run on pystray's thread) -----

    def _on_pause(self, icon=None, item=None) -> None:
        self._publish_event(TrayAction(action=TrayActionType.PAUSE))

    def _on_resume(self, icon=None, item=None) -> None:
        self._publish_event(TrayAction(action=TrayActionType.RESUME))

    def _on_stop(self, icon=None, item=None) -> None:
        self._publish_event(TrayAction(action=TrayActionType.STOP))

    def _on_exit(self, icon=None, item=None) -> None:
        self._publish_event(TrayAction(action=TrayActionType.EXIT))
        # Also publish app shutdown
        self._publish_event(AppShutdown(reason="tray_exit"))
        if self._icon:
            self._icon.stop()

    def _on_change_speed(self, speed: str) -> None:
        self._publish_event(TrayAction(action=TrayActionType.CHANGE_SPEED, value=speed))

    def _on_change_voice(self, gender: str) -> None:
        self._publish_event(
            TrayAction(action=TrayActionType.CHANGE_VOICE, value=gender)
        )

    def _publish_event(self, event: object) -> None:
        """Thread-safe event publishing from pystray's thread."""
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(event),
            self._loop,
        )

    # ----- Lifecycle -----

    def start(self) -> None:
        """Show the system tray icon."""
        image = self._create_icon_image()
        menu = self._create_menu()

        self._icon = pystray.Icon(
            name="PRAA",
            icon=image,
            title=self._get_tooltip(),
            menu=menu,
        )

        # Run pystray on its own thread (it blocks)
        self._thread = threading.Thread(
            target=self._icon.run,
            name="tray-icon",
            daemon=True,
        )
        self._thread.start()
        logger.info("System tray icon started")

    def stop(self) -> None:
        """Remove the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None
        logger.info("System tray icon stopped")

    def update_status(self, state: PlaybackState) -> None:
        """Update tray tooltip to reflect current playback state."""
        self._state = state
        if self._icon:
            self._icon.title = self._get_tooltip()

    # ----- Event Handlers (subscribed via orchestrator) -----

    async def handle_playback_started(self, event: PlaybackStarted) -> None:
        self.update_status(PlaybackState.PLAYING)

    async def handle_playback_stopped(self, event: PlaybackStopped) -> None:
        self.update_status(PlaybackState.IDLE)

    async def handle_playback_paused(self, event: PlaybackPaused) -> None:
        self.update_status(PlaybackState.PAUSED)

    async def handle_playback_resumed(self, event: PlaybackResumed) -> None:
        self.update_status(PlaybackState.PLAYING)
