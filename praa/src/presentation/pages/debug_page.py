from __future__ import annotations

import contextlib
import logging
import os
import threading
from collections.abc import Callable

import flet as ft
import psutil

from src.domain.config.theme_config import ThemeConfig
from src.infrastructure.activity_tracker import ActivityTracker
from src.presentation.components.collapsible_component import CollapsibleComponent
from src.presentation.components.kpi_grid_component import KpiGridComponent
from src.presentation.components.queue_component import QueueComponent

logger = logging.getLogger(__name__)


def _thread_role(name: str) -> str:
    lower = name.lower()
    if "mainthread" in lower:
        return "Application entry point"
    if "flet" in lower:
        return "UI event pump"
    if "audio" in lower:
        return "Audio playback consumer"
    if "tts" in lower or "synthesis" in lower:
        return "TTS synthesis worker"
    if "hotkey" in lower or "pynput" in lower:
        return "Global hotkey listener"
    if "tray" in lower or "pystray" in lower:
        return "System tray handler"
    if "asyncio" in lower or "async" in lower:
        return "Async event dispatcher"
    if "lingua" in lower:
        return "Language detector"
    if "thread" in lower and "pool" in lower:
        return "Thread pool worker"
    if "watchdog" in lower:
        return "File watcher"
    return "Background worker"


class DebugPage(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        on_play_chunk: Callable[[int], None] | None = None,
        on_pause_chunk: Callable[[int], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._log_handler = None
        self._activity_tracker: ActivityTracker | None = None

        colors = theme.colors
        typo = theme.typography

        self._state_dot = ft.Icon(ft.Icons.CIRCLE, size=10, color=colors.status_idle)
        self._state_text = ft.Text(
            "Idle", size=typo.font_size_sm, color=colors.text_dim
        )
        state_row = ft.Row(
            controls=[
                ft.Text(
                    "State",
                    size=typo.font_size_sm,
                    color=colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(expand=True),
                self._state_dot,
                self._state_text,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self._kpi = KpiGridComponent(theme)
        system_section = ft.Column(
            controls=[
                ft.Text(
                    "System",
                    size=typo.font_size_sm,
                    color=colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                self._kpi,
            ],
            spacing=4,
        )

        self._thread_col = ft.Column(spacing=6)
        self._threads_item = CollapsibleComponent(
            theme,
            label="Threads",
            initial_value=str(threading.active_count()),
            detail_builder=lambda: self._thread_col,
        )

        self.queue = QueueComponent(
            theme,
            on_play_chunk=on_play_chunk,
            on_pause_chunk=on_pause_chunk,
        )

        self.content = ft.Column(
            controls=[
                state_row,
                ft.Divider(height=1, color=colors.border_subtle),
                system_section,
                ft.Divider(height=1, color=colors.border_subtle),
                self._threads_item,
                ft.Divider(height=1, color=colors.border_subtle),
                self.queue,
            ],
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        self.bgcolor = colors.bg_panel
        self.padding = ft.padding.all(8)
        self.expand = True

        self._refresh_system_kpi()

    def set_log_handler(self, handler) -> None:
        self._log_handler = handler

    def set_activity_tracker(self, tracker: ActivityTracker) -> None:
        self._activity_tracker = tracker

    def update_state(self, text: str, color: str | None = None) -> None:
        self._state_text.value = text
        if color:
            self._state_dot.color = color
        self._safe_update(self._state_text)
        self._safe_update(self._state_dot)

    def refresh_system(self) -> None:
        self._refresh_system_kpi()

    def update_thread_panel(self, log_activity: dict[str, str]) -> None:
        colors = self._theme.colors
        typo = self._theme.typography
        tracker_data = (
            self._activity_tracker.get_all() if self._activity_tracker else {}
        )
        rows = []

        for t in threading.enumerate():
            role = _thread_role(t.name)
            daemon_badge = " [D]" if t.daemon else ""
            tracker_entry = tracker_data.get(t.name)
            activity_line = (
                tracker_entry.summary
                if tracker_entry
                else log_activity.get(t.name, "—")
            )

            rows.append(
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CIRCLE, size=6, color=colors.accent),
                                ft.Text(
                                    f"{t.name}{daemon_badge}",
                                    size=typo.font_size_xs,
                                    color=colors.text_dim,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Container(expand=True),
                                ft.Text(
                                    role,
                                    size=typo.font_size_xs,
                                    color=colors.text_muted,
                                ),
                            ],
                            spacing=4,
                        ),
                        ft.Text(
                            activity_line,
                            size=typo.font_size_xs,
                            color=colors.text_muted,
                        ),
                    ],
                    spacing=1,
                )
            )

        self._thread_col.controls = rows
        self._threads_item.set_value(str(threading.active_count()))
        self._safe_update(self._thread_col)

    def reset_chunks(self) -> None:
        self.queue.reset()

    def update_chunk_status(self, index: int, status: str, name: str = "") -> None:
        self.queue.update_chunk_status(index, status, name)

    def update_chunk_progress(
        self, index: int, current_ms: float, total_ms: float
    ) -> None:
        self.queue.update_chunk_progress(index, current_ms, total_ms)

    def _refresh_system_kpi(self) -> None:
        try:
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            self._kpi.refresh(
                rss_mb=mem.rss / (1024 * 1024),
                vms_mb=mem.vms / (1024 * 1024),
                pid=os.getpid(),
                threads=threading.active_count(),
            )
        except Exception:
            pass

    def _safe_update(self, control: ft.Control) -> None:
        with contextlib.suppress(Exception):
            control.update()
