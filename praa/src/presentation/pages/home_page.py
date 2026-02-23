from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.chunk_timeline_component import ChunkTimelineComponent
from src.presentation.components.milestone_component import MilestoneComponent
from src.presentation.components.queue_component import QueueComponent
from src.presentation.components.spectrum_component import SpectrumComponent
from src.presentation.components.speed_control_component import SpeedControlComponent
from src.presentation.components.transcript_component import TranscriptComponent
from src.presentation.components.upload_section_component import UploadSectionComponent


class HomePage(ft.Container):

    def __init__(
        self,
        theme: ThemeConfig,
        home_spectrum: SpectrumComponent,
        on_play_chunk: Optional[Callable[[int], None]] = None,
        on_pause_chunk: Optional[Callable[[int], None]] = None,
        on_seek_chunk: Optional[Callable[[int], None]] = None,
        on_seek_position: Optional[Callable[[int, float], None]] = None,
        on_download_requested: Optional[Callable[[List[Path]], None]] = None,
        on_speed_change: Optional[Callable[[float], None]] = None,
        current_speed: float = 1.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme

        self.spectrum = home_spectrum
        self.transcript = TranscriptComponent(
            theme,
            on_copy=self._copy_to_clipboard,
            on_download_requested=on_download_requested,
        )
        self.milestone = MilestoneComponent(theme)

        # Upload progress section (Home-page only, single record)
        self.upload_section = UploadSectionComponent(theme)

        # Speed control
        self.speed_control = SpeedControlComponent(
            theme,
            current_speed=current_speed,
            on_speed_change=on_speed_change,
        )

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
                ft.Row(
                    controls=[self.speed_control],
                    alignment=ft.MainAxisAlignment.END,
                ),
                self.queue,
                self.timeline,
                self.spectrum,
                self.transcript,
                self.upload_section,
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
    # Transcript audio state passthroughs
    # ------------------------------------------------------------------

    def set_audio_pending(self) -> None:
        self.transcript.set_audio_pending()

    def set_audio_ready(self, paths: List[Path]) -> None:
        self.transcript.set_audio_ready(paths)

    def reset_audio(self) -> None:
        self.transcript.reset_audio()

    # ------------------------------------------------------------------
    # Upload section passthroughs
    # ------------------------------------------------------------------

    def add_upload_record(self, record) -> None:
        self.upload_section.add_record(record)

    def advance_upload_step(self, source_path: Path, step: int) -> None:
        self.upload_section.advance_card_step(source_path, step)

    def complete_upload_card(self, source_path: Path) -> None:
        self.upload_section.complete_card(source_path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self, text: str) -> None:
        if self.page:
            self.page.run_task(self._clipboard_set, text)

    async def _clipboard_set(self, text: str) -> None:
        clip = ft.Clipboard()
        self.page.overlay.append(clip)
        self.page.update()
        try:
            await clip.set(text)
        finally:
            self.page.overlay.remove(clip)
        sb = ft.SnackBar(content=ft.Text("Copied to clipboard"), duration=1500)
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
