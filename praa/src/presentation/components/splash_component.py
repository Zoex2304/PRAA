"""
Presentation Component — First-Run Splash Screen

Shown once on first launch. Dismissed via "Get Started" button.
"""

from __future__ import annotations

from typing import Callable, Optional

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class SplashComponent(ft.Container):
    """Full-panel first-run welcome screen."""

    def __init__(
        self,
        theme: ThemeConfig,
        on_dismiss: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_dismiss = on_dismiss

        colors = theme.colors
        typo = theme.typography

        self.content = ft.Column(
            controls=[
                ft.Container(expand=True),
                ft.Icon(ft.Icons.RECORD_VOICE_OVER, size=48, color=colors.accent),
                ft.Container(height=8),
                ft.Text(
                    "Welcome to PRAA",
                    size=typo.font_size_sm + 2,
                    color=colors.text_primary,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=6),
                ft.Text(
                    "Select any text in any app and press\n"
                    "Ctrl+Shift+R to hear it read aloud.",
                    size=typo.font_size_xs,
                    color=colors.text_dim,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=4),
                ft.Text(
                    "Press Ctrl+Shift+O for screen OCR capture.\n"
                    "Upload documents via the toolbar.",
                    size=typo.font_size_xs,
                    color=colors.text_muted,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),
                ft.ElevatedButton(
                    "Get Started",
                    icon=ft.Icons.ARROW_FORWARD,
                    on_click=self._dismiss,
                    style=ft.ButtonStyle(
                        bgcolor=colors.accent,
                        color=colors.bg_dark,
                        text_style=ft.TextStyle(
                            size=typo.font_size_xs,
                            weight=ft.FontWeight.BOLD,
                        ),
                        padding=ft.padding.symmetric(horizontal=20, vertical=10),
                    ),
                ),
                ft.Container(expand=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )
        self.bgcolor = colors.bg_panel
        self.expand = True
        self.border_radius = 8

    def _dismiss(self, _e=None) -> None:
        if self._on_dismiss:
            self._on_dismiss()
