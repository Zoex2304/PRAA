from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from src.domain.config.models import AppConfig
from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.compact_bar_component import CompactBarComponent
from src.presentation.components.compact_milestone_bar import CompactMilestoneBar
from src.presentation.components.chunk_progress_component import ChunkProgressComponent
from src.presentation.components.spectrum_component import SpectrumComponent
from src.presentation.components.upload_section_component import UploadSectionComponent
from src.presentation.navigation_controller import NavigationController, ViewType
from src.presentation.pages.home_page import HomePage
from src.presentation.pages.debug_page import DebugPage
from src.presentation.pages.history_page import HistoryPage
from src.presentation.pages.log_page import LogPage

logger = logging.getLogger(__name__)

_BAR_SPECTRUM_HEIGHT = 26
_HOME_SPECTRUM_HEIGHT = 40


class FletApp:
    def __init__(
        self,
        theme: ThemeConfig,
        config: Optional[AppConfig] = None,
        get_sessions=None,
        on_load_session=None,
        on_toggle_play: Optional[Callable] = None,
        on_settings_voice: Optional[Callable[[str], None]] = None,
        on_settings_language: Optional[Callable[[str], None]] = None,
        on_play_chunk: Optional[Callable[[int], None]] = None,
        on_pause_chunk: Optional[Callable[[int], None]] = None,
        on_seek_chunk: Optional[Callable[[int], None]] = None,
        on_seek_position: Optional[Callable[[int, float], None]] = None,
        on_download_audio_requested: Optional[Callable[[List[Path]], None]] = None,
        on_download_save: Optional[Callable[[List[Path], Path], None]] = None,
        on_file_uploaded: Optional[Callable[[Path], None]] = None,
    ):
        self._theme = theme
        self._config = config
        self._get_sessions = get_sessions
        self._on_load_session = on_load_session
        self._on_toggle_play = on_toggle_play
        self._on_settings_voice = on_settings_voice
        self._on_settings_language = on_settings_language
        self._on_play_chunk = on_play_chunk
        self._on_pause_chunk = on_pause_chunk
        self._on_seek_chunk = on_seek_chunk
        self._on_seek_position = on_seek_position
        self._on_download_audio_requested = on_download_audio_requested
        self._on_download_save = on_download_save
        self._on_file_uploaded = on_file_uploaded

        self._page: Optional[ft.Page] = None
        self._expanded = False
        self._phase = "idle"          # "idle" | "processing" | "playing"
        self._nav: Optional[NavigationController] = None
        self._pending_download_paths: List[Path] = []

        # Singleton controls created in setup()
        self.compact_milestone: Optional[CompactMilestoneBar] = None
        self.bar_spectrum: Optional[SpectrumComponent] = None
        self._home_spectrum: Optional[SpectrumComponent] = None

        self.home: Optional[HomePage] = None
        self.debug: Optional[DebugPage] = None
        self.history: Optional[HistoryPage] = None
        self.logs: Optional[LogPage] = None
        self.compact_bar: Optional[CompactBarComponent] = None
        self.chunk_progress: Optional[ChunkProgressComponent] = None

        self._content_area: Optional[ft.Container] = None
        self._nav_bar: Optional[ft.Row] = None
        self._nav_buttons: dict[ViewType, ft.Container] = {}
        self._upload_section: Optional[UploadSectionComponent] = None
        self._expanded_panel: Optional[ft.Column] = None

    def setup(self, page: ft.Page) -> None:
        self._page = page
        self._nav = NavigationController(self._theme, page)

        page.title = "PRAA"
        page.window.width = self._theme.dimensions.widget_width
        page.window.height = self._theme.dimensions.compact_height
        page.window.always_on_top = True
        page.window.frameless = True
        page.window.bgcolor = ft.Colors.TRANSPARENT
        page.bgcolor = ft.Colors.TRANSPARENT
        page.padding = 0
        page.spacing = 0

        # Singleton content controls
        self.compact_milestone = CompactMilestoneBar(self._theme)
        self.bar_spectrum = SpectrumComponent(self._theme, height=_BAR_SPECTRUM_HEIGHT)
        self._home_spectrum = SpectrumComponent(self._theme, height=_HOME_SPECTRUM_HEIGHT)

        self.home = HomePage(
            self._theme,
            home_spectrum=self._home_spectrum,
            on_play_chunk=self._on_play_chunk,
            on_pause_chunk=self._on_pause_chunk,
            on_seek_chunk=self._on_seek_chunk,
            on_seek_position=self._on_seek_position,
            on_download_requested=self._on_download_audio_requested,
        )
        self.debug = DebugPage(
            self._theme,
            on_play_chunk=self._on_play_chunk,
            on_pause_chunk=self._on_pause_chunk,
        )
        self.history = HistoryPage(
            self._theme,
            get_sessions=self._get_sessions,
            on_load_session=self._on_load_session,
        )
        self.logs = LogPage(self._theme)

        self.compact_bar = CompactBarComponent(
            self._theme,
            on_toggle_expand=self._toggle_expand,
            on_toggle_play=self._on_toggle_play,
            on_settings=self._open_settings,
            on_close=self._on_close,
        )
        self.chunk_progress = ChunkProgressComponent(self._theme)

        self._content_area = ft.Container(content=self.home, expand=True)

        colors = self._theme.colors
        self._nav_buttons = {}
        nav_items = ft.Row(
            controls=[
                self._nav_btn("Home",    ft.Icons.HOME,        ViewType.HOME,    selected=True),
                self._nav_btn("Debug",   ft.Icons.BUG_REPORT,  ViewType.DEBUG),
                self._nav_btn("History", ft.Icons.HISTORY,     ViewType.HISTORY),
                self._nav_btn("Logs",    ft.Icons.TERMINAL,    ViewType.LOGS),
            ],
            spacing=0,
        )
        upload_btn = ft.IconButton(
            icon=ft.Icons.UPLOAD_FILE,
            icon_size=16,
            icon_color=colors.text_muted,
            tooltip="Upload file",
            on_click=self._open_upload_dialog,
        )
        self._nav_bar = ft.Row(
            controls=[nav_items, upload_btn],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self._upload_section = UploadSectionComponent(self._theme)

        self._expanded_panel = ft.Column(
            controls=[
                self._nav_bar,
                self._upload_section,
                self._content_area,
            ],
            spacing=2,
            expand=True,
            visible=False,
        )

        root = ft.Container(
            content=ft.Column(
                controls=[
                    ft.WindowDragArea(content=self.compact_bar, expand=False),
                    self._expanded_panel,
                ],
                spacing=0,
                expand=True,
            ),
            bgcolor=self._theme.colors.bg_dark,
            border_radius=12,
            border=ft.border.all(1, self._theme.colors.border_subtle),
            expand=True,
        )

        self._nav.on_view_change(self._on_view_change)
        page.add(root)

    # ----------------------------------------------------------------
    # Phase management
    # ----------------------------------------------------------------

    def set_phase(self, phase: str) -> None:
        self._phase = phase
        self._update_bar_center()
        if self._expanded:
            self._update_expanded_home()

    def advance_milestone(self, step_idx: int, detail: str = "") -> None:
        if self.compact_milestone:
            self.compact_milestone.advance_to(step_idx, detail)
        if self.home:
            self.home.milestone.advance_to(step_idx, detail)

    def update_milestone_detail(self, step_idx: int, detail: str) -> None:
        if self.compact_milestone:
            self.compact_milestone.update_detail(step_idx, detail)
        if self.home:
            self.home.milestone.update_active_detail(step_idx, detail)

    def complete_milestone(self) -> None:
        if self.home:
            self.home.milestone.complete_all()

    def update_spectra(self, bars: list[float]) -> None:
        if self.bar_spectrum:
            self.bar_spectrum.update_bars(bars)
        if self._home_spectrum:
            self._home_spectrum.update_bars(bars)

    # ----------------------------------------------------------------
    # Queue / Timeline passthrough
    # ----------------------------------------------------------------

    def setup_queue(self, n_chunks: int) -> None:
        if self.home:
            self.home.queue.setup(n_chunks)
            self.home.timeline.setup(n_chunks)
        if self.debug:
            self.debug.queue.setup(n_chunks)

    def update_queue_status(self, index: int, status: str, name: str = "") -> None:
        if self.home:
            self.home.queue.update_chunk_status(index, status, name)
            self.home.timeline.update_chunk_status(index, status)
        if self.debug:
            self.debug.update_chunk_status(index, status, name)

    def update_queue_progress(self, index: int, current_ms: float, total_ms: float) -> None:
        if self.home:
            self.home.queue.update_chunk_progress(index, current_ms, total_ms)
            self.home.timeline.update_playback(index, current_ms, total_ms)
        if self.debug:
            self.debug.update_chunk_progress(index, current_ms, total_ms)

    def reset_queue(self) -> None:
        if self.home:
            self.home.queue.reset()
            self.home.timeline.reset()
        if self.debug:
            self.debug.reset_chunks()

    def activate_bar(self) -> None:
        if self.compact_bar:
            self.compact_bar.activate()

    # ----------------------------------------------------------------
    # Transcript audio state
    # ----------------------------------------------------------------

    def set_audio_pending(self) -> None:
        if self.home:
            self.home.set_audio_pending()

    def set_audio_ready(self, paths: List[Path]) -> None:
        if self.home:
            self.home.set_audio_ready(paths)

    def reset_transcript_audio(self) -> None:
        if self.home:
            self.home.reset_audio()

    def save_audio_dialog(self, paths: List[Path]) -> None:
        self._pending_download_paths = list(paths)
        if self._page:
            self._page.run_task(self._do_save_dialog)

    # ----------------------------------------------------------------
    # Upload record management
    # ----------------------------------------------------------------

    def add_upload_record(self, record) -> None:
        if self._upload_section:
            self._upload_section.add_record(record)

    def advance_upload_step(self, source_path: Path, step: int) -> None:
        if self._upload_section:
            self._upload_section.advance_card_step(source_path, step)

    def complete_upload_card(self, source_path: Path) -> None:
        if self._upload_section:
            self._upload_section.complete_card(source_path)

    # ----------------------------------------------------------------
    # Expand / Collapse
    # ----------------------------------------------------------------

    def expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True
        if self.compact_bar:
            self.compact_bar.set_bar_content(None)
            self.compact_bar.set_expand_icon(True)
        self._update_expanded_home()
        self._apply_expand_state()

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False
        if self.compact_bar:
            self.compact_bar.set_expand_icon(False)
        self._update_bar_center()
        self._apply_expand_state()

    def show(self) -> None:
        if self._page:
            self._page.window.visible = True
            self._page.update()

    def hide(self) -> None:
        if self._page:
            self._page.window.visible = False
            self._page.update()

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    async def _open_upload_dialog(self, _e=None) -> None:
        files = await ft.FilePicker().pick_files(
            dialog_title="Select a file to read aloud",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["txt", "md", "pdf", "docx", "png", "jpg", "jpeg", "bmp"],
            allow_multiple=False,
        )
        if files and self._on_file_uploaded:
            for f in files:
                if f.path:
                    self._on_file_uploaded(Path(f.path))

    async def _do_save_dialog(self) -> None:
        if not self._pending_download_paths:
            return
        name = "praa_audio.wav" if len(self._pending_download_paths) == 1 else "praa_audio_merged.wav"
        save_path = await ft.FilePicker().save_file(
            dialog_title="Save audio",
            file_name=name,
            allowed_extensions=["wav"],
        )
        if save_path and self._on_download_save:
            self._on_download_save(list(self._pending_download_paths), Path(save_path))
            self._pending_download_paths = []

    def _toggle_expand(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def _update_bar_center(self) -> None:
        if not self.compact_bar:
            return
        if self._expanded:
            self.compact_bar.set_bar_content(None)
            return
        if self._phase == "processing":
            self.compact_bar.set_bar_content(self.compact_milestone)
        elif self._phase == "playing":
            self.compact_bar.set_bar_content(self.bar_spectrum)
        else:
            self.compact_bar.set_bar_content(None)

    def _update_expanded_home(self) -> None:
        if not self.home:
            return
        if self._phase == "processing":
            self.home.show_processing()
        elif self._phase == "playing":
            self.home.show_playing()
        else:
            self.home.show_idle()

    def _apply_expand_state(self) -> None:
        if self._expanded_panel is not None:
            self._expanded_panel.visible = self._expanded
        if self._page:
            dim = self._theme.dimensions
            self._page.window.height = (
                dim.expanded_height if self._expanded else dim.compact_height
            )
            self._safe_update(self._expanded_panel)
            self._page.update()

    def _on_close(self) -> None:
        if self._page:
            self._page.window.visible = False
            self._page.update()

    def _open_settings(self) -> None:
        if not self._page or not self._config:
            return
        colors = self._theme.colors
        typo = self._theme.typography

        from src.domain.config.voices_config import VOICE_CATALOG, LANGUAGE_OPTIONS

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
                subtitle=ft.Text(v.gender_label, size=typo.font_size_xs, color=colors.text_muted),
                dense=True,
                on_click=lambda _, vid=v.voice_id: self._handle_voice(vid),
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
                on_click=lambda _, lc=lang.code: self._handle_language(lc),
            )

        def section_hdr(text: str) -> ft.Container:
            return ft.Container(
                content=ft.Text(text, size=typo.font_size_xs, color=colors.text_muted, weight=ft.FontWeight.BOLD),
                padding=ft.padding.only(left=8, top=8, bottom=2),
            )

        content = ft.Column(
            controls=[
                section_hdr("Voice Model"),
                *[voice_tile(v) for v in VOICE_CATALOG],
                ft.Divider(height=1, color=colors.border_subtle),
                section_hdr("Language"),
                *[lang_tile(l) for l in LANGUAGE_OPTIONS],
            ],
            spacing=0,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            width=300,
        )

        self._settings_dlg = ft.AlertDialog(
            modal=False,
            bgcolor=colors.bg_panel,
            title=ft.Text("Settings", size=typo.font_size_sm, color=colors.text_primary, weight=ft.FontWeight.BOLD),
            content=content,
            actions=[ft.TextButton("Close", on_click=lambda _: self._page.pop_dialog(), style=ft.ButtonStyle(color=colors.accent))],
        )
        self._page.show_dialog(self._settings_dlg)

    def _handle_voice(self, voice_id: str) -> None:
        if self._on_settings_voice:
            self._on_settings_voice(voice_id)
        if hasattr(self, "_settings_dlg") and self._page:
            self._page.pop_dialog()

    def _handle_language(self, lang_code: str) -> None:
        if self._on_settings_language:
            self._on_settings_language(lang_code)
        if hasattr(self, "_settings_dlg") and self._page:
            self._page.pop_dialog()

    def _nav_btn(
        self, label: str, icon, view: ViewType, selected: bool = False
    ) -> ft.Container:
        colors = self._theme.colors
        btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icon,
                        size=13,
                        color=colors.accent if selected else colors.text_muted,
                    ),
                    ft.Text(
                        label,
                        size=self._theme.typography.font_size_xs,
                        color=colors.accent if selected else colors.text_muted,
                        weight=ft.FontWeight.BOLD if selected else None,
                    ),
                ],
                spacing=4,
            ),
            on_click=lambda _, v=view: self._nav.navigate(v),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=20,
            bgcolor=colors.bg_surface if selected else None,
        )
        self._nav_buttons[view] = btn
        return btn

    def _on_view_change(self, view: ViewType) -> None:
        if self._content_area is None:
            return

        page_map = {
            ViewType.HOME:    self.home,
            ViewType.DEBUG:   self.debug,
            ViewType.HISTORY: self.history,
            ViewType.LOGS:    self.logs,
        }

        if view == ViewType.HISTORY and self.history:
            self.history.refresh()

        self._content_area.content = page_map.get(view)

        colors = self._theme.colors
        for v, btn in self._nav_buttons.items():
            is_sel = v == view
            btn.bgcolor = colors.bg_surface if is_sel else None
            row = btn.content
            if isinstance(row, ft.Row) and len(row.controls) >= 2:
                row.controls[0].color = colors.accent if is_sel else colors.text_muted
                row.controls[1].color = colors.accent if is_sel else colors.text_muted
                row.controls[1].weight = ft.FontWeight.BOLD if is_sel else None

        self._safe_update(self._content_area)
        self._safe_update(self._nav_bar)

    def _safe_update(self, control) -> None:
        if control is None:
            return
        try:
            control.update()
        except Exception:
            pass
