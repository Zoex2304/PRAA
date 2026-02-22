from __future__ import annotations

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.spectrum_component import SpectrumComponent
from src.presentation.components.transcript_component import TranscriptComponent


class HomePage(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self.spectrum = SpectrumComponent(theme, height=40)
        self.transcript = TranscriptComponent(
            theme,
            on_copy=self._copy_to_clipboard,
        )
        self.content = ft.Column(
            controls=[
                self.spectrum,
                self.transcript,
            ],
            spacing=4,
            expand=True,
        )
        self.expand = True
        self.padding = ft.padding.symmetric(horizontal=4, vertical=2)

    def _copy_to_clipboard(self, text: str):
        if self.page:
            self.page.set_clipboard(text)
            self.page.open(
                ft.SnackBar(
                    content=ft.Text("Copied to clipboard"),
                    duration=1500,
                )
            )
