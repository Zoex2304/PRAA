from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class DownloadAudioComponent(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        on_download_requested: Callable[[list[Path]], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_download_requested = on_download_requested
        self._audio_paths: list[Path] = []

        self._spinner = ft.ProgressRing(
            width=14,
            height=14,
            stroke_width=1.5,
            color=theme.colors.text_muted,
            visible=False,
        )
        self._btn = ft.IconButton(
            icon=ft.Icons.DOWNLOAD,
            icon_size=14,
            icon_color=theme.colors.text_muted,
            tooltip="Download audio",
            on_click=self._handle_click,
            visible=False,
        )

        self.content = ft.Row(
            controls=[self._spinner, self._btn],
            spacing=0,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.visible = False

    def set_pending(self) -> None:
        self._audio_paths = []
        self._spinner.visible = True
        self._btn.visible = False
        self.visible = True
        self._safe_update(self)

    def set_ready(self, audio_paths: list[Path]) -> None:
        self._audio_paths = list(audio_paths)
        self._spinner.visible = False
        self._btn.visible = True
        self.visible = True
        self._safe_update(self)

    def reset(self) -> None:
        self._audio_paths = []
        self._spinner.visible = False
        self._btn.visible = False
        self.visible = False
        self._safe_update(self)

    def _handle_click(self, _e=None) -> None:
        if self._on_download_requested and self._audio_paths:
            self._on_download_requested(list(self._audio_paths))

    def _safe_update(self, control: ft.Control) -> None:
        with contextlib.suppress(Exception):
            control.update()
