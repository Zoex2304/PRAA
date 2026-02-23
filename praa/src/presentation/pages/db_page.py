from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig

logger = logging.getLogger(__name__)


class DbPage(ft.Container):
    def __init__(
        self,
        theme: ThemeConfig,
        get_stats: Callable[[], dict] | None = None,
        on_clear_cache: Callable[[], int] | None = None,
        on_flush_all: Callable[[], dict] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._get_stats = get_stats
        self._on_clear_cache = on_clear_cache
        self._on_flush_all = on_flush_all

        colors = theme.colors
        typo = theme.typography

        self._session_count_text = ft.Text(
            "—",
            size=typo.font_size_sm,
            color=colors.text_primary,
            weight=ft.FontWeight.BOLD,
        )
        self._cache_size_text = ft.Text(
            "—",
            size=typo.font_size_sm,
            color=colors.text_primary,
            weight=ft.FontWeight.BOLD,
        )
        self._status_text = ft.Text(
            "",
            size=typo.font_size_xs,
            color=colors.accent,
        )

        stats_row = ft.Row(
            controls=[
                self._stat_card("Sessions", self._session_count_text),
                self._stat_card("Cache", self._cache_size_text),
            ],
            spacing=8,
        )

        clear_btn = ft.ElevatedButton(
            "Clear Audio Cache",
            icon=ft.Icons.DELETE_SWEEP,
            style=ft.ButtonStyle(
                bgcolor=colors.bg_input,
                color=colors.text_primary,
                text_style=ft.TextStyle(size=typo.font_size_xs),
            ),
            on_click=self._confirm_clear_cache,
        )

        flush_btn = ft.ElevatedButton(
            "Flush All Data",
            icon=ft.Icons.DELETE_FOREVER,
            style=ft.ButtonStyle(
                bgcolor="#7f1d1d",
                color="#fca5a5",
                text_style=ft.TextStyle(size=typo.font_size_xs),
            ),
            on_click=self._confirm_flush_all,
        )

        self.content = ft.Column(
            controls=[
                ft.Text(
                    "Database & Cache",
                    size=typo.font_size_sm,
                    color=colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                stats_row,
                ft.Divider(height=1, color=colors.border_subtle),
                ft.Text(
                    "Clear audio cache files while keeping session history.",
                    size=typo.font_size_xs,
                    color=colors.text_dim,
                ),
                clear_btn,
                ft.Container(height=4),
                ft.Text(
                    "Permanently delete all sessions and cached audio.",
                    size=typo.font_size_xs,
                    color=colors.text_dim,
                ),
                flush_btn,
                self._status_text,
            ],
            spacing=8,
            expand=True,
        )
        self.bgcolor = colors.bg_panel
        self.padding = ft.padding.all(10)
        self.expand = True

    def refresh(self) -> None:
        if self._get_stats:
            try:
                stats = self._get_stats()
                self._session_count_text.value = str(stats.get("session_count", 0))
                cache_mb = stats.get("cache_size_mb", 0)
                self._cache_size_text.value = f"{cache_mb:.1f} MB"
                self._safe_update(self._session_count_text)
                self._safe_update(self._cache_size_text)
            except Exception:
                logger.exception("Failed to refresh DB stats")

    # ------------------------------------------------------------------
    # Confirm dialogs
    # ------------------------------------------------------------------

    def _confirm_clear_cache(self, _e=None) -> None:
        if not self.page:
            return
        colors = self._theme.colors
        typo = self._theme.typography

        def _do_clear(_):
            self.page.pop_dialog()
            if self._on_clear_cache:
                count = self._on_clear_cache()
                self._set_status(f"Deleted {count} cache files.")
                self.refresh()

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=colors.bg_panel,
            title=ft.Text(
                "Clear Audio Cache?", size=typo.font_size_sm, color=colors.text_primary
            ),
            content=ft.Text(
                "All cached audio files will be deleted.\nSession history records are kept.",
                size=typo.font_size_xs,
                color=colors.text_dim,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda _: self.page.pop_dialog(),
                    style=ft.ButtonStyle(color=colors.text_muted),
                ),
                ft.TextButton(
                    "Clear", on_click=_do_clear, style=ft.ButtonStyle(color="#f87171")
                ),
            ],
        )
        self.page.show_dialog(dlg)

    def _confirm_flush_all(self, _e=None) -> None:
        if not self.page:
            return
        colors = self._theme.colors
        typo = self._theme.typography

        def _do_flush(_):
            self.page.pop_dialog()
            if self._on_flush_all:
                result = self._on_flush_all()
                ocr = result.get("ocr_files", 0)
                ocr_part = f", {ocr} OCR files" if ocr else ""
                self._set_status(
                    f"Deleted {result.get('sessions', 0)} sessions, "
                    f"{result.get('files', 0)} cache files{ocr_part}. "
                    "Restart PRAA to see the onboarding screen."
                )
                self.refresh()

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=colors.bg_panel,
            title=ft.Text(
                "Flush All Data?",
                size=typo.font_size_sm,
                color="#fca5a5",
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Text(
                "This will permanently delete ALL session history, cached audio,\n"
                "and OCR debug screenshots. App state is fully reset.\n"
                "Restart PRAA after flushing to see the onboarding screen again.",
                size=typo.font_size_xs,
                color=colors.text_dim,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda _: self.page.pop_dialog(),
                    style=ft.ButtonStyle(color=colors.text_muted),
                ),
                ft.TextButton(
                    "Delete Everything",
                    on_click=_do_flush,
                    style=ft.ButtonStyle(color="#ef4444"),
                ),
            ],
        )
        self.page.show_dialog(dlg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _stat_card(self, label: str, value_control: ft.Control) -> ft.Container:
        colors = self._theme.colors
        typo = self._theme.typography
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(label, size=typo.font_size_xs, color=colors.text_muted),
                    value_control,
                ],
                spacing=2,
                tight=True,
            ),
            bgcolor=colors.bg_surface,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            expand=True,
        )

    def _set_status(self, msg: str) -> None:
        self._status_text.value = msg
        self._safe_update(self._status_text)

    def _safe_update(self, control: ft.Control) -> None:
        with contextlib.suppress(Exception):
            control.update()
