from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ColorsConfig(BaseModel):
    bg_dark: str = "#0f0f1a"
    bg_panel: str = "#1a1a2e"
    bg_surface: str = "#16162a"
    bg_input: str = "#0f3460"
    accent: str = "#0f9d9a"
    accent_hover: str = "#0d8a87"
    accent_light: str = "#14cfc9"
    border_subtle: str = "#334155"
    text_primary: str = "#e2e8f0"
    text_dim: str = "#94a3b8"
    text_muted: str = "#64748b"
    danger: str = "#ef4444"
    spectrum: list[str] = Field(default_factory=lambda: [
        "#0f9d9a", "#14cfc9", "#00e5ff", "#0ea5e9", "#06b6d4",
    ])
    status_idle: str = "#64748b"
    status_processing: str = "#f59e0b"
    status_playing: str = "#22c55e"
    status_error: str = "#ef4444"
    highlight_active: str = "#FFFF00"
    highlight_spoken: str = "#e2e8f0"
    highlight_unspoken: str = "#94a3b8"
    chunk_pending: str = "#334155"
    chunk_processing: str = "#f59e0b"
    chunk_ready: str = "#06b6d4"
    chunk_playing: str = "#22c55e"
    chunk_done: str = "#64748b"


class DimensionsConfig(BaseModel):
    widget_width: int = 480
    compact_height: int = 52
    expanded_height: int = 600
    spectrum_bar_count: int = 16
    spectrum_bar_gap: int = 2


class TypographyConfig(BaseModel):
    font_family: str = "Inter"
    font_size_xs: int = 9
    font_size_sm: int = 11
    font_size_md: int = 13
    font_size_lg: int = 16


class ThemeConfig(BaseModel):
    colors: ColorsConfig = Field(default_factory=ColorsConfig)
    dimensions: DimensionsConfig = Field(default_factory=DimensionsConfig)
    typography: TypographyConfig = Field(default_factory=TypographyConfig)

    @classmethod
    def load(cls, path: Path) -> ThemeConfig:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls.model_validate(data)
        return cls()

    @classmethod
    def load_from_base(cls, base_dir: Path) -> ThemeConfig:
        return cls.load(base_dir / "config" / "theme.json")
