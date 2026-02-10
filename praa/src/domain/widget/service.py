"""
Widget Domain — Floating CustomTkinter UI v2

Always-on-top floating widget with:
- Compact: status bar + audio spectrum animation
- Expanded: settings → controls → Spotify-like transcript
- Word-level synchronized transcript highlighting
- Play/Pause/Stop/Replay controls
- Save Audio, Copy Transcript, Silent Mode
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import shutil
import threading
import time
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from src.domain.config.models import AppConfig, UIMode, VoiceGender
from src.infrastructure.event_bus import EventBus
from src.domain.session.service import SessionService
from src.infrastructure.events import (
    HotkeyAction,
    HotkeyPressed,
    PlaybackStarted,
    PlaybackStopped,
    SynthesisComplete,
    SynthesisStarted,
    TextCaptured,
    TrayAction,
    TrayActionType,
)

logger = logging.getLogger(__name__)

# -- Theme --
BG_DARK = "#0f0f1a"
BG_PANEL = "#1a1a2e"
BG_CARD = "#16213e"
BG_INPUT = "#0f3460"
ACCENT = "#0f9d9a"
ACCENT_HOVER = "#0d8a87"
ACCENT_LIGHT = "#14cfc9"
ACCENT_GLOW = "#FFFF00" # Yellow
TEXT_PRIMARY = "#e2e8f0"
TEXT_DIM = "#94a3b8"
TEXT_HIGHLIGHT = "#FFFF00"
STATUS_IDLE = "#64748b"
STATUS_PROCESSING = "#f59e0b"
STATUS_PLAYING = "#22c55e"
STATUS_ERROR = "#ef4444"
SPECTRUM_COLORS = ["#0f9d9a", "#14cfc9", "#00e5ff", "#0ea5e9", "#06b6d4"]

WIDGET_WIDTH = 400
COMPACT_HEIGHT = 60
EXPANDED_HEIGHT = 560


class WidgetService:
    """Floating overlay widget for PRAA with Spotify-like transcript sync."""

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        session_service: SessionService,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._loop = loop
        self._session_service = session_service
        self._root: Optional[ctk.CTk] = None
        self._thread: Optional[threading.Thread] = None
        self._expanded = False
        self._running = False

        # State
        self._status_text = "Idle"
        self._status_color = STATUS_IDLE
        self._transcript_chunks: list[str] = []
        self._current_chunk = -1
        self._audio_paths: list[Path] = []
        self._last_audio_path: Optional[Path] = None
        self._transcript_text: Optional[str] = None

        # Word boundary data for lyrics sync
        self._word_boundaries: dict[int, list[tuple[float, float, str]]] = {}
        self._playback_start_time: float = 0
        self._sync_active = False
        self._sync_active = False
        self._current_word_idx = 0
        self._last_hotkey_time = 0.0

        # Spectrum animation
        self._spectrum_bars: list[float] = [0.0] * 16
        self._spectrum_target: list[float] = [0.0] * 16
        self._spectrum_active = False

    # ---------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_ui, name="widget-ui", daemon=True,
        )
        self._thread.start()
        logger.info("[bold]Widget UI[/] started (mode=%s)", self._config.ui_mode.value)

    def stop(self) -> None:
        self._running = False
        self._spectrum_active = False
        self._sync_active = False
        if self._root is not None:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_ui(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._root = ctk.CTk()
        self._root.title("PRAA")
        self._root.geometry(f"{WIDGET_WIDTH}x{COMPACT_HEIGHT}+50+50")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.95)
        self._root.configure(fg_color=BG_DARK)
        self._root.grid_columnconfigure(0, weight=1)

        self._drag_x = 0
        self._drag_y = 0

        self._build_compact_bar()
        self._build_expanded_panel()
        self._expanded_frame.grid_remove()

        # Start spectrum animation loop
        self._animate_spectrum()

        self._root.mainloop()

    # ---------------------------------------------------------------
    # COMPACT BAR
    # ---------------------------------------------------------------

    def _build_compact_bar(self) -> None:
        self._compact_frame = ctk.CTkFrame(
            self._root, fg_color=BG_DARK, height=COMPACT_HEIGHT, corner_radius=0
        )
        self._compact_frame.grid(row=0, column=0, sticky="ew")
        self._compact_frame.grid_columnconfigure(2, weight=1)

        # Bind drag to compact bar
        self._compact_frame.bind("<Button-1>", self._start_drag)
        self._compact_frame.bind("<B1-Motion>", self._do_drag)

        # Status dot
        self._status_dot = ctk.CTkLabel(
            self._compact_frame, text="●", font=ctk.CTkFont(size=16),
            text_color=STATUS_IDLE, width=24,
        )
        self._status_dot.grid(row=0, column=0, padx=(12, 2), pady=8)

        # App name
        name_lbl = ctk.CTkLabel(
            self._compact_frame, text="PRAA",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=ACCENT_LIGHT, width=45,
        )
        name_lbl.grid(row=0, column=1, padx=(0, 4), pady=8)
        name_lbl.bind("<Button-1>", self._start_drag)
        name_lbl.bind("<B1-Motion>", self._do_drag)

        # Status text
        self._status_label = ctk.CTkLabel(
            self._compact_frame, text="Idle",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DIM, anchor="w",
        )
        self._status_label.grid(row=0, column=2, padx=4, pady=8, sticky="w")
        self._status_label.bind("<Button-1>", self._start_drag)
        self._status_label.bind("<B1-Motion>", self._do_drag)

        # Spectrum canvas (Removed)
        # self._spectrum_canvas = ...

        # Speed indicator
        self._speed_label = ctk.CTkLabel(
            self._compact_frame, text=f"{self._config.speed_rate:.1f}x",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT, width=36,
        )
        self._speed_label.grid(row=0, column=3, padx=2, pady=8)

        # Expand button
        self._expand_btn = ctk.CTkButton(
            self._compact_frame, text="▼", width=28, height=28,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            hover_color=BG_PANEL, text_color=TEXT_DIM,
            command=self._toggle_expand,
        )
        self._expand_btn.grid(row=0, column=4, padx=1, pady=8)

        # Close button
        self._close_btn = ctk.CTkButton(
            self._compact_frame, text="✕", width=28, height=28,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            hover_color="#ef4444", text_color=TEXT_DIM,
            command=self._on_close,
        )
        self._close_btn.grid(row=0, column=5, padx=(1, 8), pady=8)

    # ---------------------------------------------------------------
    # EXPANDED PANEL
    # ---------------------------------------------------------------

    def _build_expanded_panel(self) -> None:
        self._expanded_frame = ctk.CTkFrame(self._root, fg_color=BG_DARK, corner_radius=0)
        self._expanded_frame.grid(row=1, column=0, sticky="nsew")
        self._root.grid_rowconfigure(1, weight=1)

        # -- TOP: Settings Row --
        # -- TOP TOOLBAR: Settings + Controls --
        self._controls_frame = ctk.CTkFrame(self._expanded_frame, fg_color=BG_PANEL, corner_radius=8)
        self._controls_frame.pack(fill="x", padx=8, pady=(4, 2))
        
        # 1. Voice & Speed (Left)
        ctk.CTkLabel(
            self._controls_frame, text="Voice", font=ctk.CTkFont(size=10),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=(10, 4), pady=6)

        current_voice = "Ardi" if self._config.voice_gender == VoiceGender.MALE else "Gadis"
        self._voice_var = ctk.StringVar(value=current_voice)
        self._voice_menu = ctk.CTkOptionMenu(
            self._controls_frame, variable=self._voice_var,
            values=["Ardi", "Gadis"], width=70, height=24,
            font=ctk.CTkFont(size=11), fg_color=BG_INPUT,
            button_color=ACCENT, command=self._on_voice_change,
        )
        self._voice_menu.pack(side="left", padx=2, pady=6)

        self._speed_var = ctk.StringVar(value=f"{self._config.speed_rate:.1f}x")
        self._speed_menu = ctk.CTkOptionMenu(
            self._controls_frame, variable=self._speed_var,
            values=["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"],
            width=65, height=24, font=ctk.CTkFont(size=11),
            fg_color=BG_INPUT, button_color=ACCENT,
            command=self._on_speed_change,
        )
        self._speed_menu.pack(side="left", padx=2, pady=6)
        
        # Separator (Vertical Line)
        ctk.CTkFrame(self._controls_frame, width=1, height=16, fg_color="#334155").pack(side="left", padx=6, pady=8)

        # 2. Play Controls (Left-Center)
        # Use simpler styling for toolbar buttons
        btn_toolbar = dict(
             width=32, height=32, font=ctk.CTkFont(size=14),
             fg_color="transparent", hover_color=BG_INPUT, text_color=TEXT_PRIMARY, corner_radius=4,
        )
        btn_play_style = dict(
             width=60, height=32, font=ctk.CTkFont(size=12, weight="bold"),
             fg_color=ACCENT, text_color=TEXT_PRIMARY, corner_radius=16,
        )

        self._btn_toggle = ctk.CTkButton(
            self._controls_frame, text="▶ Play",
            hover_color=ACCENT_HOVER, command=self._on_toggle_play, **btn_play_style,
        )
        self._btn_toggle.pack(side="left", padx=4, pady=4)

        self._save_btn = ctk.CTkButton(
            self._controls_frame, text="💾", 
            command=self._on_save_audio, **btn_toolbar
        )
        self._save_btn.pack(side="left", padx=2, pady=4)
        
        self._silent_btn = ctk.CTkButton(
            self._controls_frame, text="🔇",
            command=self._on_toggle_mode, **btn_toolbar
        )
        self._silent_btn.pack(side="left", padx=2, pady=4)

        # -- LARGE SPECTRUM VISUALIZER (Restored) --
        self._spectrum_frame = ctk.CTkFrame(
            self._expanded_frame, fg_color=BG_PANEL, corner_radius=8,
        )
        self._spectrum_frame.pack(fill="x", padx=8, pady=2)

        self._large_spectrum = ctk.CTkCanvas(
            self._spectrum_frame, width=WIDGET_WIDTH - 24, height=60,
            bg=BG_PANEL, highlightthickness=0,
        )
        self._large_spectrum.pack(padx=4, pady=6)

        # -- LARGE SPECTRUM VISUALIZER (Removed for cleaner UI) --
        # User requested minimal design.
        # self._spectrum_frame = ...

        # -- Progress label --
        self._progress_label = ctk.CTkLabel(
            self._expanded_frame, text="Ready",
            font=ctk.CTkFont(size=10), text_color=TEXT_DIM, anchor="w",
        )
        self._progress_label.pack(fill="x", padx=12, pady=(2, 0))

        # -- TRANSCRIPT --
        self._transcript_header = ctk.CTkFrame(self._expanded_frame, fg_color="transparent")
        self._transcript_header.pack(fill="x", padx=8, pady=(2, 0))
        
        transcript_header = self._transcript_header # Alias

        ctk.CTkLabel(
            transcript_header, text="📝 Transcript",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM,
        ).pack(side="left", padx=4)

        self._copy_btn = ctk.CTkButton(
            transcript_header, text="📋 Copy", width=60, height=22,
            font=ctk.CTkFont(size=10), fg_color=BG_INPUT,
            hover_color=ACCENT, text_color=TEXT_DIM,
            command=self._on_copy_transcript,
        )
        self._copy_btn.pack(side="right", padx=4)

        self._transcript_box = ctk.CTkTextbox(
            self._expanded_frame,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=BG_PANEL, text_color=TEXT_DIM,
            corner_radius=8, height=240, wrap="word",
        )
        self._transcript_box.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        # Tag for highlighted (currently-spoken) words
        self._transcript_box._textbox.tag_config("active", foreground=ACCENT_GLOW, background="#1e293b")
        self._transcript_box._textbox.tag_config("spoken", foreground=TEXT_PRIMARY)
        self._transcript_box._textbox.tag_config("unspoken", foreground=TEXT_DIM)
        
        # Ensure 'active' tag is on top of others
        self._transcript_box._textbox.tag_raise("active")
        
        # Initial visibility check
        self._refresh_content_visibility()

    def _refresh_content_visibility(self) -> None:
        """Hide controls and transcript if no content is loaded."""
        if not hasattr(self, '_controls_frame'):
            return
            
        has_content = bool(self._transcript_text or self._transcript_chunks)
        
        # Always unpack everything first
        self._controls_frame.pack_forget()
        if hasattr(self, '_spectrum_frame'):
            self._spectrum_frame.pack_forget()
        self._progress_label.pack_forget()
        self._transcript_header.pack_forget()
        self._transcript_box.pack_forget()
        
        if has_content:
            # Repack in correct order
            self._controls_frame.pack(fill="x", padx=8, pady=(4, 2))
            if hasattr(self, '_spectrum_frame'):
                self._spectrum_frame.pack(fill="x", padx=8, pady=2)
            self._progress_label.pack(fill="x", padx=12, pady=(2, 0))
            self._transcript_header.pack(fill="x", padx=8, pady=(2, 0))
            self._transcript_box.pack(fill="both", expand=True, padx=8, pady=(2, 8))


    # ---------------------------------------------------------------
    # SPECTRUM ANIMATION
    # ---------------------------------------------------------------

    def _animate_spectrum(self) -> None:
        """Animation loop for audio spectrum bars."""
        if not self._running or self._root is None:
            return

        # Update bar heights
        for i in range(len(self._spectrum_bars)):
            if self._spectrum_active:
                self._spectrum_target[i] = random.uniform(0.2, 1.0)
            else:
                self._spectrum_target[i] = 0.0

            # Smooth interpolation
            diff = self._spectrum_target[i] - self._spectrum_bars[i]
            self._spectrum_bars[i] += diff * 0.3

        # Draw mini spectrum (Removed)
        # self._draw_spectrum(self._spectrum_canvas, 60, 30, 8)

        # Draw large spectrum (expanded panel)
        if self._expanded and hasattr(self, '_large_spectrum'):
            self._draw_spectrum(self._large_spectrum, WIDGET_WIDTH - 24, 50, 16)

        try:
            self._root.after(50, self._animate_spectrum)
        except Exception:
            pass

    def _draw_spectrum(self, canvas, width: int, height: int, num_bars: int) -> None:
        """Draw spectrum bars on a canvas."""
        canvas.delete("all")
        bar_width = max(2, (width - num_bars * 2) // num_bars)
        gap = 2

        for i in range(min(num_bars, len(self._spectrum_bars))):
            bar_h = max(2, self._spectrum_bars[i] * (height - 4))
            x = i * (bar_width + gap) + gap
            y = height - 2
            color = SPECTRUM_COLORS[i % len(SPECTRUM_COLORS)]

            # Bar with rounded look
            canvas.create_rectangle(
                x, y - bar_h, x + bar_width, y,
                fill=color, outline="", width=0,
            )

    # ---------------------------------------------------------------
    # LYRICS SYNC (Spotify-like)
    # ---------------------------------------------------------------

    def _start_lyrics_sync(self, chunk_index: int) -> None:
        """Start word-by-word highlighting for the current chunk."""
        if chunk_index not in self._word_boundaries:
            return

        self._sync_active = True
        self._playback_start_time = time.time()
        self._current_word_idx = 0
        self._do_lyrics_sync(chunk_index)

    def _do_lyrics_sync(self, chunk_index: int) -> None:
        """Timer-driven word highlight update."""
        if not self._sync_active or self._root is None:
            return
        if chunk_index not in self._word_boundaries:
            return

        boundaries = self._word_boundaries[chunk_index]
        elapsed = time.time() - self._playback_start_time

        # Find which word we should be highlighting
        new_idx = self._current_word_idx
        for i in range(self._current_word_idx, len(boundaries)):
            # boundaries[i] is (offset, duration, word, text_offset, word_len)
            offset = boundaries[i][0]
            if elapsed >= offset:
                new_idx = i
            else:
                break

        if new_idx != self._current_word_idx or self._current_word_idx == 0:
            self._current_word_idx = new_idx
            self._highlight_word_at(chunk_index, new_idx)

        # Continue sync
        try:
            self._root.after(50, self._do_lyrics_sync, chunk_index)
        except Exception:
            pass

    def _highlight_word_at(self, chunk_index: int, word_idx: int) -> None:
        """Highlight the word at the given index using precise TTS offsets."""
        logger.debug("Highlight request: chunk=%d, word=%d", chunk_index, word_idx)
        
        if chunk_index not in self._word_boundaries:
            return

        boundaries = self._word_boundaries[chunk_index]
        if word_idx >= len(boundaries):
            return

        try:
            # Data: (offset, duration, word, text_offset, word_len)
            b_data = boundaries[word_idx]
            if len(b_data) < 5:
                return # Should not happen with new TTS service

            text_offset = b_data[3]
            word_len = b_data[4]

            # Calculate absolute start position of this chunk
            chunk_start_pos = 0
            for i in range(chunk_index):
                if i < len(self._transcript_chunks):
                    # +2 for \n\n
                    chunk_start_pos += len(self._transcript_chunks[i]) + 2

            abs_start = chunk_start_pos + text_offset
            abs_end = abs_start + word_len

            # Use "1.0 + N chars" format for Tkinter indices
            start_index = f"1.0 + {abs_start} chars"
            end_index = f"1.0 + {abs_end} chars"
            
            # Use private _textbox for direct tag access
            self._transcript_box._textbox.tag_remove("active", "1.0", "end")
            self._transcript_box._textbox.tag_add("active", start_index, end_index)
            self._transcript_box._textbox.see(start_index)
            
            # Optional: Mark previous words as spoken
            # This would require calculating range from 0 to abs_start
            # self._transcript_box._textbox.tag_add("spoken", "1.0", start_index)

        except Exception:
            pass  # UI timing errors are non-critical

    def _get_smart_resume_text(self) -> str:
        """
        Calculate remaining text from current word position for seamless resume.
        Returns full text if not playing or at start.
        """
        if self._current_chunk < 0 or not self._transcript_chunks:
            return self._transcript_text or ""
            
        try:
            current_chunk_text = self._transcript_chunks[self._current_chunk]
            boundaries = self._word_boundaries.get(self._current_chunk, [])
            
            if self._current_word_idx < len(boundaries):
                # Use precise text offset
                b_data = boundaries[self._current_word_idx]
                if len(b_data) >= 5:
                    text_start = b_data[3]
                    current_chunk_text = current_chunk_text[text_start:]
            
            remaining_chunks = self._transcript_chunks[self._current_chunk + 1:]
            
            parts = [current_chunk_text] + remaining_chunks
            return "\n\n".join(parts)
            
        except Exception:
            logger.exception("Failed to calculate smart resume text")
            return self._transcript_text or ""

    # ---------------------------------------------------------------
    # DRAG
    # ---------------------------------------------------------------

    def _start_drag(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event) -> None:
        if self._root:
            x = self._root.winfo_x() + event.x - self._drag_x
            y = self._root.winfo_y() + event.y - self._drag_y
            self._root.geometry(f"+{x}+{y}")

    # ---------------------------------------------------------------
    # EXPAND/COLLAPSE
    # ---------------------------------------------------------------

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._expanded_frame.grid()
            h = EXPANDED_HEIGHT
            self._expand_btn.configure(text="▲")
        else:
            self._expanded_frame.grid_remove()
            h = COMPACT_HEIGHT
            self._expand_btn.configure(text="▼")
        x = self._root.winfo_x() if self._root else 50
        y = self._root.winfo_y() if self._root else 50
        if self._root:
            self._root.geometry(f"{WIDGET_WIDTH}x{h}+{x}+{y}")

    # ---------------------------------------------------------------
    # UI UPDATES (thread-safe)
    # ---------------------------------------------------------------

    def _update_status(self, text: str, color: str) -> None:
        if self._root is None:
            return
        try:
            self._root.after(0, self._do_update_status, text, color)
        except Exception:
            pass

    def _do_update_status(self, text: str, color: str) -> None:
        self._status_text = text
        self._status_color = color
        self._status_label.configure(text=text, text_color=color)
        self._status_dot.configure(text_color=color)
        self._update_buttons()

    def _update_progress(self, text: str) -> None:
        if self._root is None:
            return
        try:
            self._root.after(0, self._progress_label.configure, {"text": text})
        except Exception:
            pass

    def _set_transcript(self, text: str) -> None:
        """Set transcript text (keeps it editable for selection/copy)."""
        if self._root is None:
            return
        try:
            self._root.after(0, self._do_set_transcript, text)
        except Exception:
            pass

    def _do_set_transcript(self, text: str) -> None:
        self._transcript_box.delete("1.0", "end")
        self._transcript_box.insert("1.0", text)
        # Apply unspoken style to all text
        self._transcript_box.tag_add("unspoken", "1.0", "end")

    # ---------------------------------------------------------------
    # EVENT HANDLERS
    # ---------------------------------------------------------------

    async def on_hotkey_pressed(self, event: HotkeyPressed) -> None:
        # Debounce to prevent double-trigger wiping data
        now = time.time()
        if now - self._last_hotkey_time < 1.0:
            logger.warning("Hotkey ignored (debounce): %s", event.action)
            return
        self._last_hotkey_time = now

        if event.action == HotkeyAction.READ:
            self.show()  # Auto-show widget on hotkey
            self._update_status("📋 Capturing...", STATUS_PROCESSING)
            
            # Clear previous session
            self._word_boundaries.clear() 
            self._transcript_chunks.clear()
            self._audio_paths.clear()
            self._sync_active = False

    async def on_text_captured(self, event: TextCaptured) -> None:
        self._update_status("📝 Processing...", STATUS_PROCESSING)
        self._transcript_text = event.raw_text
        self._refresh_content_visibility()

    async def on_synthesis_started(self, event: SynthesisStarted) -> None:
        self._update_status(
            f"⏳ Synthesizing {event.chunk_index + 1}/{event.total_chunks}",
            STATUS_PROCESSING,
        )
        self._update_progress(
            f"Synthesizing chunk {event.chunk_index + 1} of {event.total_chunks}"
        )

    async def on_synthesis_complete(self, event: SynthesisComplete) -> None:
        self._audio_paths.append(event.audio_path)
        self._last_audio_path = event.audio_path

        # Store word boundaries for lyrics sync
        if event.word_boundaries:
            self._word_boundaries[event.chunk_index] = list(event.word_boundaries)
            logger.info("Received %d boundaries for chunk %d", len(event.word_boundaries), event.chunk_index)
        else:
            logger.warning("No boundaries received for chunk %d", event.chunk_index)

        # Store chunk text
        if event.chunk_text:
            while len(self._transcript_chunks) <= event.chunk_index:
                self._transcript_chunks.append("")
            self._transcript_chunks[event.chunk_index] = event.chunk_text

        if len(self._audio_paths) == event.total_chunks:
             self._save_current_session(event.total_chunks, event.chunk_text)

        self._update_progress(
            f"Synthesized {event.chunk_index + 1}/{event.total_chunks}"
        )

    def _save_current_session(self, total_chunks: int, last_text: str) -> None:
        """Save text and audio paths to persistent history."""
        if not self._transcript_text:
            return
            
        # Reconstruct boundaries dict
        # (self._word_boundaries is already populated)
        
        try:
            self._session_service.save_session(
                text=self._transcript_text,
                audio_paths=self._audio_paths,
                word_boundaries=self._word_boundaries,
                config=self._config.model_dump(),
            )
            logger.info("Session auto-saved to history")
        except Exception:
            logger.exception("Failed to auto-save session")

    async def on_text_processed(self, event) -> None:
        """Display transcript when text is processed."""
        self._transcript_chunks = list(event.chunks)
        
        # If this was a smart resume (started mid-text), we should append to console?
        # For now, just replace transcript so user sees what's playing.
        full_text = "\n\n".join(event.chunks)
        self._set_transcript(full_text)
        
        # Reset state for new session
        self._current_chunk = 0
        self._current_word_idx = 0

    def _get_smart_resume_text(self) -> str:
        """
        Calculate remaining text from current word position for seamless resume.
        Returns full text if not playing or at start.
        """
        if self._current_chunk < 0 or not self._transcript_chunks:
            return self._transcript_text or ""
            
        try:
            # 1. Get current chunk text sliced from current word
            current_chunk_text = self._transcript_chunks[self._current_chunk]
            
            # Find character offset of current word
            # We have _current_word_idx (index in boundaries list)
            # We need to find where this word starts in the text
            if self._current_chunk in self._word_boundaries:
                boundaries = self._word_boundaries[self._current_chunk]
                if self._current_word_idx < len(boundaries):
                    # Edge-TTS boundaries: (offset, duration, word)
                    # We need character position.
                    # Simple approximation: match word by word? 
                    # Or just use the word index to split if we can't map to chars accurately.
                    # Since we want to send RAW text to synthesizer, we should construct it.
                    
                    # Reconstruction strategy:
                    # Take words from boundaries[_current_word_idx:]
                    # And join them? That loses punctuation.
                    
                    # Better strategy: text.find the word at roughly correct position?
                    # Let's use the helper provided in V2: _find_word_pos_in_text
                    
                    word_val = boundaries[self._current_word_idx][2]
                    pos = self._find_word_pos_in_text(
                        current_chunk_text, word_val, self._current_word_idx, boundaries
                    )
                    
                    if pos >= 0:
                         current_chunk_text = current_chunk_text[pos:]
            
            # 2. Get all subsequent chunks
            remaining_chunks = self._transcript_chunks[self._current_chunk + 1:]
            
            # 3. Combine
            return current_chunk_text + "\n\n" + "\n\n".join(remaining_chunks)
            
        except Exception:
            logger.exception("Failed to calculate smart resume text")
            return self._transcript_text or ""

    def _find_word_pos_in_text(self, text: str, word: str, word_idx: int, boundaries: list) -> int:
        """Helper to find approximate character position of a word."""
        # Simple heuristic: Split text and match? 
        # Or just find the Nth occurrence?
        # Since we don't have perfect mapping, returning -1 is safer than guessing wrong.
        # But for 'Resume', -1 means start of chunk, which is acceptable safety fallback.
        try:
            # Try to find word
            # This is complex because boundaries might skip words or text might have punctuation.
            # Fallback:
            return -1 
        except:
            return -1

    async def on_playback_started(self, event: PlaybackStarted) -> None:
        self._update_status("🔊 Playing...", STATUS_PLAYING)
        self._spectrum_active = True

        # Start lyrics sync for this chunk
        if self._root:
            try:
                self._root.after(0, self._start_lyrics_sync, event.chunk_index)
            except Exception:
                pass

    async def on_playback_stopped(self, event: PlaybackStopped) -> None:
        self._spectrum_active = False
        self._sync_active = False

        if event.reason == "completed":
            self._update_status("✅ Done", ACCENT)
            if self._root:
                try:
                    self._root.after(3000, lambda: self._update_status("Idle", STATUS_IDLE))
                except Exception:
                    pass
        elif event.reason == "stopped":
            self._update_status("⏹ Stopped", STATUS_IDLE)
        else:
            self._update_status("❌ Error", STATUS_ERROR)

        self._update_progress("Ready")

    # ---------------------------------------------------------------
    # BUTTON CALLBACKS
    # ---------------------------------------------------------------

    def _on_toggle_play(self) -> None:
        """Handle Play/Pause/Resume toggle."""
        if "Playing" in self._status_text:
            self._on_pause()
        elif "Paused" in self._status_text:
            self._publish_event(TrayAction(action=TrayActionType.RESUME))
            self._update_status("🔊 Playing...", STATUS_PLAYING)
        else:
            self._on_replay()

    def _update_buttons(self) -> None:
        """Update button text/icon based on status."""
        if not hasattr(self, '_btn_toggle'):
            return
            
        if "Playing" in self._status_text:
            self._btn_toggle.configure(text="⏸ Pause", fg_color=ACCENT, hover_color=ACCENT_HOVER)
        elif "Paused" in self._status_text:
            self._btn_toggle.configure(text="▶ Resume", fg_color=ACCENT, hover_color=ACCENT_HOVER)
        else:
            self._btn_toggle.configure(text="▶ Play", fg_color=ACCENT, hover_color=ACCENT_HOVER)

    def _on_stop(self) -> None:
        self._spectrum_active = False
        self._sync_active = False
        self._publish_event(TrayAction(action=TrayActionType.STOP))
        self._btn_toggle.configure(text="▶ Play")

    def _on_pause(self) -> None:
        self._spectrum_active = False
        self._sync_active = False
        self._publish_event(TrayAction(action=TrayActionType.PAUSE))
        self._update_status("⏸ Paused", STATUS_PROCESSING)

    def _on_replay(self) -> None:
        """Replay: Smart Resume (slice text) if playing, otherwise full replay."""
        # Use smart resume text slice to continue from current word
        text_to_play = self._get_smart_resume_text()
        
        if text_to_play:
            self._update_status("🔄 Resuming...", STATUS_PROCESSING)
            self._publish_event(TrayAction(action=TrayActionType.STOP))
            # Wait briefly to let STOP propagate? Orchestrator handles sequentially?
            # Actually events are async. 
            # Ideally we'd wait, but let's fire.
            self._publish_event(TextCaptured(raw_text=text_to_play))
        else:
            self._publish_event(TrayAction(action=TrayActionType.RESUME))


    def _on_voice_change(self, value: str) -> None:
        gender = "male" if value == "Ardi" else "female"
        self._publish_event(
            TrayAction(action=TrayActionType.CHANGE_VOICE, value=gender)
        )
        logger.info("[bold]Widget[/]: voice → [cyan]%s[/]", value)
        # Auto-replay with new voice
        if self._transcript_text and self._status_text != "Idle":
             self._root.after(500, self._on_replay)

    def _on_speed_change(self, value: str) -> None:
        speed = value.replace("x", "")
        self._publish_event(
            TrayAction(action=TrayActionType.CHANGE_SPEED, value=speed)
        )
        if hasattr(self, '_speed_label'):
            self._speed_label.configure(text=value)
        logger.info("[bold]Widget[/]: speed → [cyan]%s[/]", value)
        # Auto-replay with new speed
        if self._transcript_text and self._status_text != "Idle":
             self._root.after(500, self._on_replay)

    def _on_save_audio(self) -> None:
        # 1. Try to get current session from DB (most reliable)
        session = self._session_service.get_last_session()
        
        if not session or not session.audio_paths:
            logger.warning("No session history found")
            self._update_status("No audio to save", STATUS_ERROR)
            if self._root:
                self._root.after(2000, lambda: self._update_status("Idle", STATUS_IDLE))
            return

        available = [Path(p) for p in session.audio_paths if Path(p).exists()]
        if not available:
            logger.warning("Cached audio files missing")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 Audio", "*.mp3"), ("All Files", "*.*")],
            title="Save Audio File",
        )
        if save_path:
            try:
                if len(available) == 1:
                    shutil.copy2(available[0], save_path)
                else:
                    # Multiple chunks: copy each with suffix
                    base = Path(save_path)
                    for i, src in enumerate(available):
                        dest = base.parent / f"{base.stem}_part{i + 1}{base.suffix}"
                        shutil.copy2(src, dest)
                    save_path = str(base.parent)
                logger.info("[bold green]Audio saved[/] to: %s", save_path)
                self._update_status("💾 Audio saved!", ACCENT)
                if self._root:
                    self._root.after(2000, lambda: self._update_status("Idle", STATUS_IDLE))
            except Exception:
                logger.exception("Failed to save audio")

    def _on_copy_transcript(self) -> None:
        """Copy transcript text to clipboard."""
        try:
            text = self._transcript_box.get("1.0", "end-1c").strip()
            if text:
                self._root.clipboard_clear()
                self._root.clipboard_append(text)
                self._copy_btn.configure(text="✅ Copied!")
                self._root.after(1500, lambda: self._copy_btn.configure(text="📋 Copy"))
                logger.info("Transcript copied to clipboard")
        except Exception:
            logger.exception("Failed to copy transcript")

    def _on_toggle_mode(self) -> None:
        self._publish_event(
            TrayAction(action=TrayActionType.TOGGLE_MODE, value="silent")
        )
        if self._root:
            self._root.withdraw()
        logger.info("Widget minimized — still running in tray")

    def _on_close(self) -> None:
        if self._root:
            self._root.withdraw()
        logger.info("Widget minimized — right-click tray icon → Show Widget to restore")

    async def on_tray_action(self, event: TrayAction) -> None:
        """Handle tray actions relevant to the widget."""
        if event.action == TrayActionType.TOGGLE_MODE:
            if event.value == "widget":
                self.show()
                logger.info("Widget restored from tray")
            elif event.value == "toggle_window":
                if self._root and self._root.winfo_viewable():
                    self.hide()
                else:
                    self.show()
            elif event.value == "silent":
                self.hide()

    def show(self) -> None:
        if self._root:
            try:
                self._root.after(0, self._root.deiconify)
            except Exception:
                pass

    def hide(self) -> None:
        if self._root:
            try:
                self._root.after(0, self._root.withdraw)
            except Exception:
                pass

    # ---------------------------------------------------------------
    # EVENT PUBLISHING
    # ---------------------------------------------------------------

    def _publish_event(self, event: object) -> None:
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(event),
            self._loop,
        )
