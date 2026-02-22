from __future__ import annotations

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class ChunkProgressComponent(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._chunks: list[ft.Container] = []
        self._progress_bars: dict[int, ft.ProgressBar] = {}
        self._time_labels: dict[int, ft.Text] = {}
        self._row = ft.Row(spacing=2)

        self.content = self._row
        self.bgcolor = self._theme.colors.bg_surface
        self.padding = ft.padding.symmetric(horizontal=4, vertical=2)
        self.border_radius = 4

    def setup(self, total_chunks: int):
        self._row.controls.clear()
        self._chunks.clear()
        self._progress_bars.clear()
        self._time_labels.clear()
        colors = self._theme.colors

        for i in range(total_chunks):
            label = ft.Text(
                value="",
                size=self._theme.typography.font_size_xs,
                color="#ffffff",
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
            )
            block = ft.Container(
                content=label,
                bgcolor=colors.chunk_pending,
                border_radius=4,
                height=18,
                expand=True,
                alignment=ft.alignment.Alignment(0, 0),
            )
            self._chunks.append(block)
            self._row.controls.append(block)

        self._safe_update(self._row)

    def update_status(self, chunk_idx: int, status: str):
        if 0 <= chunk_idx < len(self._chunks):
            colors = self._theme.colors
            color_map = {
                "pending": colors.chunk_pending,
                "processing": colors.chunk_processing,
                "ready": colors.chunk_ready,
                "playing": colors.chunk_playing,
                "done": colors.chunk_done,
            }
            label_map = {
                "pending": "",
                "processing": "Synth",
                "ready": "Ready",
                "playing": "▶",
                "done": "✓",
            }
            block = self._chunks[chunk_idx]
            block.bgcolor = color_map.get(status, colors.chunk_pending)
            if block.content and isinstance(block.content, ft.Text):
                block.content.value = label_map.get(status, "")
            self._safe_update(block)

    def reset(self):
        self._row.controls.clear()
        self._chunks.clear()
        self._progress_bars.clear()
        self._time_labels.clear()
        self._safe_update(self._row)

    def _safe_update(self, control):
        try:
            control.update()
        except Exception:
            pass
