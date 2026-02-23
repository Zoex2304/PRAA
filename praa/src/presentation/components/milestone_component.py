from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import Enum, auto

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class MilestoneStatus(Enum):
    PENDING = auto()
    ACTIVE = auto()
    DONE = auto()
    ERROR = auto()


@dataclass
class _Step:
    label: str
    status: MilestoneStatus = MilestoneStatus.PENDING
    detail: str = ""


_STEP_LABELS = [
    "Capturing text",
    "Processing content",
    "Synthesizing audio",
    "Starting playback",
]


class MilestoneComponent(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._steps = [_Step(label=s) for s in _STEP_LABELS]
        self._icon_slots: list[ft.Container] = []
        self._label_texts: list[ft.Text] = []
        self._detail_texts: list[ft.Text] = []
        self._rows: list[ft.Row] = []

        step_col = ft.Column(spacing=14)
        colors = theme.colors

        for i in range(len(self._steps)):
            icon_slot = ft.Container(
                width=20,
                height=20,
                alignment=ft.alignment.Alignment(0, 0),
            )
            label = ft.Text(
                _STEP_LABELS[i],
                size=theme.typography.font_size_sm,
                color=colors.text_muted,
            )
            detail = ft.Text(
                "",
                size=theme.typography.font_size_xs,
                color=colors.text_muted,
                visible=False,
            )
            self._icon_slots.append(icon_slot)
            self._label_texts.append(label)
            self._detail_texts.append(detail)

            row = ft.Row(
                controls=[
                    icon_slot,
                    ft.Column(
                        controls=[label, detail],
                        spacing=2,
                        tight=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self._rows.append(row)
            step_col.controls.append(row)

        self.content = ft.Column(
            controls=[
                ft.Text(
                    "Processing",
                    size=theme.typography.font_size_sm,
                    color=colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                step_col,
            ],
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )
        self.expand = True
        self.padding = ft.padding.symmetric(horizontal=20, vertical=16)
        self._render_all()

    def advance_to(self, step_idx: int, detail: str = "") -> None:
        for i in range(step_idx):
            if self._steps[i].status != MilestoneStatus.DONE:
                self._steps[i].status = MilestoneStatus.DONE
                self._steps[i].detail = ""
                self._render_step(i)
        if step_idx < len(self._steps):
            self._steps[step_idx].status = MilestoneStatus.ACTIVE
            self._steps[step_idx].detail = detail
            self._render_step(step_idx)

    def update_active_detail(self, step_idx: int, detail: str) -> None:
        if 0 <= step_idx < len(self._steps):
            self._steps[step_idx].detail = detail
            self._detail_texts[step_idx].value = detail
            self._detail_texts[step_idx].visible = bool(detail)
            self._safe_update(self._detail_texts[step_idx])

    def complete_all(self) -> None:
        for i in range(len(self._steps)):
            self._steps[i].status = MilestoneStatus.DONE
            self._steps[i].detail = ""
            self._render_step(i)

    def reset(self) -> None:
        for i in range(len(self._steps)):
            self._steps[i].status = MilestoneStatus.PENDING
            self._steps[i].detail = ""
            self._render_step(i)

    def _render_all(self) -> None:
        for i in range(len(self._steps)):
            self._render_step(i)

    def _render_step(self, idx: int) -> None:
        step = self._steps[idx]
        colors = self._theme.colors

        if step.status == MilestoneStatus.PENDING:
            icon: ft.Control = ft.Icon(
                ft.Icons.RADIO_BUTTON_UNCHECKED,
                size=16,
                color=colors.text_muted,
            )
            label_color = colors.text_muted
        elif step.status == MilestoneStatus.ACTIVE:
            icon = ft.ProgressRing(
                width=16,
                height=16,
                stroke_width=2,
                color=colors.accent,
            )
            label_color = colors.accent
        elif step.status == MilestoneStatus.DONE:
            icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_OUTLINE,
                size=16,
                color=colors.status_playing,
            )
            label_color = colors.text_dim
        else:
            icon = ft.Icon(
                ft.Icons.ERROR_OUTLINE,
                size=16,
                color=colors.status_error,
            )
            label_color = colors.status_error

        self._icon_slots[idx].content = icon
        self._label_texts[idx].color = label_color
        self._detail_texts[idx].value = step.detail
        self._detail_texts[idx].visible = bool(step.detail)

        self._safe_update(self._icon_slots[idx])
        self._safe_update(self._label_texts[idx])
        self._safe_update(self._detail_texts[idx])

    def _safe_update(self, control: ft.Control) -> None:
        with contextlib.suppress(Exception):
            control.update()
