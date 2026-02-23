"""
Presentation Component — Speed Control

Compact +/- speed selector for real-time playback speed adjustment.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig

_SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


class SpeedControlComponent(ft.Row):
    """Compact speed control: [-] [1.0x] [+]"""

    def __init__(
        self,
        theme: ThemeConfig,
        current_speed: float = 1.0,
        on_speed_change: Callable[[float], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._current_speed = current_speed
        self._on_speed_change = on_speed_change

        colors = theme.colors
        typo = theme.typography

        self._label = ft.Text(
            self._fmt(current_speed),
            size=typo.font_size_xs,
            color=colors.text_primary,
            weight=ft.FontWeight.BOLD,
            width=36,
            text_align=ft.TextAlign.CENTER,
        )

        dec_btn = ft.IconButton(
            icon=ft.Icons.REMOVE,
            icon_size=12,
            icon_color=colors.text_muted,
            tooltip="Decrease speed",
            on_click=self._decrease,
            width=28,
            height=28,
        )
        inc_btn = ft.IconButton(
            icon=ft.Icons.ADD,
            icon_size=12,
            icon_color=colors.text_muted,
            tooltip="Increase speed",
            on_click=self._increase,
            width=28,
            height=28,
        )

        self.controls = [
            ft.Text("Speed", size=typo.font_size_xs, color=colors.text_muted),
            dec_btn,
            self._label,
            inc_btn,
        ]
        self.spacing = 0
        self.vertical_alignment = ft.CrossAxisAlignment.CENTER

    def set_speed(self, speed: float) -> None:
        self._current_speed = speed
        self._label.value = self._fmt(speed)
        self._safe_update(self._label)

    # ------------------------------------------------------------------

    def _decrease(self, _e=None) -> None:
        idx = self._current_idx()
        if idx > 0:
            self._apply(_SPEEDS[idx - 1])

    def _increase(self, _e=None) -> None:
        idx = self._current_idx()
        if idx < len(_SPEEDS) - 1:
            self._apply(_SPEEDS[idx + 1])

    def _apply(self, speed: float) -> None:
        self._current_speed = speed
        self._label.value = self._fmt(speed)
        self._safe_update(self._label)
        if self._on_speed_change:
            self._on_speed_change(speed)

    def _current_idx(self) -> int:
        closest = min(
            range(len(_SPEEDS)), key=lambda i: abs(_SPEEDS[i] - self._current_speed)
        )
        return closest

    @staticmethod
    def _fmt(speed: float) -> str:
        if speed == int(speed):
            return f"{int(speed)}x"
        return f"{speed:.2f}".rstrip("0") + "x"

    def _safe_update(self, control: ft.Control) -> None:
        with contextlib.suppress(Exception):
            control.update()
