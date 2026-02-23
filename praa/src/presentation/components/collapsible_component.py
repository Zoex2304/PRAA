from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class CollapsibleComponent(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        label: str,
        initial_value: str = "",
        detail_builder: Callable | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._label = label
        self._expanded = False
        self._detail_builder = detail_builder

        self._value_text = ft.Text(
            value=initial_value,
            size=theme.typography.font_size_sm,
            color=theme.colors.text_dim,
        )
        self._arrow = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_RIGHT,
            size=14,
            color=theme.colors.text_muted,
        )
        self._detail_container = ft.Container(visible=False)

        header = ft.Container(
            content=ft.Row(
                controls=[
                    self._arrow,
                    ft.Text(
                        value=self._label,
                        size=self._theme.typography.font_size_sm,
                        color=self._theme.colors.text_muted,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(expand=True),
                    self._value_text,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=self._toggle,
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border_radius=4,
            ink=True,
        )
        self.content = ft.Column(
            controls=[header, self._detail_container],
            spacing=0,
        )

    def set_value(self, value: str):
        self._value_text.value = value
        self._safe_update(self._value_text)

    def set_detail_content(self, content: ft.Control):
        self._detail_container.content = ft.Container(
            content=content,
            padding=ft.padding.only(left=22, right=8, bottom=8),
        )
        if self._expanded:
            self._safe_update(self._detail_container)

    def _toggle(self, _e=None):
        self._expanded = not self._expanded
        self._arrow.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN
            if self._expanded
            else ft.Icons.KEYBOARD_ARROW_RIGHT
        )
        self._detail_container.visible = self._expanded

        if self._expanded and self._detail_builder:
            content = self._detail_builder()
            if content:
                self.set_detail_content(content)

        self._safe_update(self._arrow)
        self._safe_update(self._detail_container)

    def _safe_update(self, control):
        with contextlib.suppress(Exception):
            control.update()
