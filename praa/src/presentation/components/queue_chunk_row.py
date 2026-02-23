from __future__ import annotations

import contextlib

import flet as ft

from src.domain.config.theme_config import ThemeConfig


def _fmt_ms(ms: float) -> str:
    total_s = ms / 1000.0
    m = int(total_s) // 60
    s = int(total_s) % 60
    return f"{m}:{s:02d}"


class QueueChunkRow(ft.Container):
    def __init__(self, theme: ThemeConfig, index: int, name: str = "", **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._index = index

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
        self._time_text = ft.Text(
            value="",
            size=theme.typography.font_size_xs,
            color=theme.colors.text_muted,
            visible=False,
        )
        self._progress = ft.ProgressBar(
            value=0,
            height=4,
            color=theme.colors.chunk_playing,
            bgcolor=theme.colors.bg_input,
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
        self.bgcolor = theme.colors.bg_surface

    def update_status(self, status: str, name: str = "") -> None:
        colors = self._theme.colors
        status_cfg: dict[str, tuple[str, str, bool]] = {
            "pending": ("Pending", colors.chunk_pending, False),
            "processing": ("Synthesizing…", colors.chunk_processing, False),
            "ready": ("Ready", colors.chunk_ready, False),
            "playing": ("▶ Playing", colors.chunk_playing, True),
            "done": ("✓ Done", colors.chunk_done, False),
        }
        label, color, show_progress = status_cfg.get(
            status, ("", colors.text_muted, False)
        )
        self._status_text.value = label
        self._status_text.color = color
        self._progress.visible = show_progress
        self._time_text.visible = show_progress or status == "done"
        if name:
            self._name_text.value = name
        self._safe_update()

    def update_progress(self, current_ms: float, total_ms: float) -> None:
        if total_ms > 0:
            self._progress.value = min(1.0, current_ms / total_ms)
            self._time_text.value = f"{_fmt_ms(current_ms)} / {_fmt_ms(total_ms)}"
            self._time_text.visible = True
            self._progress.visible = True
            self._safe_update()

    def _safe_update(self) -> None:
        with contextlib.suppress(Exception):
            self.update()
