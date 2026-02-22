from __future__ import annotations

from typing import Callable, Optional

import flet as ft

from src.domain.config.models import AppConfig
from src.domain.config.theme_config import ThemeConfig
from src.domain.config.voices_config import VOICE_CATALOG, LANGUAGE_OPTIONS


class SettingsMenuComponent(ft.Container):
    """Vertical ⋮ button that opens a voice/language settings dialog.

    Voice and language options are driven by voices_config.py — adding
    a new language or voice model requires only a catalog entry, not
    any structural code change.
    """

    def __init__(
        self,
        theme: ThemeConfig,
        config: AppConfig,
        on_voice_change: Optional[Callable[[str], None]] = None,
        on_language_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._config = config
        self._on_voice_change = on_voice_change
        self._on_language_change = on_language_change
        self._page: Optional[ft.Page] = None
        self._dialog: Optional[ft.AlertDialog] = None

        self._btn = ft.IconButton(
            icon=ft.Icons.MORE_VERT,
            icon_size=16,
            icon_color=theme.colors.text_muted,
            tooltip="Settings",
            on_click=self._open_dialog,
            style=ft.ButtonStyle(padding=ft.padding.all(4)),
        )
        self.content = self._btn

    def set_page(self, page: ft.Page) -> None:
        self._page = page

    def update_config(self, config: AppConfig) -> None:
        """Called when config changes externally to keep selection in sync."""
        self._config = config

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open_dialog(self, _e=None) -> None:
        if not self._page:
            return

        colors = self._theme.colors
        typo = self._theme.typography

        def section_header(text: str) -> ft.Container:
            return ft.Container(
                content=ft.Text(
                    text,
                    size=typo.font_size_xs,
                    color=colors.text_muted,
                    weight=ft.FontWeight.BOLD,
                ),
                padding=ft.padding.only(left=8, top=8, bottom=2),
            )

        def voice_tile(v) -> ft.ListTile:
            selected = (
                (v.language_code == "id" and v.voice_id == self._config.voice_id)
                or (v.language_code == "en" and v.voice_id == self._config.voice_en)
            )
            return ft.ListTile(
                leading=ft.Icon(
                    ft.Icons.RADIO_BUTTON_ON if selected else ft.Icons.RADIO_BUTTON_OFF,
                    color=colors.accent if selected else colors.text_muted,
                    size=14,
                ),
                title=ft.Text(
                    v.display_label,
                    size=typo.font_size_sm,
                    color=colors.text_primary if selected else colors.text_dim,
                ),
                subtitle=ft.Text(
                    v.gender_label,
                    size=typo.font_size_xs,
                    color=colors.text_muted,
                ),
                dense=True,
                on_click=lambda _, vid=v.voice_id: self._select_voice(vid),
            )

        def lang_tile(lang) -> ft.ListTile:
            selected = self._config.language_preference.value == lang.code
            return ft.ListTile(
                leading=ft.Icon(
                    ft.Icons.RADIO_BUTTON_ON if selected else ft.Icons.RADIO_BUTTON_OFF,
                    color=colors.accent if selected else colors.text_muted,
                    size=14,
                ),
                title=ft.Text(
                    lang.label,
                    size=typo.font_size_sm,
                    color=colors.text_primary if selected else colors.text_dim,
                ),
                dense=True,
                on_click=lambda _, lc=lang.code: self._select_language(lc),
            )

        content = ft.Column(
            controls=[
                section_header("Voice Model"),
                *[voice_tile(v) for v in VOICE_CATALOG],
                ft.Divider(height=1, color=colors.border_subtle),
                section_header("Language"),
                *[lang_tile(l) for l in LANGUAGE_OPTIONS],
            ],
            spacing=0,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            width=300,
        )

        self._dialog = ft.AlertDialog(
            modal=False,
            bgcolor=colors.bg_panel,
            title=ft.Text(
                "Settings",
                size=typo.font_size_sm,
                color=colors.text_primary,
                weight=ft.FontWeight.BOLD,
            ),
            content=content,
            actions=[
                ft.TextButton(
                    "Close",
                    on_click=lambda _: self._close(),
                    style=ft.ButtonStyle(color=colors.accent),
                )
            ],
        )
        self._page.open(self._dialog)

    def _select_voice(self, voice_id: str) -> None:
        if self._on_voice_change:
            self._on_voice_change(voice_id)
        self._close()

    def _select_language(self, lang_code: str) -> None:
        if self._on_language_change:
            self._on_language_change(lang_code)
        self._close()

    def _close(self) -> None:
        if self._dialog and self._page:
            self._page.close(self._dialog)
            self._dialog = None
