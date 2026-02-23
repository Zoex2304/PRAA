from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.splash_slides import SLIDES


class SplashComponent(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        on_dismiss: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_dismiss = on_dismiss
        self._current_index = 0

        colors = theme.colors
        typo = theme.typography

        # Close (X) button — top-right; skips the intro entirely
        close_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=16,
            icon_color=colors.text_muted,
            tooltip="Skip introduction",
            on_click=lambda _: self._dismiss(),
        )

        # Back button
        self._back_button = ft.ElevatedButton(
            "BACK",
            style=ft.ButtonStyle(
                bgcolor=colors.bg_panel,
                color=colors.text_dim,
                text_style=ft.TextStyle(
                    size=typo.font_size_xs,
                    weight=ft.FontWeight.BOLD,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
            ),
            on_click=self._handle_back,
        )

        # Next / Get Started button
        self._next_button = ft.ElevatedButton(
            "Next",
            icon=ft.Icons.ARROW_FORWARD,
            style=ft.ButtonStyle(
                bgcolor=colors.accent,
                color=colors.bg_dark,
                text_style=ft.TextStyle(
                    size=typo.font_size_xs,
                    weight=ft.FontWeight.BOLD,
                ),
                padding=ft.padding.symmetric(horizontal=20, vertical=8),
            ),
            on_click=self._handle_next,
        )

        # Slide content (updated per slide).
        # NOTE: Mutating ft.Icon.name with an IconData object after construction
        # fails silently in Flet's _set_attr serialization (always renders circle).
        # Fix: wrap in a Container and replace .content with a fresh ft.Icon per slide.
        self._icon_slot = ft.Container(
            content=ft.Icon(ft.Icons.CIRCLE, size=48, color=colors.accent),
        )
        self._slide_title = ft.Text(
            size=typo.font_size_sm + 2,
            color=colors.text_primary,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self._slide_body = ft.Text(
            size=typo.font_size_xs,
            color=colors.text_dim,
            text_align=ft.TextAlign.CENTER,
        )

        # Indicator dots row
        self._dots_row = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        )

        # Slide column (center-aligned content)
        slide_col = ft.Column(
            controls=[
                ft.Container(expand=True),
                self._icon_slot,
                ft.Container(height=8),
                self._slide_title,
                ft.Container(height=6),
                self._slide_body,
                ft.Container(height=16),
                self._dots_row,
                ft.Container(height=16),
                ft.Row(
                    controls=[self._back_button, self._next_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                ),
                ft.Container(expand=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )

        # Stack: slide content + floating close button at top-right
        self.content = ft.Stack(
            controls=[
                slide_col,
                ft.Container(
                    content=close_btn,
                    top=4,
                    right=4,
                ),
            ],
            expand=True,
        )
        self.bgcolor = colors.bg_panel
        self.expand = True
        self.border_radius = 8

        self._update_slide()

    def _update_slide(self) -> None:
        colors = self._theme.colors
        slide = SLIDES[self._current_index]
        total = len(SLIDES)
        is_last = self._current_index == total - 1

        # Replace the icon control entirely — mutating ft.Icon.name after
        # construction fails silently in Flet's serialization layer.
        self._icon_slot.content = ft.Icon(slide.icon, size=48, color=colors.accent)
        self._slide_title.value = slide.title
        self._slide_body.value = slide.body

        # Back button state
        self._back_button.disabled = self._current_index == 0
        self._back_button.style.color = (
            colors.text_muted if self._current_index == 0 else colors.text_dim
        )

        # Next button label
        self._next_button.text = "Get Started" if is_last else "Next"
        self._next_button.icon = ft.Icons.CHECK if is_last else ft.Icons.ARROW_FORWARD

        # Indicator dots
        self._dots_row.controls.clear()
        for i in range(total):
            dot = ft.Container(
                width=10,
                height=10,
                border_radius=5,
                bgcolor=colors.accent if i == self._current_index else None,
                border=(
                    None
                    if i == self._current_index
                    else ft.border.all(2, colors.accent)
                ),
            )
            self._dots_row.controls.append(dot)

        # Push changes to the client. Silently skip during __init__ (not yet mounted).
        with contextlib.suppress(Exception):
            self.update()

    def _handle_back(self, _e=None) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._update_slide()

    def _handle_next(self, _e=None) -> None:
        if self._current_index == len(SLIDES) - 1:
            self._dismiss()
        else:
            self._current_index += 1
            self._update_slide()

    def _dismiss(self) -> None:
        if self._on_dismiss:
            self._on_dismiss()
