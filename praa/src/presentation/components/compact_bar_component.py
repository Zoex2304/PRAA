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
        on_settings: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_toggle_expand = on_toggle_expand
        self._on_toggle_play = on_toggle_play
        self._on_settings = on_settings
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

        # Center animated content slot — fades between idle / milestone / spectrum
        self._idle_hint = ft.Text(
            "Select text → Ctrl+Shift+R",
            size=theme.typography.font_size_xs,
            color=theme.colors.text_dim,
            italic=True,
        )
        self._center_slot = ft.Container(content=self._idle_hint, expand=True, key="bar-idle")
        self._center_wrap = ft.Container(
            content=self._center_slot,
            expand=True,
            opacity=1.0,
            animate_opacity=ft.Animation(
                duration=350,
                curve=ft.AnimationCurve.EASE_IN_OUT,
            ),
        )

        self._expand_btn = ft.IconButton(
            icon=ft.Icons.EXPAND_MORE,
            icon_size=16,
            icon_color=theme.colors.text_muted,
            tooltip="Expand",
            on_click=lambda _: self._on_toggle_expand() if self._on_toggle_expand else None,
            visible=False,
        )
        self._play_btn = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            icon_size=18,
            icon_color=theme.colors.accent,
            on_click=lambda _: self._on_toggle_play() if self._on_toggle_play else None,
            visible=False,
        )
        self._settings_btn = ft.IconButton(
            icon=ft.Icons.MORE_VERT,
            icon_size=14,
            icon_color=theme.colors.text_muted,
            tooltip="Settings",
            on_click=lambda _: self._on_settings() if self._on_settings else None,
            visible=False,
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
                self._center_wrap,
                self._expand_btn,
                self._play_btn,
                self._settings_btn,
                self._close_btn,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.bgcolor = self._theme.colors.bg_dark
        self.border_radius = ft.border_radius.all(12)
        self.padding = ft.padding.symmetric(horizontal=8, vertical=4)
        self.height = self._theme.dimensions.compact_height

    def activate(self) -> None:
        """Called once after first hotkey — reveals action controls and clears idle hint."""
        self._expand_btn.visible = True
        self._play_btn.visible = True
        self._settings_btn.visible = True
        self._center_slot.content = None
        self._safe_update(self._expand_btn)
        self._safe_update(self._play_btn)
        self._safe_update(self._settings_btn)
        self._safe_update(self._center_wrap)

    def set_bar_content(self, control: ft.Control | None) -> None:
        self._center_wrap.opacity = 0.0
        self._safe_update(self._center_wrap)

        if control is None:
            self._center_slot.content = None
            self._center_slot.key = "bar-idle"
        else:
            self._center_slot.content = control
            self._center_slot.key = getattr(control, "key", "bar-content")

        self._center_wrap.opacity = 1.0
        self._safe_update(self._center_wrap)

    def set_expand_icon(self, is_expanded: bool) -> None:
        self._expand_btn.icon = ft.Icons.EXPAND_LESS if is_expanded else ft.Icons.EXPAND_MORE
        self._expand_btn.tooltip = "Collapse" if is_expanded else "Expand"
        self._safe_update(self._expand_btn)

    def set_status(self, text: str, color: str) -> None:
        self._status_text.value = text
        self._status_icon.color = color
        self._safe_update(self._status_text)
        self._safe_update(self._status_icon)

    def set_play_icon(self, is_playing: bool, is_paused: bool = False) -> None:
        self._play_btn.icon = ft.Icons.PAUSE if is_playing else ft.Icons.PLAY_ARROW
        self._safe_update(self._play_btn)

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
