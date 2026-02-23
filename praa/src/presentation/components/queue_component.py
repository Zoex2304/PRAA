from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.audio_player_component import AudioPlayerComponent


def _fmt_ms(ms: float) -> str:
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


_STATUS_CFG: dict[str, tuple[str, str, bool]] = {
    # status: (label, dot_color, playable)
    "pending": ("Pending", "#334155", False),
    "processing": ("Synthesizing", "#f59e0b", False),
    "ready": ("Ready", "#06b6d4", True),
    "playing": ("Playing", "#22c55e", True),
    "paused": ("Paused", "#eab308", True),
    "done": ("Done", "#64748b", True),
}


class _QueueRow(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        index: int,
        name: str,
        on_play: Callable[[int], None] | None,
        on_pause: Callable[[int], None] | None,
    ):
        super().__init__()
        self._theme = theme
        self._index = index

        self._dot = ft.Container(
            width=7,
            height=7,
            bgcolor=theme.colors.chunk_pending,
            border_radius=4,
        )
        self._name = ft.Text(
            name or f"Chunk {index + 1}",
            size=theme.typography.font_size_xs,
            color=theme.colors.text_dim,
            expand=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            max_lines=1,
        )
        self._status = ft.Text(
            "Pending",
            size=theme.typography.font_size_xs,
            color=theme.colors.chunk_pending,
        )
        self._time = ft.Text(
            "",
            size=theme.typography.font_size_xs,
            color=theme.colors.text_muted,
            visible=False,
        )
        self._player = AudioPlayerComponent(
            theme, index, on_play=on_play, on_pause=on_pause
        )
        self._progress = ft.ProgressBar(
            value=0,
            height=2,
            color=theme.colors.chunk_playing,
            bgcolor=theme.colors.bg_input,
            visible=False,
        )

        top = ft.Row(
            controls=[self._dot, self._name, self._status, self._time, self._player],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.content = ft.Column(controls=[top, self._progress], spacing=2)
        self.padding = ft.padding.symmetric(horizontal=8, vertical=4)
        self.border_radius = 4
        self.bgcolor = theme.colors.bg_surface

    def update_status(self, status: str, name: str = "") -> None:
        label, color, playable = _STATUS_CFG.get(
            status, ("", self._theme.colors.text_muted, False)
        )
        self._dot.bgcolor = color
        self._status.value = label
        self._status.color = color
        self._player.set_enabled(playable)
        self._player.set_playing(status == "playing")
        self._progress.visible = status in ("playing", "paused")
        self._time.visible = status in ("playing", "done")
        if name:
            self._name.value = name
        self._safe_update()

    def update_progress(self, current_ms: float, total_ms: float) -> None:
        if total_ms > 0:
            self._progress.value = min(1.0, current_ms / total_ms)
            self._time.value = f"{_fmt_ms(current_ms)} / {_fmt_ms(total_ms)}"
            self._time.visible = True
            self._safe_update()

    def _safe_update(self) -> None:
        with contextlib.suppress(Exception):
            self.update()


class QueueComponent(ft.Container):
    """Standalone collapsible queue with per-row audio player controls.

    Can be embedded in HomePage, DebugPage, or anywhere else.
    Exposes setup(), update_chunk_status(), update_chunk_progress(), reset().
    """

    def __init__(
        self,
        theme: ThemeConfig,
        on_play_chunk: Callable[[int], None] | None = None,
        on_pause_chunk: Callable[[int], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_play_chunk = on_play_chunk
        self._on_pause_chunk = on_pause_chunk
        self._rows: dict[int, _QueueRow] = {}
        self._expanded = False

        colors = theme.colors
        typo = theme.typography

        self._count_text = ft.Text(
            "—",
            size=typo.font_size_xs,
            color=colors.text_muted,
        )
        self._arrow = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_RIGHT, size=14, color=colors.text_muted
        )
        self._list_col = ft.Column(spacing=3)
        self._detail = ft.Container(
            content=ft.Container(
                content=self._list_col,
                padding=ft.padding.only(top=4, left=4, right=4),
            ),
            visible=False,
        )

        header = ft.Container(
            content=ft.Row(
                controls=[
                    self._arrow,
                    ft.Text(
                        "Queue",
                        size=typo.font_size_sm,
                        color=colors.text_muted,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(expand=True),
                    self._count_text,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=self._toggle,
            padding=ft.padding.symmetric(horizontal=4, vertical=6),
            border_radius=4,
            ink=True,
        )

        self.content = ft.Column(controls=[header, self._detail], spacing=0)
        self.bgcolor = colors.bg_panel
        self.border_radius = 6
        self.padding = ft.padding.symmetric(horizontal=4, vertical=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self, n_chunks: int) -> None:
        self._rows.clear()
        self._list_col.controls.clear()
        self._count_text.value = f"{n_chunks} chunks"
        self._safe_update(self._count_text)
        self._safe_update(self._list_col)

    def update_chunk_status(self, index: int, status: str, name: str = "") -> None:
        if index not in self._rows:
            row = _QueueRow(
                self._theme,
                index,
                name,
                on_play=self._on_play_chunk,
                on_pause=self._on_pause_chunk,
            )
            self._rows[index] = row
            self._list_col.controls.append(row)
            self._count_text.value = f"{len(self._rows)} chunks"
            self._safe_update(self._count_text)
            self._safe_update(self._list_col)
        self._rows[index].update_status(status, name)

    def update_chunk_progress(
        self, index: int, current_ms: float, total_ms: float
    ) -> None:
        if index in self._rows:
            self._rows[index].update_progress(current_ms, total_ms)

    def reset(self) -> None:
        self._rows.clear()
        self._list_col.controls.clear()
        self._count_text.value = "—"
        self._safe_update(self._count_text)
        self._safe_update(self._list_col)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _toggle(self, _e=None) -> None:
        self._expanded = not self._expanded
        self._arrow.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN
            if self._expanded
            else ft.Icons.KEYBOARD_ARROW_RIGHT
        )
        self._detail.visible = self._expanded
        self._safe_update(self._arrow)
        self._safe_update(self._detail)

    def _safe_update(self, control) -> None:
        with contextlib.suppress(Exception):
            control.update()
