from __future__ import annotations

import logging
import threading
from typing import Optional

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.collapsible_component import CollapsibleComponent
from src.presentation.components.debug_metrics_component import DebugMetricsComponent

logger = logging.getLogger(__name__)


class QueueChunkRow(ft.Container):
    def __init__(self, theme: ThemeConfig, index: int, name: str = "", **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._index = index
        self._status = "pending"
        self._name_text = ft.Text(
            value=name or f"Chunk {index + 1}",
            size=theme.typography.font_size_xs,
            color=theme.colors.text_dim,
            expand=True,
        )
        self._status_text = ft.Text(
            value="Pending",
            size=theme.typography.font_size_xs,
            color=theme.colors.chunk_pending,
        )
        self._progress = ft.ProgressBar(
            value=0,
            height=4,
            color=theme.colors.chunk_playing,
            bgcolor=theme.colors.bg_input,
            visible=False,
        )
        self._time_text = ft.Text(
            value="",
            size=self._theme.typography.font_size_xs,
            color=theme.colors.text_muted,
            visible=False,
        )
        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=[self._name_text, self._status_text, self._time_text],
                    spacing=4,
                ),
                self._progress,
            ],
            spacing=2,
        )
        self.padding = ft.padding.symmetric(horizontal=8, vertical=4)
        self.border_radius = 4
        self.bgcolor = self._theme.colors.bg_surface

    def update_status(self, status: str, name: str = ""):
        self._status = status
        colors = self._theme.colors
        status_cfg = {
            "pending": ("Pending", colors.chunk_pending, False),
            "processing": ("Synthesizing…", colors.chunk_processing, False),
            "ready": ("Ready", colors.chunk_ready, False),
            "playing": ("▶ Playing", colors.chunk_playing, True),
            "done": ("✓ Done", colors.chunk_done, False),
        }
        label, color, show_progress = status_cfg.get(status, ("", colors.text_muted, False))
        self._status_text.value = label
        self._status_text.color = color
        self._progress.visible = show_progress
        self._time_text.visible = show_progress or status == "done"
        if name:
            self._name_text.value = name
        self._safe_update()

    def update_progress(self, current_ms: float, total_ms: float):
        if total_ms > 0:
            self._progress.value = min(1.0, current_ms / total_ms)
            self._time_text.value = f"{_fmt_ms(current_ms)} / {_fmt_ms(total_ms)}"
            self._time_text.visible = True
            self._progress.visible = True
            self._safe_update()

    def _safe_update(self):
        try:
            self.update()
        except Exception:
            pass


class DebugPage(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._metrics = DebugMetricsComponent(theme)
        self._chunk_rows: dict[int, QueueChunkRow] = {}
        self._queue_col = ft.Column(spacing=2)

        self._state_item = CollapsibleComponent(
            theme, label="State", initial_value="IDLE"
        )
        self._threads_item = CollapsibleComponent(
            theme,
            label="Threads",
            initial_value=str(threading.active_count()),
            detail_builder=self._metrics.get_thread_details,
        )
        self._memory_item = CollapsibleComponent(
            theme,
            label="Memory",
            initial_value="—",
            detail_builder=self._metrics.get_memory_details,
        )
        self._queue_item = CollapsibleComponent(
            theme,
            label="Queue",
            initial_value="0",
            detail_builder=lambda: self._queue_col,
        )

        self._log_text = ft.TextField(
            multiline=True,
            read_only=True,
            min_lines=8,
            max_lines=12,
            text_size=self._theme.typography.font_size_xs,
            color=self._theme.colors.text_dim,
            bgcolor=self._theme.colors.bg_dark,
            border_color=self._theme.colors.border_subtle,
            value="",
        )
        self.content = ft.Column(
            controls=[
                self._state_item,
                ft.Divider(height=1, color=self._theme.colors.border_subtle),
                self._threads_item,
                ft.Divider(height=1, color=self._theme.colors.border_subtle),
                self._memory_item,
                ft.Divider(height=1, color=self._theme.colors.border_subtle),
                self._queue_item,
                ft.Divider(height=1, color=self._theme.colors.border_subtle),
                ft.Text(
                    "Logs",
                    size=self._theme.typography.font_size_sm,
                    color=self._theme.colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                self._log_text,
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        self.bgcolor = self._theme.colors.bg_panel
        self.padding = ft.padding.all(8)
        self.expand = True

    def update_state(self, text: str):
        self._state_item.set_value(text)

    def update_thread_count(self):
        self._threads_item.set_value(str(threading.active_count()))

    def update_memory(self, text: str):
        self._memory_item.set_value(text)

    def update_queue_count(self, count: int):
        self._queue_item.set_value(str(count))

    def reset_chunks(self):
        self._chunk_rows.clear()
        self._queue_col.controls.clear()
        self._safe_update(self._queue_col)

    def update_chunk_status(self, index: int, status: str, name: str = ""):
        if index not in self._chunk_rows:
            row = QueueChunkRow(self._theme, index, name)
            self._chunk_rows[index] = row
            self._queue_col.controls.append(row)
            self._safe_update(self._queue_col)
        self._chunk_rows[index].update_status(status, name)
        self.update_queue_count(len(self._chunk_rows))

    def update_chunk_progress(self, index: int, current_ms: float, total_ms: float):
        if index in self._chunk_rows:
            self._chunk_rows[index].update_progress(current_ms, total_ms)

    def append_log(self, text: str):
        current = self._log_text.value or ""
        lines = current.split("\n")
        lines.append(text)
        if len(lines) > 200:
            lines = lines[-200:]
        self._log_text.value = "\n".join(lines)
        self._safe_update(self._log_text)

    def _safe_update(self, control):
        try:
            control.update()
        except Exception:
            pass


def _fmt_ms(ms: float) -> str:
    total_s = ms / 1000.0
    m = int(total_s) // 60
    s = int(total_s) % 60
    return f"{m}:{s:02d}"
