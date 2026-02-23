from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class _StepStatus(Enum):
    PENDING = auto()
    ACTIVE = auto()
    DONE = auto()


@dataclass(frozen=True)
class StepConfig:
    label: str


class VerticalStepperComponent(ft.Container):

    def __init__(self, theme: ThemeConfig, steps: list[StepConfig], **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._statuses: list[_StepStatus] = [_StepStatus.PENDING] * len(steps)
        self._icon_slots: list[ft.Container] = []
        self._label_texts: list[ft.Text] = []

        step_col = ft.Column(spacing=10)
        colors = theme.colors

        for step in steps:
            icon_slot = ft.Container(
                width=16,
                height=16,
                alignment=ft.alignment.Alignment(0, 0),
            )
            label = ft.Text(
                step.label,
                size=theme.typography.font_size_sm,
                color=colors.text_muted,
            )
            self._icon_slots.append(icon_slot)
            self._label_texts.append(label)
            step_col.controls.append(
                ft.Row(
                    controls=[icon_slot, label],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        self.content = step_col
        self._render_all()

    def advance_to(self, step_idx: int) -> None:
        for i in range(len(self._statuses)):
            if i < step_idx:
                self._set_status(i, _StepStatus.DONE)
            elif i == step_idx:
                self._set_status(i, _StepStatus.ACTIVE)

    def complete_all(self) -> None:
        for i in range(len(self._statuses)):
            self._set_status(i, _StepStatus.DONE)

    def reset(self) -> None:
        for i in range(len(self._statuses)):
            self._set_status(i, _StepStatus.PENDING)

    def _render_all(self) -> None:
        for i in range(len(self._statuses)):
            self._render_slot(i)

    def _set_status(self, idx: int, status: _StepStatus) -> None:
        self._statuses[idx] = status
        self._render_slot(idx)

    def _render_slot(self, idx: int) -> None:
        colors = self._theme.colors
        status = self._statuses[idx]

        if status == _StepStatus.PENDING:
            icon: ft.Control = ft.Icon(
                ft.Icons.RADIO_BUTTON_UNCHECKED, size=14, color=colors.text_muted
            )
            label_color = colors.text_muted
        elif status == _StepStatus.ACTIVE:
            icon = ft.ProgressRing(
                width=14, height=14, stroke_width=2, color=colors.accent
            )
            label_color = colors.accent
        else:
            icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_OUTLINE, size=14, color=colors.status_playing
            )
            label_color = colors.text_dim

        self._icon_slots[idx].content = icon
        self._label_texts[idx].color = label_color
        self._safe_update(self._icon_slots[idx])
        self._safe_update(self._label_texts[idx])

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
