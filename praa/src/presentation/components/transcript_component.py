from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import flet as ft

from src.domain.config.theme_config import ThemeConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkData:
    index: int
    text: str
    char_offset: int

    @property
    def char_end(self) -> int:
        return self.char_offset + len(self.text)


class TranscriptComponent(ft.Container):
    def __init__(self, theme: ThemeConfig, on_copy: Optional[callable] = None, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_copy = on_copy
        self._chunks: dict[int, ChunkData] = {}
        self._full_text = ""
        self._word_spans: list[ft.TextSpan] = []
        self._text_control = ft.Text(
            selectable=True,
            size=theme.typography.font_size_md,
            color=theme.colors.text_dim,
        )
        self._copy_btn = ft.IconButton(
            icon=ft.Icons.COPY,
            icon_size=14,
            icon_color=self._theme.colors.text_muted,
            tooltip="Copy transcript",
            on_click=self._handle_copy,
        )
        self._time_label = ft.Text(
            value="00:00",
            size=theme.typography.font_size_sm,
            color=theme.colors.text_muted,
        )

        header = ft.Row(
            controls=[
                ft.Text(
                    "Transcript",
                    size=self._theme.typography.font_size_sm,
                    color=self._theme.colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Row(
                    controls=[self._time_label, self._copy_btn],
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self._scroll_col = ft.Column(
            controls=[self._text_control],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        self.content = ft.Column(
            controls=[header, self._scroll_col],
            spacing=4,
            expand=True,
        )
        self.bgcolor = self._theme.colors.bg_surface
        self.border_radius = 8
        self.padding = ft.padding.all(8)
        self.expand = True

    def set_content(self, chunks: list[str]):
        chunk_data = []
        offset = 0
        for idx, text in enumerate(chunks):
            chunk_data.append(ChunkData(index=idx, text=text, char_offset=offset))
            offset += len(text) + 2

        self._chunks = {c.index: c for c in chunk_data}
        self._full_text = "\n\n".join(chunks)
        self._rebuild_spans()
        logger.info("Transcript loaded: %d chunks, %d chars", len(chunks), len(self._full_text))

    def clear_content(self):
        self._chunks.clear()
        self._full_text = ""
        self._text_control.spans = []
        self._text_control.value = ""
        self._safe_update(self._text_control)

    def highlight_relative(self, chunk_idx: int, start: int, end: int):
        if chunk_idx not in self._chunks:
            return
        chunk = self._chunks[chunk_idx]
        abs_start = chunk.char_offset + start
        abs_end = chunk.char_offset + end
        self._rebuild_spans(highlight_start=abs_start, highlight_end=abs_end)

    def clear_highlight(self):
        self._rebuild_spans()

    def get_text(self) -> str:
        return self._full_text

    def get_chunk(self, chunk_idx: int) -> Optional[ChunkData]:
        return self._chunks.get(chunk_idx)

    def get_chunk_offset(self, chunk_idx: int) -> int:
        chunk = self._chunks.get(chunk_idx)
        return chunk.char_offset if chunk else 0

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def set_time(self, text: str):
        self._time_label.value = text
        self._safe_update(self._time_label)

    def _rebuild_spans(self, highlight_start: int = -1, highlight_end: int = -1):
        if not self._full_text:
            self._text_control.spans = []
            self._text_control.value = ""
            self._safe_update(self._text_control)
            return

        colors = self._theme.colors
        spans = []

        if highlight_start >= 0 and highlight_end > highlight_start:
            # Type ignore since Pyre is confusing python slicing here
            before = self._full_text[: int(highlight_start)] # type: ignore
            active = self._full_text[int(highlight_start) : int(highlight_end)] # type: ignore
            after = self._full_text[int(highlight_end) :] # type: ignore

            if before:
                spans.append(ft.TextSpan(
                    text=before,
                    style=ft.TextStyle(color=colors.highlight_spoken),
                ))
            spans.append(ft.TextSpan(
                text=active,
                style=ft.TextStyle(
                    color=colors.highlight_active,
                    bgcolor=colors.bg_input,
                    weight=ft.FontWeight.BOLD,
                ),
            ))
            if after:
                spans.append(ft.TextSpan(
                    text=after,
                    style=ft.TextStyle(color=colors.highlight_unspoken),
                ))
        else:
            spans.append(ft.TextSpan(
                text=self._full_text,
                style=ft.TextStyle(color=colors.highlight_unspoken),
            ))

        self._text_control.value = None
        self._text_control.spans = spans
        self._safe_update(self._text_control)

    def _handle_copy(self, e):
        if self._on_copy and self._full_text:
            self._on_copy(self._full_text)

    def _safe_update(self, control):
        try:
            control.update()
        except Exception:
            pass
