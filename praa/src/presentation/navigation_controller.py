from __future__ import annotations

from enum import Enum, auto
from typing import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class ViewType(Enum):
    HOME = auto()
    DEBUG = auto()
    HISTORY = auto()
    LOGS = auto()


class NavigationController:
    def __init__(self, theme: ThemeConfig, page: ft.Page):
        self._theme = theme
        self._page = page
        self._current_view = ViewType.HOME
        self._callbacks: list[Callable[[ViewType], None]] = []

    @property
    def current_view(self) -> ViewType:
        return self._current_view

    def on_view_change(self, callback: Callable[[ViewType], None]) -> None:
        self._callbacks.append(callback)

    def navigate(self, view: ViewType) -> None:
        if view == self._current_view:
            return
        self._current_view = view
        for cb in self._callbacks:
            cb(view)
