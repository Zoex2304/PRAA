"""Widget UI construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .theme import (
    BG_DARK, BG_PANEL, BG_INPUT,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT,
    TEXT_PRIMARY, TEXT_DIM, WIDGET_WIDTH,
)
from src.domain.config.models import VoiceGender

if TYPE_CHECKING:
    from .service import WidgetService


class UIBuilder:
    """Constructs compact bar and expanded panel."""

    @staticmethod
    def build_compact_bar(widget: WidgetService) -> None:
        root = widget._root

        compact = ctk.CTkFrame(root, fg_color=BG_DARK, height=60, corner_radius=0)
        compact.grid(row=0, column=0, sticky="ew")
        compact.grid_columnconfigure(2, weight=1)
        widget._compact_frame = compact

        compact.bind("<Button-1>", widget._start_drag)
        compact.bind("<B1-Motion>", widget._do_drag)

        widget._status_dot = ctk.CTkLabel(
            compact, text="\u25cf", font=ctk.CTkFont(size=16),
            text_color="#64748b", width=24,
        )
        widget._status_dot.grid(row=0, column=0, padx=(12, 2), pady=8)

        name_lbl = ctk.CTkLabel(
            compact, text="PRAA",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=ACCENT_LIGHT, width=45,
        )
        name_lbl.grid(row=0, column=1, padx=(0, 4), pady=8)
        name_lbl.bind("<Button-1>", widget._start_drag)
        name_lbl.bind("<B1-Motion>", widget._do_drag)

        widget._status_label = ctk.CTkLabel(
            compact, text="Idle",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DIM, anchor="w",
        )
        widget._status_label.grid(row=0, column=2, padx=4, pady=8, sticky="w")
        widget._status_label.bind("<Button-1>", widget._start_drag)
        widget._status_label.bind("<B1-Motion>", widget._do_drag)

        widget._speed_label = ctk.CTkLabel(
            compact, text=f"{widget._config.speed_rate:.1f}x",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT, width=36,
        )
        widget._speed_label.grid(row=0, column=3, padx=2, pady=8)

        widget._expand_btn = ctk.CTkButton(
            compact, text="\u25bc", width=28, height=28,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            hover_color=BG_PANEL, text_color=TEXT_DIM,
            command=widget._toggle_expand,
        )
        widget._expand_btn.grid(row=0, column=4, padx=1, pady=8)

        widget._minimize_btn = ctk.CTkButton(
            compact, text="\u2500", width=28, height=28,
            font=ctk.CTkFont(size=14, weight="bold"), fg_color="transparent",
            hover_color=BG_PANEL, text_color=TEXT_DIM,
            command=widget.hide,
        )
        widget._minimize_btn.grid(row=0, column=5, padx=1, pady=8)

        widget._close_btn = ctk.CTkButton(
            compact, text="\u2715", width=28, height=28,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            hover_color="#ef4444", text_color=TEXT_DIM,
            command=widget._on_close,
        )
        widget._close_btn.grid(row=0, column=6, padx=(1, 8), pady=8)

    @staticmethod
    def build_expanded_panel(widget: WidgetService) -> None:
        root = widget._root
        config = widget._config

        expanded = ctk.CTkFrame(root, fg_color=BG_DARK, corner_radius=0)
        expanded.grid(row=1, column=0, sticky="nsew")
        root.grid_rowconfigure(1, weight=1)
        widget._expanded_frame = expanded

        controls = ctk.CTkFrame(expanded, fg_color=BG_PANEL, corner_radius=8)
        controls.pack(fill="x", padx=8, pady=(4, 2))
        widget._controls_frame = controls

        ctk.CTkLabel(
            controls, text="Voice", font=ctk.CTkFont(size=10),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=(10, 4), pady=6)

        current_voice = "Ardi" if config.voice_gender == VoiceGender.MALE else "Gadis"
        widget._voice_var = ctk.StringVar(value=current_voice)
        widget._voice_menu = ctk.CTkOptionMenu(
            controls, variable=widget._voice_var,
            values=["Ardi", "Gadis"], width=70, height=24,
            font=ctk.CTkFont(size=11), fg_color=BG_INPUT,
            button_color=ACCENT, command=widget._on_voice_change,
        )
        widget._voice_menu.pack(side="left", padx=2, pady=6)

        widget._speed_var = ctk.StringVar(value=f"{config.speed_rate:.1f}x")
        widget._speed_menu = ctk.CTkOptionMenu(
            controls, variable=widget._speed_var,
            values=["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"],
            width=65, height=24, font=ctk.CTkFont(size=11),
            fg_color=BG_INPUT, button_color=ACCENT,
            command=widget._on_speed_change,
        )
        widget._speed_menu.pack(side="left", padx=2, pady=6)

        ctk.CTkFrame(controls, width=1, height=16, fg_color="#334155").pack(
            side="left", padx=6, pady=8
        )

        btn_style = dict(
            width=32, height=32, font=ctk.CTkFont(size=14),
            fg_color="transparent", hover_color=BG_INPUT,
            text_color=TEXT_PRIMARY, corner_radius=4,
        )

        widget._btn_toggle = ctk.CTkButton(
            controls, text="\u25b6 Play", width=60, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY, corner_radius=16,
            command=widget._on_toggle_play,
        )
        widget._btn_toggle.pack(side="left", padx=4, pady=4)

        widget._save_btn = ctk.CTkButton(
            controls, text="Save",
            command=widget._on_save_audio, **btn_style
        )
        widget._save_btn.pack(side="left", padx=2, pady=4)

        ctk.CTkFrame(controls, width=1, height=16, fg_color="#334155").pack(
            side="left", padx=6, pady=8
        )

        widget._history_btn = ctk.CTkButton(
            controls, text="History",
            command=widget._toggle_history, **btn_style
        )
        widget._history_btn.pack(side="left", padx=2, pady=4)

        widget._debug_btn = ctk.CTkButton(
            controls, text="Debug",
            command=widget._toggle_debug, **btn_style
        )
        widget._debug_btn.pack(side="left", padx=2, pady=4)

        from .components.chunk_progress import ChunkProgressMap
        widget._chunk_progress = ChunkProgressMap(expanded)
        widget._chunk_progress.pack(fill="x", padx=12, pady=(2, 4))

        widget._extra_panel_frame = ctk.CTkFrame(expanded, fg_color="transparent")
        widget._extra_panel_frame.pack(fill="x", padx=8, pady=0)

        from .components.debug_panel import DebugPanel
        widget._debug_panel = DebugPanel(widget._extra_panel_frame)
        widget._debug_panel.pack(fill="both", expand=True)

        widget._spectrum_frame = ctk.CTkFrame(
            expanded, fg_color=BG_PANEL, corner_radius=8,
        )
        widget._spectrum_frame.pack(fill="x", padx=8, pady=2)

        widget._large_spectrum = ctk.CTkCanvas(
            widget._spectrum_frame, width=WIDGET_WIDTH - 24, height=60,
            bg=BG_PANEL, highlightthickness=0,
        )
        widget._large_spectrum.pack(padx=4, pady=6)

        widget._progress_label = ctk.CTkLabel(
            expanded, text="Ready",
            font=ctk.CTkFont(size=10), text_color=TEXT_DIM, anchor="w",
        )
        widget._progress_label.pack(fill="x", padx=12, pady=(2, 0))

        widget._transcript_header = ctk.CTkFrame(expanded, fg_color="transparent")
        widget._transcript_header.pack(fill="x", padx=8, pady=(2, 0))

        ctk.CTkLabel(
            widget._transcript_header, text="Transcript",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM,
        ).pack(side="left", padx=4)

        widget._copy_btn = ctk.CTkButton(
            widget._transcript_header, text="Copy", width=60, height=22,
            font=ctk.CTkFont(size=10), fg_color=BG_INPUT,
            hover_color=ACCENT, text_color=TEXT_DIM,
            command=widget._on_copy_transcript,
        )
        widget._copy_btn.pack(side="right", padx=4)

        widget._time_label = ctk.CTkLabel(
            widget._transcript_header, text="00:00/00:00",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=ACCENT_LIGHT,
        )
        widget._time_label.pack(side="right", padx=8)

        widget._transcript_box = ctk.CTkTextbox(
            expanded,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=BG_PANEL, text_color=TEXT_DIM,
            corner_radius=8, height=240, wrap="word",
        )
        widget._transcript_box.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        widget._refresh_content_visibility()
