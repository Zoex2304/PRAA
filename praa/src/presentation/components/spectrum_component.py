from __future__ import annotations

import contextlib

import flet as ft
import flet.canvas as cv

from src.domain.config.theme_config import ThemeConfig


class SpectrumComponent(ft.Container):
    def __init__(self, theme: ThemeConfig, height: int = 40, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._height = height
        self._bars: list[float] = [0.0] * theme.dimensions.spectrum_bar_count
        self._canvas = cv.Canvas(
            width=theme.dimensions.widget_width,
            height=height,
            shapes=[],
        )
        self.content = self._canvas
        self.height = self._height
        self.bgcolor = self._theme.colors.bg_dark

    def update_bars(self, bars: list[float]):
        self._bars = bars
        self._redraw()

    def _redraw(self):
        colors = self._theme.colors.spectrum
        num_bars = len(self._bars)
        width = self._theme.dimensions.widget_width
        gap = self._theme.dimensions.spectrum_bar_gap
        bar_w = max(2, (width - num_bars * gap) // num_bars)
        shapes = []

        for i, magnitude in enumerate(self._bars):
            bar_h = max(2, magnitude * (self._height - 4))
            x = i * (bar_w + gap) + gap
            y = self._height - 2 - bar_h
            color = colors[i % len(colors)]
            shapes.append(
                cv.Rect(
                    x=x,
                    y=y,
                    width=bar_w,
                    height=bar_h,
                    paint=ft.Paint(color=color, style=ft.PaintingStyle.FILL),
                )
            )

        self._canvas.shapes = shapes
        with contextlib.suppress(Exception):
            self._canvas.update()
