from __future__ import annotations

import logging

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.infrastructure.flet_log_handler import LogEntry

_LEVEL_COLORS = {
    logging.DEBUG:    "#64748b",
    logging.INFO:     "#94a3b8",
    logging.WARNING:  "#f59e0b",
    logging.ERROR:    "#ef4444",
    logging.CRITICAL: "#dc2626",
}

_MAX_VISIBLE = 500


class LogPage(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme

        self._list = ft.ListView(
            spacing=0,
            auto_scroll=True,
            expand=True,
        )

        header = ft.Row(
            controls=[
                ft.Text(
                    "Logs",
                    size=theme.typography.font_size_sm,
                    color=theme.colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_size=14,
                    icon_color=theme.colors.text_muted,
                    tooltip="Clear logs",
                    on_click=self._handle_clear,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.content = ft.Column(
            controls=[header, self._list],
            spacing=4,
            expand=True,
        )
        self.bgcolor = theme.colors.bg_dark
        self.padding = ft.padding.all(8)
        self.expand = True

    def append(self, entry: LogEntry) -> None:
        color = _LEVEL_COLORS.get(entry.level, self._theme.colors.text_dim)
        line = ft.Text(
            f"{entry.formatted_time}  {entry.level_name:>8}  [{entry.module}] {entry.message}",
            size=self._theme.typography.font_size_xs,
            color=color,
            font_family="Courier New",
            no_wrap=True,
            selectable=True,
        )
        self._list.controls.append(line)
        if len(self._list.controls) > _MAX_VISIBLE:
            self._list.controls = self._list.controls[-_MAX_VISIBLE:]
        self._safe_update(self._list)

    def clear(self) -> None:
        self._list.controls.clear()
        self._safe_update(self._list)

    def _handle_clear(self, _e=None) -> None:
        self.clear()

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
