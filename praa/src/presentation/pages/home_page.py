from __future__ import annotations

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.milestone_component import MilestoneComponent
from src.presentation.components.spectrum_component import SpectrumComponent
from src.presentation.components.transcript_component import TranscriptComponent


class HomePage(ft.Container):
    """Expanded home view. Content switches between idle/processing/playing states."""

    def __init__(self, theme: ThemeConfig, home_spectrum: SpectrumComponent, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme

        # home_spectrum is the full-size (height=40) instance owned by FletApp
        self.spectrum = home_spectrum
        self.transcript = TranscriptComponent(theme, on_copy=self._copy_to_clipboard)
        self.milestone = MilestoneComponent(theme)

        self._playing_view = ft.Column(
            controls=[self.spectrum, self.transcript],
            spacing=4,
            expand=True,
        )

        self._inner = ft.Column(
            controls=[],
            spacing=0,
            expand=True,
        )

        self.content = self._inner
        self.expand = True
        self.padding = ft.padding.symmetric(horizontal=4, vertical=2)

    def show_idle(self) -> None:
        self._inner.controls = []
        self._safe_update(self._inner)

    def show_processing(self) -> None:
        self._inner.controls = [self.milestone]
        self._safe_update(self._inner)

    def show_playing(self) -> None:
        self._inner.controls = [self._playing_view]
        self._safe_update(self._inner)

    def _copy_to_clipboard(self, text: str) -> None:
        if self.page:
            self.page.set_clipboard(text)
            self.page.open(
                ft.SnackBar(
                    content=ft.Text("Copied to clipboard"),
                    duration=1500,
                )
            )

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
