from __future__ import annotations

import logging

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.compact_bar_component import CompactBarComponent
from src.presentation.components.compact_milestone_bar import CompactMilestoneBar
from src.presentation.components.chunk_progress_component import ChunkProgressComponent
from src.presentation.components.spectrum_component import SpectrumComponent
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
        get_sessions=None,
        on_load_session=None,
    ):
        self._theme = theme
        self._get_sessions = get_sessions
        self._on_load_session = on_load_session
        self._page: ft.Page | None = None
        self._expanded = False
        self._phase = "idle"          # "idle" | "processing" | "playing"
        self._nav: NavigationController | None = None

        # Singleton controls created in setup()
        self.compact_milestone: CompactMilestoneBar | None = None
        self.bar_spectrum: SpectrumComponent | None = None        # lives in bar center
        self._home_spectrum: SpectrumComponent | None = None     # lives in expanded home

        self.home: HomePage | None = None
        self.debug: DebugPage | None = None
        self.history: HistoryPage | None = None
        self.logs: LogPage | None = None
        self.compact_bar: CompactBarComponent | None = None
        self.chunk_progress: ChunkProgressComponent | None = None

        self._content_area: ft.Container | None = None
        self._nav_bar: ft.Row | None = None
        self._nav_buttons: dict[ViewType, ft.Container] = {}
        self._expanded_panel: ft.Column | None = None

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

        # Create singleton content controls
        self.compact_milestone = CompactMilestoneBar(self._theme)
        self.bar_spectrum = SpectrumComponent(self._theme, height=_BAR_SPECTRUM_HEIGHT)
        self._home_spectrum = SpectrumComponent(self._theme, height=_HOME_SPECTRUM_HEIGHT)

        self.home = HomePage(self._theme, home_spectrum=self._home_spectrum)
        self.debug = DebugPage(self._theme)
        self.history = HistoryPage(
            self._theme,
            get_sessions=self._get_sessions,
            on_load_session=self._on_load_session,
        )
        self.logs = LogPage(self._theme)

        self.compact_bar = CompactBarComponent(
            self._theme,
            on_toggle_expand=self._toggle_expand,
            on_close=self._on_close,
        )
        self.chunk_progress = ChunkProgressComponent(self._theme)

        self._content_area = ft.Container(content=self.home, expand=True)

        self._nav_buttons = {}
        self._nav_bar = ft.Row(
            controls=[
                self._nav_btn("Home",    ft.Icons.HOME,        ViewType.HOME,    selected=True),
                self._nav_btn("Debug",   ft.Icons.BUG_REPORT,  ViewType.DEBUG),
                self._nav_btn("History", ft.Icons.HISTORY,     ViewType.HISTORY),
                self._nav_btn("Logs",    ft.Icons.TERMINAL,    ViewType.LOGS),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
        )

        self._expanded_panel = ft.Column(
            controls=[
                self._nav_bar,
                self.chunk_progress,
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
    # Phase management — drives bar center and expanded home content
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
    # Expand / Collapse
    # ----------------------------------------------------------------

    def expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True
        # Clear bar center — content moves to expanded view
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

    def _toggle_expand(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def _update_bar_center(self) -> None:
        if not self.compact_bar:
            return
        if self._expanded:
            # When expanded, bar center is always empty — content is in expanded view
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
