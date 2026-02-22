from __future__ import annotations

from typing import Callable, Optional

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.chunk_timeline_component import ChunkTimelineComponent
from src.presentation.components.milestone_component import MilestoneComponent
from src.presentation.components.queue_component import QueueComponent
from src.presentation.components.spectrum_component import SpectrumComponent
from src.presentation.components.transcript_component import TranscriptComponent


class HomePage(ft.Container):
    """Expanded home view. Switches between idle / processing / playing states."""

    def __init__(
        self,
        theme: ThemeConfig,
        home_spectrum: SpectrumComponent,
        on_play_chunk: Optional[Callable[[int], None]] = None,
        on_pause_chunk: Optional[Callable[[int], None]] = None,
        on_seek_chunk: Optional[Callable[[int], None]] = None,
        on_seek_position: Optional[Callable[[int, float], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme

        self.spectrum = home_spectrum
        self.transcript = TranscriptComponent(theme, on_copy=self._copy_to_clipboard)
        self.milestone = MilestoneComponent(theme)

        # Queue + timeline live in the playing view
        self.queue = QueueComponent(
            theme,
            on_play_chunk=on_play_chunk,
            on_pause_chunk=on_pause_chunk,
        )
        self.timeline = ChunkTimelineComponent(
            theme, on_seek_chunk=on_seek_chunk, on_seek_position=on_seek_position
        )

        self._playing_view = ft.Column(
            controls=[
                self.queue,
                self.timeline,
                self.spectrum,
                self.transcript,
            ],
            spacing=4,
            expand=True,
        )

        self._inner = ft.Column(controls=[], spacing=0, expand=True)
        self.content = self._inner
        self.expand = True
        self.padding = ft.padding.symmetric(horizontal=4, vertical=2)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def show_idle(self) -> None:
        self._inner.controls = []
        self._safe_update(self._inner)

    def show_processing(self) -> None:
        self._inner.controls = [self.milestone]
        self._safe_update(self._inner)

    def show_playing(self) -> None:
        self._inner.controls = [self._playing_view]
        self._safe_update(self._inner)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self, text: str) -> None:
        if self.page:
            self.page.set_clipboard(text)
            sb = ft.SnackBar(content=ft.Text("Copied to clipboard"), duration=1500)
            self.page.overlay.append(sb)
            sb.open = True
            self.page.update()

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
