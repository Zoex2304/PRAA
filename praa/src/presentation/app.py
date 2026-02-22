from __future__ import annotations

import logging
from enum import Enum, auto

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.presentation.components.compact_bar_component import CompactBarComponent
from src.presentation.components.chunk_progress_component import ChunkProgressComponent
from src.presentation.pages.home_page import HomePage
from src.presentation.pages.debug_page import DebugPage
from src.presentation.pages.history_page import HistoryPage

logger = logging.getLogger(__name__)


class ViewType(Enum):
    HOME = auto()
    DEBUG = auto()
    HISTORY = auto()


from typing import Callable

class NavigationController:
    def __init__(self, theme: ThemeConfig, page: ft.Page):
        self._theme = theme
        self._page = page
        self._current_view = ViewType.HOME
        self._callbacks: list[Callable] = []

    @property
    def current_view(self) -> ViewType:
        return self._current_view

    def on_view_change(self, callback: Callable):
        self._callbacks.append(callback)

    def navigate(self, view: ViewType):
        if view == self._current_view:
            return
        self._current_view = view
        for cb in self._callbacks:
            cb(view)


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
        self._expanded = True
        self._nav: NavigationController | None = None

        self.home: HomePage | None = None
        self.debug: DebugPage | None = None
        self.history: HistoryPage | None = None
        self.compact_bar: CompactBarComponent | None = None
        self.chunk_progress: ChunkProgressComponent | None = None

        self._content_area: ft.Container | None = None
        self._nav_bar: ft.Row | None = None
        self._nav_buttons: dict[ViewType, ft.Container] = {}
        self._expanded_panel: ft.Column | None = None
        self._root: ft.Container | None = None

    def setup(self, page: ft.Page):
        self._page = page
        self._nav = NavigationController(self._theme, page)

        page.title = "PRAA"
        page.window.width = self._theme.dimensions.widget_width
        page.window.height = self._theme.dimensions.expanded_height
        page.window.always_on_top = True
        page.window.frameless = True
        page.window.bgcolor = ft.Colors.TRANSPARENT
        page.bgcolor = ft.Colors.TRANSPARENT
        page.padding = 0
        page.spacing = 0

        self.home = HomePage(self._theme)
        self.debug = DebugPage(self._theme)
        self.history = HistoryPage(
            self._theme,
            get_sessions=self._get_sessions,
            on_load_session=self._on_load_session,
        )
        self.compact_bar = CompactBarComponent(
            self._theme,
            on_toggle_expand=self._toggle_expand,
            on_close=self._on_close,
        )
        self.chunk_progress = ChunkProgressComponent(self._theme)

        self._content_area = ft.Container(
            content=self.home,
            expand=True,
        )

        self._nav_bar = ft.Row(
            controls=[
                self._nav_btn("Home", ft.Icons.HOME, ViewType.HOME, selected=True),
                self._nav_btn("Debug", ft.Icons.BUG_REPORT, ViewType.DEBUG),
                self._nav_btn("History", ft.Icons.HISTORY, ViewType.HISTORY),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
        )
        self._nav_buttons: dict[ViewType, ft.Container] = {}

        self._expanded_panel = ft.Column(
            controls=[
                self._nav_bar,
                self.chunk_progress,
                self._content_area,
            ],
            spacing=2,
            expand=True,
        )

        self._root = ft.Container(
            content=ft.Column(
                controls=[
                    ft.GestureDetector(
                        content=self.compact_bar,
                        on_pan_start=self._start_drag,
                        on_pan_update=self._do_drag,
                    ),
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

        if self._nav is not None:
            self._nav.on_view_change(self._on_view_change)
        if self._root is not None:
            page.add(self._root)

    def _nav_btn(self, label: str, icon, view: ViewType, selected: bool = False) -> ft.Container:
        colors = self._theme.colors
        btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=14, color=colors.accent if selected else colors.text_muted),
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
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            border_radius=20,
            bgcolor=colors.bg_surface if selected else None,
        )
        self._nav_buttons[view] = btn
        return btn

    def _on_view_change(self, view: ViewType):
        if self._content_area is not None:
            if view == ViewType.HOME:
                self._content_area.content = self.home
            elif view == ViewType.DEBUG:
                self._content_area.content = self.debug
            elif view == ViewType.HISTORY:
                if self.history is not None:
                    self.history.refresh()
                self._content_area.content = self.history

        colors = self._theme.colors
        for v, btn in self._nav_buttons.items():
            is_sel = v == view
            btn.bgcolor = colors.bg_surface if is_sel else None
            row = btn.content
            if isinstance(row, ft.Row) and len(row.controls) >= 2:
                row.controls[0].color = colors.accent if is_sel else colors.text_muted
                row.controls[1].color = colors.accent if is_sel else colors.text_muted
                row.controls[1].weight = ft.FontWeight.BOLD if is_sel else None

        if self._content_area is not None:
            self._safe_update(self._content_area)
        if self._nav_bar is not None:
            self._safe_update(self._nav_bar)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded_panel is not None:
            self._expanded_panel.visible = self._expanded
        if self._page:
            dim = self._theme.dimensions
            self._page.window.height = (
                dim.expanded_height if self._expanded else dim.compact_height
            )
        if self._expanded_panel is not None:
            self._safe_update(self._expanded_panel)
        if self._page:
            self._page.update()

    def _on_close(self):
        if self._page:
            self._page.window.visible = False
            self._page.update()

    def show(self):
        if self._page:
            self._page.window.visible = True
            self._page.update()

    def hide(self):
        if self._page:
            self._page.window.visible = False
            self._page.update()

    def _start_drag(self, e: ft.DragStartEvent):
        pass

    def _do_drag(self, e: ft.DragUpdateEvent):
        if self._page and e.global_delta:
            self._page.window.left += e.global_delta.x
            self._page.window.top += e.global_delta.y
            self._page.update()

    def _safe_update(self, control):
        try:
            control.update()
        except Exception:
            pass
