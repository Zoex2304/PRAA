from __future__ import annotations

import logging
import os
import threading

import flet as ft
import psutil

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.collapsible_component import CollapsibleComponent
from src.presentation.components.queue_chunk_row import QueueChunkRow

logger = logging.getLogger(__name__)


def _describe_thread(name: str) -> str:
    lower = name.lower()
    if "mainthread" in lower:
        return "Main loop"
    if "flet" in lower:
        return "UI event loop"
    if "asyncio" in lower or "async" in lower:
        return "EventBus dispatch"
    if "hotkey" in lower or "pynput" in lower:
        return "Hotkey listener"
    if "tray" in lower or "pystray" in lower:
        return "System tray"
    if "audio" in lower or "playback" in lower or "sounddevice" in lower:
        return "Audio playback"
    if "tts" in lower or "synthesis" in lower:
        return "TTS synthesis"
    if "thread" in lower and "pool" in lower:
        return "Thread pool"
    if "watchdog" in lower or "observer" in lower:
        return "File watcher"
    if "lingua" in lower:
        return "Language detection"
    return "Worker"


class DebugPage(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._chunk_rows: dict[int, QueueChunkRow] = {}
        self._queue_col = ft.Column(spacing=2)
        self._log_handler = None

        colors = theme.colors
        typo = theme.typography

        # State: flat indicator row (not collapsible)
        self._state_dot = ft.Icon(ft.Icons.CIRCLE, size=10, color=colors.status_idle)
        self._state_text = ft.Text("Idle", size=typo.font_size_sm, color=colors.text_dim)
        state_row = ft.Row(
            controls=[
                ft.Text("State", size=typo.font_size_sm, color=colors.text_muted, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self._state_dot,
                self._state_text,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # System: memory + PID (collapsible)
        self._system_item = CollapsibleComponent(
            theme, label="System", initial_value="—",
            detail_builder=self._build_system_details,
        )

        # Threads: collapsible with per-thread activity
        self._thread_list_col = ft.Column(spacing=3)
        self._threads_item = CollapsibleComponent(
            theme,
            label="Threads",
            initial_value=str(threading.active_count()),
            detail_builder=lambda: self._thread_list_col,
        )

        # Queue: collapsible with chunk rows + progress
        self._queue_item = CollapsibleComponent(
            theme,
            label="Queue",
            initial_value="0",
            detail_builder=lambda: self._queue_col,
        )

        self.content = ft.Column(
            controls=[
                state_row,
                ft.Divider(height=1, color=colors.border_subtle),
                self._system_item,
                ft.Divider(height=1, color=colors.border_subtle),
                self._threads_item,
                ft.Divider(height=1, color=colors.border_subtle),
                self._queue_item,
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        self.bgcolor = colors.bg_panel
        self.padding = ft.padding.all(8)
        self.expand = True

    def set_log_handler(self, handler) -> None:
        self._log_handler = handler

    def update_state(self, text: str, color: str | None = None) -> None:
        self._state_text.value = text
        if color:
            self._state_dot.color = color
        self._safe_update(self._state_text)
        self._safe_update(self._state_dot)

    def update_system(self, text: str) -> None:
        self._system_item.set_value(text)

    def update_thread_panel(self, activity: dict[str, str]) -> None:
        colors = self._theme.colors
        typo = self._theme.typography
        rows = []

        live_names = {t.name for t in threading.enumerate()}
        for t in threading.enumerate():
            last_msg = activity.get(t.name, "")
            daemon_tag = " [D]" if t.daemon else ""
            desc = _describe_thread(t.name)
            rows.append(
                ft.Column(
                    controls=[
                        ft.Text(
                            f"● {t.name}{daemon_tag} — {desc}",
                            size=typo.font_size_xs,
                            color=colors.accent,
                        ),
                        ft.Text(
                            last_msg if last_msg else "—",
                            size=typo.font_size_xs,
                            color=colors.text_muted,
                        ),
                    ],
                    spacing=1,
                )
            )

        self._thread_list_col.controls = rows
        self._threads_item.set_value(str(threading.active_count()))
        self._safe_update(self._thread_list_col)

    def update_queue_count(self, count: int) -> None:
        self._queue_item.set_value(str(count))

    def reset_chunks(self) -> None:
        self._chunk_rows.clear()
        self._queue_col.controls.clear()
        self._safe_update(self._queue_col)

    def update_chunk_status(self, index: int, status: str, name: str = "") -> None:
        if index not in self._chunk_rows:
            row = QueueChunkRow(self._theme, index, name)
            self._chunk_rows[index] = row
            self._queue_col.controls.append(row)
            self._safe_update(self._queue_col)
        self._chunk_rows[index].update_status(status, name)
        self.update_queue_count(len(self._chunk_rows))

    def update_chunk_progress(self, index: int, current_ms: float, total_ms: float) -> None:
        if index in self._chunk_rows:
            self._chunk_rows[index].update_progress(current_ms, total_ms)

    def _build_system_details(self) -> ft.Control:
        colors = self._theme.colors
        try:
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            rss_mb = mem.rss / (1024 * 1024)
            vms_mb = mem.vms / (1024 * 1024)
            lines = [
                f"RSS: {rss_mb:.1f} MB",
                f"VMS: {vms_mb:.1f} MB",
                f"PID: {os.getpid()}",
                f"Threads: {threading.active_count()}",
            ]
            summary = f"{rss_mb:.0f} MB"
        except Exception:
            lines = ["Unavailable"]
            summary = "—"

        self._system_item.set_value(summary)
        return ft.Column(
            controls=[
                ft.Text(line, size=self._theme.typography.font_size_xs, color=colors.text_dim)
                for line in lines
            ],
            spacing=2,
        )

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
