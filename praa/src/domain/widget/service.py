"""Widget service facade. Coordinates extracted modules."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from src.domain.config.models import AppConfig
from src.infrastructure.event_bus import EventBus
from src.domain.session.service import SessionService
from src.infrastructure.events import (
    HotkeyPressed,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SynthesisComplete,
    TrayAction,
    TextCaptured,
)
from src.infrastructure.gui_logger import TkinterLogHandler

from .theme import (
    BG_DARK, SPECTRUM_COLORS,
    WIDGET_WIDTH, COMPACT_HEIGHT, EXPANDED_HEIGHT,
)
from .builder import UIBuilder
from .handlers import WidgetEventHandler
from .actions import WidgetActions
from .history import HistoryManager
from .sync import SyncController
from .transcript import TranscriptRenderer
from .state import PlaybackStateManager
from .time_provider import CalibratedTimeProvider
from .interpolator import WordBoundaryInterpolator
from .spectrum import SpectrumAnalyzer

logger = logging.getLogger(__name__)


class WidgetService:
    """Floating overlay widget. Thin facade over extracted modules."""

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        session_service: SessionService,
        audio_service=None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._loop = loop
        self._session_service = session_service
        self._audio_service = audio_service

        self._log_handler = TkinterLogHandler()
        logging.getLogger().addHandler(self._log_handler)

        self._root: Optional[ctk.CTk] = None
        self._thread: Optional[threading.Thread] = None

        self._state_manager: Optional[PlaybackStateManager] = None
        self._sync_controller: Optional[SyncController] = None
        self._transcript_renderer: Optional[TranscriptRenderer] = None
        self._spectrum: Optional[SpectrumAnalyzer] = None
        self._chunk_progress = None
        self._debug_panel = None
        self._time_provider = None
        self._interpolator = None

        self._transcript_text: Optional[str] = None
        self._audio_paths: list[Path] = []
        self._total_chunks = 0
        self._processed_chunks = 0

        self._expanded = False
        self._running = False
        self._debug_visible = False
        self._history_panel_visible = False
        self._settings_popup = None

        self._drag_x = 0
        self._drag_y = 0

    

    def start(self) -> None:
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_ui, name="widget-ui", daemon=True,
        )
        self._thread.start()
        logger.info("Widget UI started (mode=%s)", self._config.ui_mode.value)

    def stop(self) -> None:
        self._running = False
        if self._sync_controller:
            self._sync_controller.reset()
        if self._spectrum:
            self._spectrum.set_active(False)
        if self._chunk_progress:
            self._chunk_progress.reset()
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

        UIBuilder.build_compact_bar(self)
        UIBuilder.build_expanded_panel(self)
        self._expanded_frame.grid_remove()

        self._state_manager = PlaybackStateManager()
        self._time_provider = CalibratedTimeProvider(
            get_player_position_ms=lambda: self._audio_service.position_ms if self._audio_service else 0.0,
            get_player_state=lambda: self._audio_service.is_actively_playing if self._audio_service else False,
            latency_compensation_ms=self._config.playback_latency_ms,
        )
        self._interpolator = WordBoundaryInterpolator()
        self._sync_controller = SyncController(
            time_provider=self._time_provider,
            highlight_callback=self._on_highlight_word,
        )
        self._transcript_renderer = TranscriptRenderer(self._transcript_box)
        self._spectrum = SpectrumAnalyzer(num_bands=16)

        self._animate_spectrum()
        self._update_sync()
        self._root.mainloop()

    

    def _animate_spectrum(self) -> None:
        if not self._running or self._root is None:
            return
        if self._spectrum:
            block = None
            samplerate = 24000
            if self._audio_service and self._audio_service.is_actively_playing:
                block = self._audio_service.current_block
                samplerate = self._audio_service.samplerate
            self._spectrum.update(block=block, samplerate=samplerate)
            if self._expanded and hasattr(self, '_large_spectrum'):
                self._spectrum.draw(self._large_spectrum, WIDGET_WIDTH - 24, 50, SPECTRUM_COLORS)
        try:
            self._root.after(50, self._animate_spectrum)
        except Exception:
            pass

    def _update_sync(self) -> None:
        if not self._running or self._root is None:
            return
        if self._sync_controller and self._time_provider:
            try:
                self._sync_controller.update_sync()
                if self._audio_service and hasattr(self, '_time_label'):
                    pos = self._audio_service.current_position_global_ms / 1000
                    dur = self._audio_service.total_duration_ms / 1000
                    has_hours = dur >= 3600

                    def fmt(s, force_hours=False):
                        h = int(s // 3600)
                        m = int((s % 3600) // 60)
                        s = int(s % 60)
                        if force_hours or h > 0:
                            return f"{h:02}:{m:02}:{s:02}"
                        return f"{m:02}:{s:02}"

                    self._time_label.configure(text=f"{fmt(pos, has_hours)}/{fmt(dur, has_hours)}")

                if self._debug_visible and self._debug_panel and self._audio_service:
                    self._debug_panel.update_metrics(
                        state_text=self._state_manager.get_state_info().status_text if self._state_manager else "Unknown",
                        queue_size=self._audio_service.queue_size,
                        is_playing=self._audio_service.is_playing,
                        position_ms=self._audio_service.position_ms,
                    )
                    self._log_handler.poll(self._debug_panel.get_log_widget())
            except Exception:
                logger.debug("Sync update error", exc_info=True)
        try:
            self._root.after(50, self._update_sync)
        except Exception:
            pass

    

    def _update_ui_state(self) -> None:
        if not self._state_manager or not self._root:
            return
        info = self._state_manager.get_state_info()
        self._status_label.configure(text=info.status_text, text_color=info.status_color)
        self._status_dot.configure(text_color=info.status_color)
        if info.can_play:
            self._btn_toggle.configure(text="\u25b6 Play", state="normal")
        elif info.can_resume:
            self._btn_toggle.configure(text="\u25b6 Resume", state="normal")
        elif info.can_pause:
            self._btn_toggle.configure(text="\u23f8 Pause", state="normal")
        else:
            self._btn_toggle.configure(state="disabled")

    def _schedule_ui_update(self) -> None:
        if self._root:
            try:
                self._root.after(0, self._update_ui_state)
            except Exception:
                pass

    def _update_progress(self, text: str) -> None:
        if self._root:
            try:
                self._root.after(0, self._progress_label.configure, {"text": text})
            except Exception:
                pass

    def _refresh_content_visibility(self) -> None:
        if not hasattr(self, '_controls_frame'):
            return
        has_content = bool(self._transcript_text)

        self._controls_frame.pack_forget()
        if hasattr(self, '_chunk_progress') and self._chunk_progress:
            self._chunk_progress.pack_forget()
        if hasattr(self, '_extra_panel_frame'):
            self._extra_panel_frame.pack_forget()
        if hasattr(self, '_spectrum_frame'):
            self._spectrum_frame.pack_forget()
        self._progress_label.pack_forget()
        self._transcript_header.pack_forget()
        self._transcript_box.pack_forget()

        if hasattr(self, '_expand_btn'):
            if has_content:
                self._expand_btn.grid()
            else:
                self._expand_btn.grid_remove()

        if has_content:
            self._controls_frame.pack(fill="x", padx=6, pady=(4, 2))
            if hasattr(self, '_chunk_progress') and self._chunk_progress:
                self._chunk_progress.pack(fill="x", padx=10, pady=(2, 2))
            if hasattr(self, '_extra_panel_frame'):
                if self._debug_visible or self._history_panel_visible:
                    self._extra_panel_frame.pack(fill="x", padx=6)
            if hasattr(self, '_spectrum_frame'):
                self._spectrum_frame.pack(fill="x", padx=6, pady=2)
            self._progress_label.pack(fill="x", padx=12, pady=(2, 0))
            self._transcript_header.pack(fill="x", padx=6, pady=(2, 0))
            self._transcript_box.pack(fill="both", expand=True, padx=6, pady=(2, 6))

    def _on_highlight_word(self, chunk_idx: int, start_char: int, end_char: int) -> None:
        if self._transcript_renderer:
            self._transcript_renderer.highlight_relative(chunk_idx, start_char, end_char)

    

    async def on_hotkey_pressed(self, event: HotkeyPressed) -> None:
        await WidgetEventHandler.on_hotkey_pressed(self, event)

    async def on_text_captured(self, event: TextCaptured) -> None:
        await WidgetEventHandler.on_text_captured(self, event)

    async def on_synthesis_started(self, event) -> None:
        await WidgetEventHandler.on_synthesis_started(self, event)

    async def on_synthesis_complete(self, event: SynthesisComplete) -> None:
        await WidgetEventHandler.on_synthesis_complete(self, event)

    async def on_text_processed(self, event) -> None:
        await WidgetEventHandler.on_text_processed(self, event)

    async def on_playback_started(self, event: PlaybackStarted) -> None:
        await WidgetEventHandler.on_playback_started(self, event)

    async def on_playback_paused(self, event: PlaybackPaused) -> None:
        await WidgetEventHandler.on_playback_paused(self, event)

    async def on_playback_resumed(self, event: PlaybackResumed) -> None:
        await WidgetEventHandler.on_playback_resumed(self, event)

    async def on_playback_stopped(self, event: PlaybackStopped) -> None:
        await WidgetEventHandler.on_playback_stopped(self, event)

    async def on_tray_action(self, event: TrayAction) -> None:
        await WidgetEventHandler.on_tray_action(self, event)

    

    def _on_toggle_play(self) -> None:
        WidgetActions.on_toggle_play(self)

    def _on_voice_change(self, value: str) -> None:
        WidgetActions.on_voice_change(self, value)

    def _on_speed_change(self, value: str) -> None:
        WidgetActions.on_speed_change(self, value)

    def _on_save_audio(self) -> None:
        WidgetActions.on_save_audio(self)

    def _on_copy_transcript(self) -> None:
        WidgetActions.on_copy_transcript(self)

    def _on_toggle_mode(self) -> None:
        WidgetActions.on_toggle_mode(self)

    def _on_close(self) -> None:
        WidgetActions.on_close(self)

    

    def _toggle_debug(self) -> None:
        self._debug_visible = not self._debug_visible
        self._refresh_content_visibility()

    def _toggle_history(self) -> None:
        HistoryManager.toggle_history(self)

    def _show_settings_menu(self) -> None:
        if hasattr(self, '_settings_popup') and self._settings_popup is not None:
            try:
                self._settings_popup.destroy()
            except Exception:
                pass
            self._settings_popup = None
            return

        import customtkinter as ctk
        from .theme import BG_PANEL, BG_INPUT, ACCENT, TEXT_DIM, TEXT_MUTED, BORDER_SUBTLE

        popup = ctk.CTkToplevel(self._root)
        popup.overrideredirect(True)
        popup.configure(fg_color=BG_PANEL)
        popup.attributes("-topmost", True)

        # Position below the kebab button
        btn = self._kebab_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 4
        popup.geometry(f"180x90+{x}+{y}")

        # Voice row
        ctk.CTkLabel(
            popup, text="Voice", font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
        ).grid(row=0, column=0, padx=(10, 4), pady=(8, 4), sticky="w")

        voice_menu = ctk.CTkOptionMenu(
            popup, variable=self._voice_var,
            values=["Ardi", "Gadis"], width=90, height=22,
            font=ctk.CTkFont(size=10), fg_color=BG_INPUT,
            button_color=ACCENT, command=self._on_voice_change,
        )
        voice_menu.grid(row=0, column=1, padx=(0, 10), pady=(8, 4), sticky="e")

        # Speed row
        ctk.CTkLabel(
            popup, text="Speed", font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
        ).grid(row=1, column=0, padx=(10, 4), pady=(4, 8), sticky="w")

        speed_menu = ctk.CTkOptionMenu(
            popup, variable=self._speed_var,
            values=["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"],
            width=90, height=22, font=ctk.CTkFont(size=10),
            fg_color=BG_INPUT, button_color=ACCENT,
            command=self._on_speed_change,
        )
        speed_menu.grid(row=1, column=1, padx=(0, 10), pady=(4, 8), sticky="e")

        popup.grid_columnconfigure(1, weight=1)

        self._settings_popup = popup

        # Close popup when clicking elsewhere
        def _on_focus_out(e):
            try:
                popup.destroy()
            except Exception:
                pass
            self._settings_popup = None

        popup.bind("<FocusOut>", _on_focus_out)

    def _save_current_session(self) -> None:
        HistoryManager.save_current_session(self)

    

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._expanded_frame.grid()
            h = EXPANDED_HEIGHT
            self._expand_btn.configure(text="\u25b2")
        else:
            self._expanded_frame.grid_remove()
            h = COMPACT_HEIGHT
            self._expand_btn.configure(text="\u25bc")
        x = self._root.winfo_x() if self._root else 50
        y = self._root.winfo_y() if self._root else 50
        if self._root:
            self._root.geometry(f"{WIDGET_WIDTH}x{h}+{x}+{y}")

    def _start_drag(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event) -> None:
        if self._root:
            x = self._root.winfo_x() + event.x - self._drag_x
            y = self._root.winfo_y() + event.y - self._drag_y
            self._root.geometry(f"+{x}+{y}")

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

    def _publish_event(self, event: object) -> None:
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(event),
            self._loop,
        )
