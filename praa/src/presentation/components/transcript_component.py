from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.download_audio_component import DownloadAudioComponent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkData:
    index: int
    text: str


class TranscriptComponent(ft.Container):
    """Transcript display with per-chunk ListView items, word highlighting, and auto-scroll.

    Each chunk is a separate ft.Text keyed by "chunk_{idx}".
    highlight_relative() updates only the active chunk's spans and calls
    list.scroll_to(key=...) to keep the spoken word in view automatically.
    """

    def __init__(
        self,
        theme: ThemeConfig,
        on_copy: Optional[Callable] = None,
        on_download_requested: Optional[Callable[[List[Path]], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_copy = on_copy
        self._chunks: dict[int, ChunkData] = {}
        self._chunk_texts: dict[int, ft.Text] = {}
        self._full_text = ""
        self._prev_highlight_chunk = -1

        self._copy_btn = ft.IconButton(
            icon=ft.Icons.COPY,
            icon_size=14,
            icon_color=theme.colors.text_muted,
            tooltip="Copy transcript",
            on_click=self._handle_copy,
        )
        self._time_label = ft.Text(
            value="0:00",
            size=theme.typography.font_size_sm,
            color=theme.colors.text_muted,
        )
        self._download = DownloadAudioComponent(theme, on_download_requested)

        header = ft.Row(
            controls=[
                ft.Text(
                    "Transcript",
                    size=theme.typography.font_size_sm,
                    color=theme.colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Row(
                    controls=[self._time_label, self._download, self._copy_btn],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self._list = ft.ListView(
            spacing=8,
            auto_scroll=False,
            expand=True,
        )

        self.content = ft.Column(
            controls=[header, self._list],
            spacing=4,
            expand=True,
        )
        self.bgcolor = theme.colors.bg_surface
        self.border_radius = 8
        self.padding = ft.padding.all(8)
        self.expand = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_content(self, chunks: list[str]) -> None:
        self._chunks = {i: ChunkData(index=i, text=text) for i, text in enumerate(chunks)}
        self._full_text = "\n\n".join(chunks)
        self._prev_highlight_chunk = -1
        self._rebuild_list()
        logger.info("Transcript loaded: %d chunks, %d chars", len(chunks), len(self._full_text))

    def clear_content(self) -> None:
        self._chunks.clear()
        self._chunk_texts.clear()
        self._full_text = ""
        self._prev_highlight_chunk = -1
        self._list.controls.clear()
        self._safe_update(self._list)

    def highlight_relative(self, chunk_idx: int, start: int, end: int) -> None:
        if chunk_idx not in self._chunks:
            return

        # Clear previous chunk highlight when transitioning chunks
        if self._prev_highlight_chunk != chunk_idx and self._prev_highlight_chunk >= 0:
            self._reset_chunk_to_spoken(self._prev_highlight_chunk)

        chunk = self._chunks[chunk_idx]
        text = chunk.text
        colors = self._theme.colors
        spans: list[ft.TextSpan] = []

        if start > 0:
            spans.append(ft.TextSpan(
                text=text[:start],
                style=ft.TextStyle(color=colors.highlight_spoken),
            ))
        spans.append(ft.TextSpan(
            text=text[start:end],
            style=ft.TextStyle(
                color=colors.highlight_active,
                bgcolor=colors.bg_input,
                weight=ft.FontWeight.BOLD,
            ),
        ))
        if end < len(text):
            spans.append(ft.TextSpan(
                text=text[end:],
                style=ft.TextStyle(color=colors.highlight_unspoken),
            ))

        ctrl = self._chunk_texts.get(chunk_idx)
        if ctrl:
            ctrl.value = None
            ctrl.spans = spans
            self._safe_update(ctrl)

        # Auto-scroll to keep the active chunk visible
        try:
            self._list.scroll_to(key=f"chunk_{chunk_idx}", duration=300)
        except Exception:
            pass

        self._prev_highlight_chunk = chunk_idx

    def clear_highlight(self) -> None:
        if self._prev_highlight_chunk >= 0:
            self._reset_chunk_to_spoken(self._prev_highlight_chunk)
        self._prev_highlight_chunk = -1

    def get_text(self) -> str:
        return self._full_text

    def set_audio_pending(self) -> None:
        self._download.set_pending()

    def set_audio_ready(self, paths: List[Path]) -> None:
        self._download.set_ready(paths)

    def reset_audio(self) -> None:
        self._download.reset()

    def set_time(self, text: str) -> None:
        self._time_label.value = text
        self._safe_update(self._time_label)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_list(self) -> None:
        colors = self._theme.colors
        self._chunk_texts.clear()
        self._list.controls.clear()

        for i, chunk in self._chunks.items():
            ctrl = ft.Text(
                value=None,
                key=f"chunk_{i}",
                spans=[ft.TextSpan(
                    text=chunk.text,
                    style=ft.TextStyle(color=colors.highlight_unspoken),
                )],
                size=self._theme.typography.font_size_md,
                selectable=True,
            )
            self._chunk_texts[i] = ctrl
            self._list.controls.append(ctrl)

        self._safe_update(self._list)

    def _reset_chunk_to_spoken(self, chunk_idx: int) -> None:
        chunk = self._chunks.get(chunk_idx)
        ctrl = self._chunk_texts.get(chunk_idx)
        if chunk and ctrl:
            ctrl.value = None
            ctrl.spans = [ft.TextSpan(
                text=chunk.text,
                style=ft.TextStyle(color=self._theme.colors.highlight_spoken),
            )]
            self._safe_update(ctrl)

    def _handle_copy(self, _e=None) -> None:
        if self._on_copy and self._full_text:
            self._on_copy(self._full_text)

    def _safe_update(self, control) -> None:
        try:
            control.update()
        except Exception:
            pass
