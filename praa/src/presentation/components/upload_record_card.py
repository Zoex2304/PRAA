from __future__ import annotations

import contextlib
from pathlib import Path

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.domain.upload.models import UploadRecord
from src.presentation.components.vertical_stepper_component import (
    StepConfig,
    VerticalStepperComponent,
)

_UPLOAD_STEPS = [
    StepConfig("File received"),
    StepConfig("Reading content"),
    StepConfig("Splitting into chunks"),
    StepConfig("Synthesizing audio"),
    StepConfig("Ready for playback"),
]


class UploadRecordCard(ft.Container):
    def __init__(self, theme: ThemeConfig, record: UploadRecord, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._record = record
        self._expanded = True

        colors = theme.colors
        typo = theme.typography

        self._stepper = VerticalStepperComponent(theme, _UPLOAD_STEPS)
        self._arrow = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_DOWN, size=13, color=colors.text_muted
        )

        ext = record.source_path.suffix.lstrip(".").upper() or "FILE"
        type_label = "Image" if record.is_image else ext
        meta = f"{self._fmt_size(record.file_size_bytes)} · {type_label} · {record.word_count:,} words"

        header_inner = ft.Row(
            controls=[
                self._arrow,
                ft.Column(
                    controls=[
                        ft.Text(
                            record.file_name,
                            size=typo.font_size_sm,
                            color=colors.text_primary,
                            no_wrap=True,
                        ),
                        ft.Text(meta, size=typo.font_size_xs, color=colors.text_muted),
                    ],
                    spacing=2,
                    expand=True,
                    tight=True,
                ),
                ft.Icon(
                    ft.Icons.IMAGE if record.is_image else ft.Icons.DESCRIPTION,
                    size=18,
                    color=colors.text_muted,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        header = ft.Container(
            content=header_inner,
            on_click=self._toggle,
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border_radius=4,
            ink=True,
        )

        self._detail = ft.Container(
            content=ft.Container(
                content=self._stepper,
                padding=ft.padding.only(left=20, right=8, bottom=8),
            ),
            visible=True,
        )

        self.content = ft.Column(controls=[header, self._detail], spacing=0)
        self.bgcolor = colors.bg_panel
        self.border_radius = 8
        self.border = ft.border.all(1, colors.border_subtle)
        self.padding = ft.padding.all(2)

    @property
    def source_path(self) -> Path:
        return self._record.source_path

    def advance_step(self, step_idx: int) -> None:
        self._stepper.advance_to(step_idx)

    def complete(self) -> None:
        self._stepper.complete_all()
        self._collapse()

    def _collapse(self) -> None:
        self._expanded = False
        self._arrow.name = ft.Icons.KEYBOARD_ARROW_RIGHT
        self._detail.visible = False
        self._safe_update(self._arrow)
        self._safe_update(self._detail)

    def _toggle(self, _e=None) -> None:
        self._expanded = not self._expanded
        self._arrow.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN
            if self._expanded
            else ft.Icons.KEYBOARD_ARROW_RIGHT
        )
        self._detail.visible = self._expanded
        self._safe_update(self._arrow)
        self._safe_update(self._detail)

    def _fmt_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _safe_update(self, control: ft.Control) -> None:
        with contextlib.suppress(Exception):
            control.update()
