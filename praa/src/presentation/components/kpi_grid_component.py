from __future__ import annotations

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class _KpiTile(ft.Container):
    def __init__(self, theme: ThemeConfig, label: str):
        self._value_text = ft.Text(
            "—",
            size=theme.typography.font_size_sm,
            color=theme.colors.accent,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        super().__init__(
            content=ft.Column(
                controls=[
                    ft.Text(
                        label,
                        size=theme.typography.font_size_xs,
                        color=theme.colors.text_muted,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    self._value_text,
                ],
                spacing=1,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=theme.colors.bg_surface,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=6, vertical=6),
            expand=True,
        )

    def set_value(self, value: str) -> None:
        self._value_text.value = value
        try:
            self._value_text.update()
        except Exception:
            pass


class KpiGridComponent(ft.Container):
    """Displays process metrics as a flat KPI grid.  No collapsible — always visible."""

    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._rss     = _KpiTile(theme, "RSS")
        self._vms     = _KpiTile(theme, "VMS")
        self._pid     = _KpiTile(theme, "PID")
        self._threads = _KpiTile(theme, "Threads")

        self.content = ft.Row(
            controls=[self._rss, self._vms, self._pid, self._threads],
            spacing=4,
        )
        self.padding = ft.padding.symmetric(vertical=4)

    def refresh(self, rss_mb: float, vms_mb: float, pid: int, threads: int) -> None:
        self._rss.set_value(f"{rss_mb:.0f} MB")
        self._vms.set_value(f"{vms_mb:.0f} MB")
        self._pid.set_value(str(pid))
        self._threads.set_value(str(threads))
