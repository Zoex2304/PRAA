from __future__ import annotations

from typing import Optional, Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class CompactBarComponent(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        on_toggle_expand: Optional[Callable] = None,
        on_toggle_play: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_toggle_expand = on_toggle_expand
        self._on_toggle_play = on_toggle_play
        self._on_close = on_close

        self._status_icon = ft.Icon(
            ft.Icons.CIRCLE,
            size=10,
            color=theme.colors.status_idle,
        )
        self._status_text = ft.Text(
            value="PRAA",
            size=theme.typography.font_size_sm,
            color=theme.colors.text_primary,
            weight=ft.FontWeight.BOLD,
        )
        self._play_btn = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            icon_size=18,
            icon_color=theme.colors.accent,
            on_click=lambda _: self._on_toggle_play() if self._on_toggle_play else None,
        )
        self._close_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=14,
            icon_color=theme.colors.text_muted,
            on_click=lambda _: self._on_close() if self._on_close else None,
        )

        self.content = ft.Row(
            controls=[
                self._status_icon,
                self._status_text,
                ft.Container(expand=True),
                self._play_btn,
                self._close_btn,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.bgcolor = self._theme.colors.bg_dark
        self.border_radius = ft.border_radius.all(12)
        self.padding = ft.padding.symmetric(horizontal=12, vertical=4)
        self.height = self._theme.dimensions.compact_height
        self.on_click = lambda _: self._on_toggle_expand() if self._on_toggle_expand else None

    def set_status(self, text: str, color: str):
        self._status_text.value = text
        self._status_icon.color = color
        self._safe_update(self._status_text)
        self._safe_update(self._status_icon)

    def set_play_icon(self, is_playing: bool, is_paused: bool = False):
        if is_playing:
            self._play_btn.icon = ft.Icons.PAUSE
        elif is_paused:
            self._play_btn.icon = ft.Icons.PLAY_ARROW
        else:
            self._play_btn.icon = ft.Icons.PLAY_ARROW
        self._safe_update(self._play_btn)

    def _safe_update(self, control):
        try:
            control.update()
        except Exception:
            pass
