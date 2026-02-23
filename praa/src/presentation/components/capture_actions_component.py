from __future__ import annotations

from collections.abc import Callable

import flet as ft

from src.domain.config.theme_config import ThemeConfig


class CaptureActionsComponent(ft.Row):
    def __init__(
        self,
        theme: ThemeConfig,
        on_ocr_capture: Callable | None = None,
        on_upload: Callable | None = None,
        icon_size: int = 14,
        **kwargs,
    ):
        super().__init__(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.DOCUMENT_SCANNER,
                    icon_size=icon_size,
                    icon_color=theme.colors.text_muted,
                    tooltip="OCR capture (Ctrl+Shift+O)",
                    on_click=lambda _: on_ocr_capture() if on_ocr_capture else None,
                ),
                ft.IconButton(
                    icon=ft.Icons.UPLOAD_FILE,
                    icon_size=icon_size,
                    icon_color=theme.colors.text_muted,
                    tooltip="Upload file",
                    on_click=on_upload,
                ),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            **kwargs,
        )
