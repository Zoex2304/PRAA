from __future__ import annotations

import flet as ft

from src.domain.config.theme_config import ThemeConfig

_LABELS = ["Capturing", "Processing", "Synthesizing", "Starting playback"]


class CompactMilestoneBar(ft.Container):
    """Single-line processing indicator that sits in the compact bar center slot."""

    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._step_idx = 0

        self._spinner = ft.ProgressRing(
            width=14,
            height=14,
            stroke_width=2,
            color=theme.colors.accent,
        )
        self._label = ft.Text(
            "Preparing…",
            size=theme.typography.font_size_xs,
            color=theme.colors.accent,
        )

        self.content = ft.Row(
            controls=[self._spinner, self._label],
            spacing=8,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.expand = True
        self.key = "bar-milestone"

    def advance_to(self, step_idx: int, detail: str = "") -> None:
        self._step_idx = step_idx
        label = _LABELS[step_idx] if step_idx < len(_LABELS) else "Processing"
        self._label.value = f"{label}: {detail}" if detail else label
        self._safe_update(self._label)

    def update_detail(self, step_idx: int, detail: str) -> None:
        label = _LABELS[step_idx] if step_idx < len(_LABELS) else "Processing"
        self._label.value = f"{label}: {detail}" if detail else label
        self._safe_update(self._label)

    def reset(self) -> None:
        self._step_idx = 0
        self._label.value = "Preparing…"
        self._safe_update(self._label)

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
