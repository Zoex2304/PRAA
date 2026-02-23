from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import Any

import flet as ft

from src.domain.config.theme_config import ThemeConfig

logger = logging.getLogger(__name__)


class HistoryPage(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        get_sessions: Callable[..., Any] | None = None,
        on_load_session: Callable[..., Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._get_sessions = get_sessions
        self._on_load_session = on_load_session
        self._list_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
        header = ft.Row(
            controls=[
                ft.Text(
                    "Recent Sessions",
                    size=self._theme.typography.font_size_sm,
                    color=self._theme.colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_size=14,
                    icon_color=self._theme.colors.text_muted,
                    tooltip="Refresh",
                    on_click=lambda _: self.refresh(),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.content = ft.Column(
            controls=[header, self._list_col],
            spacing=4,
            expand=True,
        )
        self.bgcolor = self._theme.colors.bg_panel
        self.padding = ft.padding.all(8)
        self.expand = True

    def refresh(self):
        self._list_col.controls.clear()

        if not self._get_sessions:
            self._show_empty("No session provider")
            return

        sessions = self._get_sessions()
        if not sessions:
            self._show_empty("No history found")
            return

        for sess in sessions:
            card = self._build_card(sess)
            self._list_col.controls.append(card)

        self._safe_update(self._list_col)

    def _build_card(self, session) -> ft.Control:
        colors = self._theme.colors
        try:
            ts_str: str = str(getattr(session, "timestamp", ""))
            ts = ts_str.replace("T", " ")
            ts = ts[:16]
        except Exception:
            ts = str(getattr(session, "timestamp", "Unknown"))

        preview_text: str = str(getattr(session, "text_content", ""))
        preview = preview_text[:60].replace("\n", " ") + "..."

        source_type = getattr(session, "source_type", "USER_BLOCK") or "USER_BLOCK"
        source_chip = self._source_chip(source_type)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                ts,
                                size=self._theme.typography.font_size_xs,
                                color=colors.accent,
                                weight=ft.FontWeight.BOLD,
                            ),
                            source_chip,
                            ft.Container(expand=True),
                            ft.ElevatedButton(
                                "Load",
                                height=22,
                                style=ft.ButtonStyle(
                                    bgcolor=colors.bg_input,
                                    color=colors.text_primary,
                                    text_style=ft.TextStyle(
                                        size=self._theme.typography.font_size_xs,
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=8, vertical=2
                                    ),
                                ),
                                on_click=lambda _, s=session: self._handle_load(s),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        preview,
                        size=self._theme.typography.font_size_xs,
                        color=colors.text_dim,
                    ),
                ],
                spacing=2,
            ),
            bgcolor=colors.bg_surface,
            border_radius=6,
            padding=ft.padding.all(8),
        )

    def _source_chip(self, source_type: str) -> ft.Container:
        typo = self._theme.typography
        cfg = {
            "OCR": ("OCR", "#3b82f6", "#1e3a5f"),
            "FILE_UPLOAD": ("File", "#22c55e", "#14532d"),
            "USER_BLOCK": ("Clip", "#6b7280", "#1f2937"),
        }
        label, fg, bg = cfg.get(source_type, ("?", "#6b7280", "#1f2937"))
        return ft.Container(
            content=ft.Text(
                label, size=typo.font_size_xs - 1, color=fg, weight=ft.FontWeight.BOLD
            ),
            bgcolor=bg,
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=5, vertical=1),
        )

    def _show_empty(self, message: str):
        self._list_col.controls.clear()
        self._list_col.controls.append(
            ft.Container(
                content=ft.Text(
                    message,
                    size=self._theme.typography.font_size_sm,
                    color=self._theme.colors.text_muted,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.alignment.Alignment(0, 0),
                padding=ft.padding.all(20),
            )
        )
        self._safe_update(self._list_col)

    def _handle_load(self, session):
        if self._on_load_session:
            self._on_load_session(session)

    def _safe_update(self, control):
        with contextlib.suppress(Exception):
            control.update()
