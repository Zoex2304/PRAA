from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class AudioPlayerComponent(ft.Container):
    """Compact play/pause button bound to a specific chunk index.

    Enabled only when the chunk is in a playable state (ready / done).
    Calls on_play(chunk_index) or on_pause(chunk_index) when clicked.
    Can be embedded anywhere: queue rows, debug panels, etc.
    """

    def __init__(
        self,
        theme: ThemeConfig,
        chunk_index: int,
        on_play: Callable[[int], None] | None = None,
        on_pause: Callable[[int], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._chunk_index = chunk_index
        self._on_play = on_play
        self._on_pause = on_pause
        self._is_playing = False

        self._btn = ft.IconButton(
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE,
            icon_size=18,
            icon_color=theme.colors.text_muted,
            disabled=True,
            on_click=self._handle_click,
            style=ft.ButtonStyle(padding=ft.padding.all(2)),
        )
        self.content = self._btn

    def set_playing(self, is_playing: bool) -> None:
        self._is_playing = is_playing
        self._btn.icon = (
            ft.Icons.PAUSE_CIRCLE_OUTLINE
            if is_playing
            else ft.Icons.PLAY_CIRCLE_OUTLINE
        )
        self._btn.icon_color = (
            self._theme.colors.accent
            if is_playing
            else self._theme.colors.status_playing
        )
        self._safe_update(self._btn)

    def set_enabled(self, enabled: bool) -> None:
        self._btn.disabled = not enabled
        if not enabled:
            self._btn.icon_color = self._theme.colors.text_muted
        elif not self._is_playing:
            self._btn.icon_color = self._theme.colors.status_playing
        self._safe_update(self._btn)

    def _handle_click(self, _e) -> None:
        if self._is_playing:
            if self._on_pause:
                self._on_pause(self._chunk_index)
        else:
            if self._on_play:
                self._on_play(self._chunk_index)

    def _safe_update(self, control) -> None:
        with contextlib.suppress(Exception):
            control.update()
