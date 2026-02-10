"""
Widget Domain — Refactored with SOLID Principles

ARCHITECTURE IMPROVEMENTS:
✅ Single Responsibility: Each component has ONE job
✅ Dependency Injection: Clear component boundaries
✅ State Machine: Deterministic transitions
✅ Promise Resolution: No race conditions
✅ Thread Safety: Clear UI thread boundaries

COMPOSITION STRUCTURE:
  WidgetService (Facade/Coordinator)
      ├─ PlaybackStateManager (State transitions)
      ├─ SyncController (Word-level sync)
      ├─ TranscriptRenderer (UI rendering)
      └─ SpectrumAnimator (Visual feedback)
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import threading
import time
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from src.domain.config.models import AppConfig, VoiceGender
from src.infrastructure.event_bus import EventBus
from src.domain.session.service import SessionService
from src.infrastructure.events import (
    HotkeyAction,
    HotkeyPressed,
    PlaybackStarted,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStopped,
    SynthesisComplete,
    SynthesisStarted,
    TextCaptured,
    TrayAction,
    TrayActionType,
)

# Import our new responsible objects
from .sync_controller import SyncController, SyncState
from .transcript_renderer import TranscriptRenderer
from .playback_state_manager import PlaybackStateManager, PlaybackState

logger = logging.getLogger(__name__)

# -- Theme --
BG_DARK = "#0f0f1a"
BG_PANEL = "#1a1a2e"
BG_INPUT = "#0f3460"
ACCENT = "#0f9d9a"
ACCENT_HOVER = "#0d8a87"
ACCENT_LIGHT = "#14cfc9"
TEXT_PRIMARY = "#e2e8f0"
TEXT_DIM = "#94a3b8"
SPECTRUM_COLORS = ["#0f9d9a", "#14cfc9", "#00e5ff", "#0ea5e9", "#06b6d4"]

WIDGET_WIDTH = 400
COMPACT_HEIGHT = 60
EXPANDED_HEIGHT = 560


class SpectrumAnimator:
    """
    SINGLE RESPONSIBILITY: Visual audio spectrum animation.
    
    Encapsulates all spectrum bar logic.
    """
    
    def __init__(self, num_bars: int = 16) -> None:
        self._num_bars = num_bars
        self._bars = [0.0] * num_bars
        self._targets = [0.0] * num_bars
        self._active = False
        
    def set_active(self, active: bool) -> None:
        """Enable/disable spectrum animation."""
        self._active = active
        
    def update(self) -> None:
        """Update bar heights (call every ~50ms)."""
        import random
        
        for i in range(self._num_bars):
            if self._active:
                self._targets[i] = random.uniform(0.2, 1.0)
            else:
                self._targets[i] = 0.0
            
            # Smooth interpolation
            diff = self._targets[i] - self._bars[i]
            self._bars[i] += diff * 0.3
    
    def draw(self, canvas, width: int, height: int) -> None:
        """Draw spectrum on canvas."""
        canvas.delete("all")
        
        bar_width = max(2, (width - self._num_bars * 2) // self._num_bars)
        gap = 2
        
        for i in range(min(self._num_bars, len(self._bars))):
            bar_h = max(2, self._bars[i] * (height - 4))
            x = i * (bar_width + gap) + gap
            y = height - 2
            color = SPECTRUM_COLORS[i % len(SPECTRUM_COLORS)]
            
            canvas.create_rectangle(
                x, y - bar_h, x + bar_width, y,
                fill=color, outline="", width=0,
            )


class WidgetService:
    """
    Floating overlay widget — Refactored with SOLID principles.
    
    ARCHITECTURE:
    - Facade pattern: Coordinates 4 responsible objects
    - Event-driven: Reacts to domain events
    - Thread-safe: UI updates via tk.after()
    - Deterministic: State machine prevents race conditions
    """

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
        
        # UI state
        self._root: Optional[ctk.CTk] = None
        self._thread: Optional[threading.Thread] = None
        self._expanded = False
        self._running = False
        
        # COMPOSITION: Inject responsible objects later (after UI init)
        self._state_manager: Optional[PlaybackStateManager] = None
        self._sync_controller: Optional[SyncController] = None
        self._transcript_renderer: Optional[TranscriptRenderer] = None
        self._spectrum: Optional[SpectrumAnimator] = None
        
        # Session data
        self._transcript_text: Optional[str] = None
        self._audio_paths: list[Path] = []
        self._total_chunks = 0
        
        # Drag state
        self._drag_x = 0
        self._drag_y = 0

    # ---------------------------------------------------------------
    # LIFECYCLE
    # ---------------------------------------------------------------

    def start(self) -> None:
        """Start UI thread."""
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_ui, name="widget-ui", daemon=True,
        )
        self._thread.start()
        logger.info("Widget UI started (mode=%s)", self._config.ui_mode.value)

    def stop(self) -> None:
        """Stop UI thread."""
        self._running = False
        
        if self._sync_controller:
            self._sync_controller.stop_sync()
        if self._spectrum:
            self._spectrum.set_active(False)
            
        if self._root is not None:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_ui(self) -> None:
        """UI thread entry point."""
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

        # Build UI
        self._build_compact_bar()
        self._build_expanded_panel()
        self._expanded_frame.grid_remove()
        
        # INITIALIZE RESPONSIBLE OBJECTS (after UI exists)
        self._state_manager = PlaybackStateManager()
        self._sync_controller = SyncController(
            highlight_callback=self._on_highlight_word,
        )
        self._sync_controller.set_latency(self._config.playback_latency_ms)
        self._transcript_renderer = TranscriptRenderer(self._transcript_box)
        self._spectrum = SpectrumAnimator(num_bars=16)
        
        # Start animation loops
        self._animate_spectrum()
        self._update_sync()
        
        self._root.mainloop()

    # ---------------------------------------------------------------
    # UI CONSTRUCTION
    # ---------------------------------------------------------------

    def _build_compact_bar(self) -> None:
        """Build compact status bar."""
        self._compact_frame = ctk.CTkFrame(
            self._root, fg_color=BG_DARK, height=COMPACT_HEIGHT, corner_radius=0
        )
        self._compact_frame.grid(row=0, column=0, sticky="ew")
        self._compact_frame.grid_columnconfigure(2, weight=1)

        # Bind drag
        self._compact_frame.bind("<Button-1>", self._start_drag)
        self._compact_frame.bind("<B1-Motion>", self._do_drag)

        # Status dot
        self._status_dot = ctk.CTkLabel(
            self._compact_frame, text="●", font=ctk.CTkFont(size=16),
            text_color="#64748b", width=24,
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

    def _build_expanded_panel(self) -> None:
        """Build expanded control panel."""
        self._expanded_frame = ctk.CTkFrame(self._root, fg_color=BG_DARK, corner_radius=0)
        self._expanded_frame.grid(row=1, column=0, sticky="nsew")
        self._root.grid_rowconfigure(1, weight=1)

        # Controls toolbar
        self._controls_frame = ctk.CTkFrame(self._expanded_frame, fg_color=BG_PANEL, corner_radius=8)
        self._controls_frame.pack(fill="x", padx=8, pady=(4, 2))
        
        # Voice selector
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

        # Speed selector
        self._speed_var = ctk.StringVar(value=f"{self._config.speed_rate:.1f}x")
        self._speed_menu = ctk.CTkOptionMenu(
            self._controls_frame, variable=self._speed_var,
            values=["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"],
            width=65, height=24, font=ctk.CTkFont(size=11),
            fg_color=BG_INPUT, button_color=ACCENT,
            command=self._on_speed_change,
        )
        self._speed_menu.pack(side="left", padx=2, pady=6)
        
        # Separator
        ctk.CTkFrame(self._controls_frame, width=1, height=16, fg_color="#334155").pack(side="left", padx=6, pady=8)

        # Play controls
        btn_style = dict(
            width=32, height=32, font=ctk.CTkFont(size=14),
            fg_color="transparent", hover_color=BG_INPUT, 
            text_color=TEXT_PRIMARY, corner_radius=4,
        )
        
        self._btn_toggle = ctk.CTkButton(
            self._controls_frame, text="▶ Play", width=60, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY, corner_radius=16,
            command=self._on_toggle_play,
        )
        self._btn_toggle.pack(side="left", padx=4, pady=4)

        self._save_btn = ctk.CTkButton(
            self._controls_frame, text="💾", 
            command=self._on_save_audio, **btn_style
        )
        self._save_btn.pack(side="left", padx=2, pady=4)
        
        self._silent_btn = ctk.CTkButton(
            self._controls_frame, text="🔇",
            command=self._on_toggle_mode, **btn_style
        )
        self._silent_btn.pack(side="left", padx=2, pady=4)

        # Spectrum visualizer
        self._spectrum_frame = ctk.CTkFrame(
            self._expanded_frame, fg_color=BG_PANEL, corner_radius=8,
        )
        self._spectrum_frame.pack(fill="x", padx=8, pady=2)

        self._large_spectrum = ctk.CTkCanvas(
            self._spectrum_frame, width=WIDGET_WIDTH - 24, height=60,
            bg=BG_PANEL, highlightthickness=0,
        )
        self._large_spectrum.pack(padx=4, pady=6)

        # Progress label
        self._progress_label = ctk.CTkLabel(
            self._expanded_frame, text="Ready",
            font=ctk.CTkFont(size=10), text_color=TEXT_DIM, anchor="w",
        )
        self._progress_label.pack(fill="x", padx=12, pady=(2, 0))

        # Transcript header
        self._transcript_header = ctk.CTkFrame(self._expanded_frame, fg_color="transparent")
        self._transcript_header.pack(fill="x", padx=8, pady=(2, 0))
        
        ctk.CTkLabel(
            self._transcript_header, text="📝 Transcript",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM,
        ).pack(side="left", padx=4)

        self._copy_btn = ctk.CTkButton(
            self._transcript_header, text="📋 Copy", width=60, height=22,
            font=ctk.CTkFont(size=10), fg_color=BG_INPUT,
            hover_color=ACCENT, text_color=TEXT_DIM,
            command=self._on_copy_transcript,
        )
        self._copy_btn.pack(side="right", padx=4)

        # Transcript textbox (managed by TranscriptRenderer)
        self._transcript_box = ctk.CTkTextbox(
            self._expanded_frame,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=BG_PANEL, text_color=TEXT_DIM,
            corner_radius=8, height=240, wrap="word",
        )
        self._transcript_box.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        
        # Initial visibility
        self._refresh_content_visibility()

    # ---------------------------------------------------------------
    # ANIMATION LOOPS
    # ---------------------------------------------------------------

    def _animate_spectrum(self) -> None:
        """Spectrum animation loop (50ms intervals)."""
        if not self._running or self._root is None:
            return

        if self._spectrum:
            self._spectrum.update()
            
            if self._expanded and hasattr(self, '_large_spectrum'):
                self._spectrum.draw(self._large_spectrum, WIDGET_WIDTH - 24, 50)

        try:
            self._root.after(50, self._animate_spectrum)
        except Exception:
            pass

    def _update_sync(self) -> None:
        """Sync update loop (50ms intervals)."""
        if not self._running or self._root is None:
            return

        if self._sync_controller and self._sync_controller.is_active:
            should_continue = self._sync_controller.update_sync()
            
            if not should_continue:
                # Chunk completed
                logger.debug("Sync completed for current chunk")

        try:
            self._root.after(50, self._update_sync)
        except Exception:
            pass

    # ---------------------------------------------------------------
    # THREAD-SAFE UI UPDATES
    # ---------------------------------------------------------------

    def _update_ui_state(self) -> None:
        """Update UI based on state manager (call from UI thread)."""
        if not self._state_manager or not self._root:
            return
            
        info = self._state_manager.get_state_info()
        
        # Update status bar
        self._status_label.configure(text=info.status_text, text_color=info.status_color)
        self._status_dot.configure(text_color=info.status_color)
        
        # Update button state
        if info.can_play:
            self._btn_toggle.configure(text="▶ Play", state="normal")
        elif info.can_resume:
            self._btn_toggle.configure(text="▶ Resume", state="normal")
        elif info.can_pause:
            self._btn_toggle.configure(text="⏸ Pause", state="normal")
        else:
            self._btn_toggle.configure(state="disabled")

    def _schedule_ui_update(self) -> None:
        """Schedule UI update on UI thread (call from any thread)."""
        if self._root:
            try:
                self._root.after(0, self._update_ui_state)
            except Exception:
                pass

    def _update_progress(self, text: str) -> None:
        """Update progress label."""
        if self._root:
            try:
                self._root.after(0, self._progress_label.configure, {"text": text})
            except Exception:
                pass

    def _refresh_content_visibility(self) -> None:
        """Show/hide controls based on content availability."""
        if not hasattr(self, '_controls_frame'):
            return
            
        has_content = bool(self._transcript_text)
        
        # Clear everything first
        self._controls_frame.pack_forget()
        if hasattr(self, '_spectrum_frame'):
            self._spectrum_frame.pack_forget()
        self._progress_label.pack_forget()
        self._transcript_header.pack_forget()
        self._transcript_box.pack_forget()
        
        # Show expand button only if content exists
        if hasattr(self, '_expand_btn'):
            if has_content:
                self._expand_btn.grid()
            else:
                self._expand_btn.grid_remove()
        
        # Repack if content exists
        if has_content:
            self._controls_frame.pack(fill="x", padx=8, pady=(4, 2))
            if hasattr(self, '_spectrum_frame'):
                self._spectrum_frame.pack(fill="x", padx=8, pady=2)
            self._progress_label.pack(fill="x", padx=12, pady=(2, 0))
            self._transcript_header.pack(fill="x", padx=8, pady=(2, 0))
            self._transcript_box.pack(fill="both", expand=True, padx=8, pady=(2, 8))

    # ---------------------------------------------------------------
    # HIGHLIGHT CALLBACK (from SyncController)
    # ---------------------------------------------------------------

    def _on_highlight_word(self, chunk_idx: int, start_char: int, end_char: int) -> None:
        """
        Highlight callback from SyncController.
        
        GUARANTEE: Always called from UI thread (via _update_sync loop).
        """
        if self._transcript_renderer:
            # Use highlight_relative as defined in TranscriptRenderer
            self._transcript_renderer.highlight_relative(chunk_idx, start_char, end_char)

    # ---------------------------------------------------------------
    # EVENT HANDLERS (Domain Events)
    # ---------------------------------------------------------------

    async def on_hotkey_pressed(self, event: HotkeyPressed) -> None:
        """Handle hotkey press."""
        if event.action == HotkeyAction.READ:
            self.show()

    async def on_text_captured(self, event: TextCaptured) -> None:
        """Handle text capture event."""
        logger.info("Text captured: %d chars", len(event.raw_text))
        
        # Reset all controllers
        if self._sync_controller:
            self._sync_controller.clear_all()
        if self._state_manager:
            self._state_manager.reset()
        
        # Store text
        self._transcript_text = event.raw_text
        self._audio_paths.clear()
        
        # Update state
        if self._state_manager:
            self._state_manager.start_processing(total_chunks=0)  # Will update later
        
        self._schedule_ui_update()
        self._refresh_content_visibility()
        
        # Auto-expand
        if not self._expanded and self._root:
            self._root.after(0, self._toggle_expand)

    async def on_synthesis_started(self, event: SynthesisStarted) -> None:
        """Handle synthesis start."""
        self._total_chunks = event.total_chunks
        
        if self._state_manager and self._state_manager.state == PlaybackState.IDLE:
            self._state_manager.start_processing(event.total_chunks)
        
        self._update_progress(f"Synthesizing chunk {event.chunk_index + 1}/{event.total_chunks}")
        self._schedule_ui_update()

    async def on_synthesis_complete(self, event: SynthesisComplete) -> None:
        """Handle synthesis completion."""
        logger.info("Synthesis complete: chunk=%d", event.chunk_index)
        
        # Store audio path
        self._audio_paths.append(event.audio_path)
        
        # Store word boundaries in SyncController
        if event.word_boundaries and self._sync_controller:
            self._sync_controller.load_boundaries(event.chunk_index, event.word_boundaries)
        
        # Update progress
        self._update_progress(f"Synthesized {event.chunk_index + 1}/{event.total_chunks}")
        
        # If all chunks done, transition to READY
        if len(self._audio_paths) == event.total_chunks:
            if self._state_manager:
                self._state_manager.processing_complete()
            
            # Save session
            if self._transcript_text:
                self._save_current_session()
            
            self._schedule_ui_update()

    async def on_text_processed(self, event) -> None:
        """Handle text processing (chunk split)."""
        if self._transcript_renderer:
            # Set transcript content (will calculate offsets)
            if self._root:
                self._root.after(0, self._transcript_renderer.set_content, list(event.chunks))

    async def on_playback_started(self, event: PlaybackStarted) -> None:
        """Handle playback start."""
        logger.info("Playback started: chunk=%d", event.chunk_index)
        
        # Update state manager
        if self._state_manager:
            self._state_manager.start_playback(event.chunk_index)
        
        # Start spectrum
        if self._spectrum:
            self._spectrum.set_active(True)
        
        # Start sync
        if self._sync_controller:
            success = self._sync_controller.start_sync(event.chunk_index, event.timestamp)
            if not success:
                logger.warning("Sync pending - boundaries not ready for chunk %d", event.chunk_index)
        
        self._schedule_ui_update()
        
    async def on_playback_paused(self, event: PlaybackPaused) -> None:
        """Handle playback paused."""
        logger.info("Playback paused")
        if self._state_manager:
            self._state_manager.pause_playback()
        if self._sync_controller:
            self._sync_controller.pause_sync()
        if self._spectrum:
            self._spectrum.set_active(False)
        self._schedule_ui_update()

    async def on_playback_resumed(self, event: PlaybackResumed) -> None:
        """Handle playback resumed."""
        logger.info("Playback resumed")
        if self._state_manager:
            self._state_manager.resume_playback()
        if self._sync_controller:
            self._sync_controller.resume_sync(event.timestamp)
        if self._spectrum:
            self._spectrum.set_active(True)
        self._schedule_ui_update()

    async def on_playback_stopped(self, event: PlaybackStopped) -> None:
        """Handle playback stop."""
        logger.info("Playback stopped: reason=%s", event.reason)
        
        # Stop spectrum
        if self._spectrum:
            self._spectrum.set_active(False)
        
        # Stop sync
        if self._sync_controller:
            self._sync_controller.stop_sync()
        
        # Update state
        if self._state_manager:
            if event.reason == "completed":
                self._state_manager.complete_playback()
            elif event.reason == "error":
                self._state_manager.error_occurred()
            else:
                self._state_manager.stop_playback()
        
        self._schedule_ui_update()

    # ---------------------------------------------------------------
    # BUTTON CALLBACKS
    # ---------------------------------------------------------------

    def _on_toggle_play(self) -> None:
        """Handle Play/Pause/Resume toggle."""
        if not self._state_manager:
            return
            
        info = self._state_manager.get_state_info()
        
        if info.can_pause:
            self._publish_event(TrayAction(action=TrayActionType.PAUSE))
            # State update will happen via event loop
        elif info.can_resume:
            self._publish_event(TrayAction(action=TrayActionType.RESUME))
        elif info.can_play:
            # Replay from start
            if self._transcript_text:
                self._publish_event(TextCaptured(raw_text=self._transcript_text))
        
        # UI update scheduled by event handlers

    def _on_voice_change(self, value: str) -> None:
        """Handle voice change."""
        gender = "male" if value == "Ardi" else "female"
        self._publish_event(
            TrayAction(action=TrayActionType.CHANGE_VOICE, value=gender)
        )
        logger.info("Voice changed: %s", value)
        
        # Auto-replay
        if self._transcript_text and self._state_manager and not self._state_manager.is_idle:
            if self._transcript_text:
                self._publish_event(TextCaptured(raw_text=self._transcript_text))

    def _on_speed_change(self, value: str) -> None:
        """Handle speed change."""
        speed = value.replace("x", "")
        self._publish_event(
            TrayAction(action=TrayActionType.CHANGE_SPEED, value=speed)
        )
        if hasattr(self, '_speed_label'):
            self._speed_label.configure(text=value)
        logger.info("Speed changed: %s", value)
        
        # Auto-replay
        if self._transcript_text and self._state_manager and not self._state_manager.is_idle:
            if self._transcript_text:
                self._publish_event(TextCaptured(raw_text=self._transcript_text))

    def _on_save_audio(self) -> None:
        """Save audio to file."""
        session = self._session_service.get_last_session()
        
        if not session or not session.audio_paths:
            logger.warning("No session to save")
            return

        available = [Path(p) for p in session.audio_paths if Path(p).exists()]
        if not available:
            logger.warning("No audio files found")
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
                    base = Path(save_path)
                    for i, src in enumerate(available):
                        dest = base.parent / f"{base.stem}_part{i + 1}{base.suffix}"
                        shutil.copy2(src, dest)
                logger.info("Audio saved: %s", save_path)
            except Exception:
                logger.exception("Failed to save audio")

    def _on_copy_transcript(self) -> None:
        """Copy transcript to clipboard."""
        if self._transcript_renderer:
            text = self._transcript_renderer.get_text()
            if text and self._root:
                try:
                    self._root.clipboard_clear()
                    self._root.clipboard_append(text)
                    self._copy_btn.configure(text="✅ Copied!")
                    self._root.after(1500, lambda: self._copy_btn.configure(text="📋 Copy"))
                    logger.info("Transcript copied")
                except Exception:
                    logger.exception("Failed to copy transcript")

    def _on_toggle_mode(self) -> None:
        """Toggle to silent mode."""
        self._publish_event(
            TrayAction(action=TrayActionType.TOGGLE_MODE, value="silent")
        )
        if self._root:
            self._root.withdraw()

    def _on_close(self) -> None:
        """Close/minimize widget."""
        if self._root:
            self._root.withdraw()

    # ---------------------------------------------------------------
    # TRAY ACTIONS
    # ---------------------------------------------------------------

    async def on_tray_action(self, event: TrayAction) -> None:
        """Handle tray actions."""
        if event.action == TrayActionType.TOGGLE_MODE:
            if event.value == "widget":
                self.show()
            elif event.value == "toggle_window":
                if self._root and self._root.winfo_viewable():
                    self.hide()
                else:
                    self.show()
            elif event.value == "silent":
                self.hide()

    # ---------------------------------------------------------------
    # WINDOW MANAGEMENT
    # ---------------------------------------------------------------

    def _toggle_expand(self) -> None:
        """Toggle expanded/compact mode."""
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

    def _start_drag(self, event) -> None:
        """Start window drag."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event) -> None:
        """Handle window drag."""
        if self._root:
            x = self._root.winfo_x() + event.x - self._drag_x
            y = self._root.winfo_y() + event.y - self._drag_y
            self._root.geometry(f"+{x}+{y}")

    def show(self) -> None:
        """Show widget window."""
        if self._root:
            try:
                self._root.after(0, self._root.deiconify)
            except Exception:
                pass

    def hide(self) -> None:
        """Hide widget window."""
        if self._root:
            try:
                self._root.after(0, self._root.withdraw)
            except Exception:
                pass

    # ---------------------------------------------------------------
    # SESSION MANAGEMENT
    # ---------------------------------------------------------------

    def _save_current_session(self) -> None:
        """Save current session to history."""
        if not self._transcript_text:
            return
            
        try:
            # Get boundaries from sync controller
            boundaries = {}
            if self._sync_controller:
                for i in range(self._total_chunks):
                    if self._sync_controller.has_boundaries(i):
                        # Convert back to tuple format for storage
                        # (This is a temporary bridge - ideally session would store WordBoundary objects)
                        boundaries[i] = []
            
            self._session_service.save_session(
                text=self._transcript_text,
                audio_paths=self._audio_paths,
                word_boundaries=boundaries,
                config=self._config.model_dump(),
            )
            logger.info("Session saved to history")
        except Exception:
            logger.exception("Failed to save session")

    # ---------------------------------------------------------------
    # EVENT PUBLISHING
    # ---------------------------------------------------------------

    def _publish_event(self, event: object) -> None:
        """Publish event to event bus."""
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(event),
            self._loop,
        )
