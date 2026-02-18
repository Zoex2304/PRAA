"""Widget UI construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .theme import (
    BG_DARK, BG_PANEL, BG_SURFACE, BG_INPUT,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT,
    BORDER_SUBTLE, TEXT_PRIMARY, TEXT_DIM, TEXT_MUTED,
    DANGER, WIDGET_WIDTH,
)
from src.domain.config.models import VoiceGender

if TYPE_CHECKING:
    from .service import WidgetService


class UIBuilder:
    """Constructs compact bar and expanded panel."""

    # ------------------------------------------------------------------
    # Compact title bar
    # ------------------------------------------------------------------

    @staticmethod
    def build_compact_bar(widget: WidgetService) -> None:
        root = widget._root

        compact = ctk.CTkFrame(root, fg_color=BG_DARK, height=52, corner_radius=0)
        compact.grid(row=0, column=0, sticky="ew")
        compact.grid_columnconfigure(2, weight=1)
        compact.grid_propagate(False)
        widget._compact_frame = compact

        compact.bind("<Button-1>", widget._start_drag)
        compact.bind("<B1-Motion>", widget._do_drag)

        # Status dot
        widget._status_dot = ctk.CTkLabel(
            compact, text="\u25cf", font=ctk.CTkFont(size=14),
            text_color=TEXT_MUTED, width=20,
        )
        widget._status_dot.grid(row=0, column=0, padx=(10, 0), pady=6)

        # App name
        name_lbl = ctk.CTkLabel(
            compact, text="PRAA",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=ACCENT_LIGHT, width=40,
        )
        name_lbl.grid(row=0, column=1, padx=(4, 4), pady=6)
        name_lbl.bind("<Button-1>", widget._start_drag)
        name_lbl.bind("<B1-Motion>", widget._do_drag)

        # Status text — clamped width
        widget._status_label = ctk.CTkLabel(
            compact, text="Idle",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM, anchor="w", width=200,
        )
        widget._status_label.grid(row=0, column=2, padx=4, pady=6, sticky="w")
        widget._status_label.bind("<Button-1>", widget._start_drag)
        widget._status_label.bind("<B1-Motion>", widget._do_drag)

        # Speed badge
        widget._speed_label = ctk.CTkLabel(
            compact, text=f"{widget._config.speed_rate:.1f}x",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=ACCENT, width=32,
        )
        widget._speed_label.grid(row=0, column=3, padx=2, pady=6)

        # Window buttons
        btn_cfg = dict(width=26, height=26, fg_color="transparent", corner_radius=4)

        widget._expand_btn = ctk.CTkButton(
            compact, text="\u25bc",
            font=ctk.CTkFont(size=10), hover_color=BG_PANEL,
            text_color=TEXT_DIM, command=widget._toggle_expand, **btn_cfg,
        )
        widget._expand_btn.grid(row=0, column=4, padx=1, pady=6)

        widget._minimize_btn = ctk.CTkButton(
            compact, text="\u2500",
            font=ctk.CTkFont(size=12, weight="bold"), hover_color=BG_PANEL,
            text_color=TEXT_DIM, command=widget.hide, **btn_cfg,
        )
        widget._minimize_btn.grid(row=0, column=5, padx=1, pady=6)

        widget._close_btn = ctk.CTkButton(
            compact, text="\u2715",
            font=ctk.CTkFont(size=10), hover_color=DANGER,
            text_color=TEXT_DIM, command=widget._on_close, **btn_cfg,
        )
        widget._close_btn.grid(row=0, column=6, padx=(1, 8), pady=6)

    # ------------------------------------------------------------------
    # Expanded panel
    # ------------------------------------------------------------------

    @staticmethod
    def build_expanded_panel(widget: WidgetService) -> None:
        root = widget._root
        config = widget._config

        # Scrollable container for all expanded content
        expanded = ctk.CTkScrollableFrame(
            root, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER_SUBTLE,
            scrollbar_button_hover_color=TEXT_MUTED,
        )
        expanded.grid(row=1, column=0, sticky="nsew")
        root.grid_rowconfigure(1, weight=1)
        widget._expanded_frame = expanded

        # ==============================================================
        # Single control row — Play | Save | History | Debug | ⋮ | Time
        # ==============================================================
        controls = ctk.CTkFrame(expanded, fg_color=BG_PANEL, corner_radius=8, height=40)
        controls.pack(fill="x", padx=6, pady=(4, 2))

        # Play/Pause button
        widget._btn_toggle = ctk.CTkButton(
            controls, text="\u25b6  Play", width=80, height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY, corner_radius=15,
            command=widget._on_toggle_play,
        )
        widget._btn_toggle.pack(side="left", padx=(8, 2), pady=5)

        # Separator
        ctk.CTkFrame(controls, width=1, height=16, fg_color=BORDER_SUBTLE).pack(
            side="left", padx=4, pady=8
        )

        # Small utility buttons
        sm_btn = dict(
            height=26, font=ctk.CTkFont(size=10),
            fg_color="transparent", hover_color=BG_INPUT,
            text_color=TEXT_DIM, corner_radius=4,
        )

        widget._save_btn = ctk.CTkButton(
            controls, text="Save", width=42,
            command=widget._on_save_audio, **sm_btn,
        )
        widget._save_btn.pack(side="left", padx=2, pady=5)

        widget._history_btn = ctk.CTkButton(
            controls, text="History", width=50,
            command=widget._toggle_history, **sm_btn,
        )
        widget._history_btn.pack(side="left", padx=2, pady=5)

        widget._debug_btn = ctk.CTkButton(
            controls, text="Debug", width=46,
            command=widget._toggle_debug, **sm_btn,
        )
        widget._debug_btn.pack(side="left", padx=2, pady=5)

        # Kebab menu (⋮) — voice & speed settings
        widget._kebab_btn = ctk.CTkButton(
            controls, text="\u22ee", width=26, height=26,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="transparent", hover_color=BG_INPUT,
            text_color=TEXT_DIM, corner_radius=4,
            command=widget._show_settings_menu,
        )
        widget._kebab_btn.pack(side="left", padx=2, pady=5)

        # Time indicator — right-aligned
        widget._time_label = ctk.CTkLabel(
            controls, text="00:00 / 00:00",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=ACCENT_LIGHT,
        )
        widget._time_label.pack(side="right", padx=(0, 10), pady=5)

        widget._controls_frame = controls

        # Store voice/speed vars for kebab menu
        current_voice = "Ardi" if config.voice_gender == VoiceGender.MALE else "Gadis"
        widget._voice_var = ctk.StringVar(value=current_voice)
        widget._speed_var = ctk.StringVar(value=f"{config.speed_rate:.1f}x")

        # ==============================================================
        # Chunk progress
        # ==============================================================
        from .components.chunk_progress import ChunkProgressMap
        widget._chunk_progress = ChunkProgressMap(expanded)
        widget._chunk_progress.pack(fill="x", padx=10, pady=(2, 2))

        # ==============================================================
        # Extra panels (debug / history) — hidden by default
        # ==============================================================
        widget._extra_panel_frame = ctk.CTkFrame(expanded, fg_color="transparent")

        from .components.debug_panel import DebugPanel
        widget._debug_panel = DebugPanel(widget._extra_panel_frame)
        widget._debug_panel.pack(fill="both", expand=True)

        # ==============================================================
        # Spectrum analyzer
        # ==============================================================
        widget._spectrum_frame = ctk.CTkFrame(
            expanded, fg_color=BG_PANEL, corner_radius=8,
        )
        widget._spectrum_frame.pack(fill="x", padx=6, pady=2)

        widget._large_spectrum = ctk.CTkCanvas(
            widget._spectrum_frame, width=WIDGET_WIDTH - 28, height=50,
            bg=BG_PANEL, highlightthickness=0,
        )
        widget._large_spectrum.pack(padx=4, pady=4)

        # ==============================================================
        # Status
        # ==============================================================
        widget._progress_label = ctk.CTkLabel(
            expanded, text="Ready",
            font=ctk.CTkFont(size=10), text_color=TEXT_MUTED, anchor="w",
        )
        widget._progress_label.pack(fill="x", padx=12, pady=(2, 0))

        # ==============================================================
        # Transcript
        # ==============================================================
        widget._transcript_header = ctk.CTkFrame(expanded, fg_color="transparent")
        widget._transcript_header.pack(fill="x", padx=6, pady=(2, 0))

        ctk.CTkLabel(
            widget._transcript_header, text="Transcript",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM,
        ).pack(side="left", padx=4)

        widget._copy_btn = ctk.CTkButton(
            widget._transcript_header, text="Copy", width=50, height=20,
            font=ctk.CTkFont(size=9), fg_color=BG_INPUT,
            hover_color=ACCENT, text_color=TEXT_DIM, corner_radius=4,
            command=widget._on_copy_transcript,
        )
        widget._copy_btn.pack(side="right", padx=4)

        widget._transcript_box = ctk.CTkTextbox(
            expanded,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=BG_PANEL, text_color=TEXT_DIM,
            corner_radius=8, height=200, wrap="word",
        )
        widget._transcript_box.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        widget._refresh_content_visibility()
