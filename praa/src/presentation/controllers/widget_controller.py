from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from src.domain.audio.service import AudioService
from src.domain.config.models import AppConfig
from src.domain.config.theme_config import ThemeConfig
from src.domain.session.service import SessionService
from src.domain.widget.interpolator import WordBoundaryInterpolator
from src.domain.widget.spectrum import SpectrumAnalyzer
from src.domain.widget.state import PlaybackState, PlaybackStateManager
from src.domain.widget.sync import SyncController
from src.domain.widget.time_provider import CalibratedTimeProvider
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    HotkeyAction,
    HotkeyPressed,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SynthesisComplete,
    SynthesisStarted,
    TextCaptured,
    TextProcessed,
    TrayAction,
    TrayActionType,
)
from src.presentation.app import FletApp

logger = logging.getLogger(__name__)

_THREAD_REFRESH_TICKS = 40  # refresh every ~2s at 50ms tick rate


class WidgetController:
    def __init__(
        self,
        config: AppConfig,
        theme: ThemeConfig,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        session_service: SessionService,
        audio_service: Optional[AudioService] = None,
    ):
        self._config = config
        self._theme = theme
        self._event_bus = event_bus
        self._loop = loop
        self._session_service = session_service
        self._audio_service = audio_service

        self._state_manager = PlaybackStateManager()
        self._spectrum = SpectrumAnalyzer(num_bands=theme.dimensions.spectrum_bar_count)
        self._interpolator = WordBoundaryInterpolator()
        self._log_handler = None
        self._tick_count = 0
        self._current_playing_chunk = 0
        self._synthesis_complete_count = 0
        self._total_chunks = 0

        self._time_provider: Optional[CalibratedTimeProvider] = None
        self._sync_controller: Optional[SyncController] = None
        if audio_service:
            self._time_provider = CalibratedTimeProvider(
                get_player_position_ms=lambda: audio_service.position_ms,
                get_player_state=lambda: audio_service.is_playing,
                latency_compensation_ms=config.playback_latency_ms,
            )
            self._sync_controller = SyncController(
                time_provider=self._time_provider,
                highlight_callback=self._on_highlight_word,
            )

        self._transcript_text = ""
        self._audio_paths: list[Path] = []
        self._text_chunks: list[str] = []
        self._chunk_statuses: dict[int, str] = {}
        self._running = False

        self._app = FletApp(
            theme=theme,
            get_sessions=self._get_sessions,
            on_load_session=self._load_session,
        )

    @property
    def app(self) -> FletApp:
        return self._app

    def set_log_handler(self, handler) -> None:
        self._log_handler = handler
        if self._app.debug:
            self._app.debug.set_log_handler(handler)

    def start(self) -> None:
        self._running = True
        self._ui_task = self._loop.create_task(self._ui_loop())

    def stop(self) -> None:
        self._running = False
        if hasattr(self, "_ui_task"):
            self._ui_task.cancel()
        self._spectrum.reset()
        if self._sync_controller:
            self._sync_controller.reset()

    def show(self) -> None:
        self._app.show()

    def hide(self) -> None:
        self._app.hide()

    async def on_hotkey_pressed(self, event: HotkeyPressed) -> None:
        if event.action == HotkeyAction.READ:
            self.show()

    async def on_text_captured(self, event: TextCaptured) -> None:
        logger.info("Text captured: %d chars", len(event.raw_text))

        if self._sync_controller:
            self._sync_controller.reset()
        self._state_manager.reset()
        self._synthesis_complete_count = 0
        self._total_chunks = 0

        if self._audio_service and self._audio_service.is_playing:
            self._publish_event(TrayAction(action=TrayActionType.STOP))

        self._transcript_text = event.raw_text
        self._audio_paths.clear()
        self._state_manager.start_processing(total_chunks=0)

        # Show milestone loading state (no auto-expand)
        if self._app.compact_milestone:
            self._app.compact_milestone.reset()
        self._app.set_phase("processing")
        self._app.advance_milestone(0, "Reading clipboard…")

        self._schedule_ui_update()

    async def on_text_processed(self, event: TextProcessed) -> None:
        self._text_chunks = list(event.chunks)
        self._chunk_statuses.clear()
        n = len(event.chunks)

        # Milestone: steps 0+1 done, now synthesizing
        self._app.advance_milestone(2, f"0 / {n} chunks")

        if self._app.home and self._app.home.transcript:
            self._app.home.transcript.set_content(self._text_chunks)

        if self._app.debug:
            self._app.debug.reset_chunks()
            for i, chunk in enumerate(event.chunks):
                name = chunk.strip().replace("\n", " ")[:30] + ("…" if len(chunk) > 30 else "")
                self._app.debug.update_chunk_status(i, "pending", name)
                self._chunk_statuses[i] = "pending"

        if self._app.chunk_progress:
            self._app.chunk_progress.setup(n)

    async def on_synthesis_started(self, event: SynthesisStarted) -> None:
        self._total_chunks = event.total_chunks
        self._chunk_statuses[event.chunk_index] = "processing"

        if self._app.debug:
            self._app.debug.update_chunk_status(event.chunk_index, "processing")

        if self._state_manager.state == PlaybackState.IDLE:
            self._state_manager.start_processing(event.total_chunks)

        self._schedule_ui_update()

    async def on_synthesis_complete(self, event: SynthesisComplete) -> None:
        self._audio_paths.append(event.audio_path)
        self._chunk_statuses[event.chunk_index] = "ready"
        self._synthesis_complete_count += 1

        if event.word_boundaries and self._sync_controller:
            self._sync_controller.load_boundaries(event.chunk_index, event.word_boundaries)
        elif event.sentence_boundaries and self._sync_controller:
            interpolated = self._interpolator.interpolate_from_sentences(event.sentence_boundaries)
            from src.domain.processor.text_offset_mapper import calculate_text_offsets
            enhanced = calculate_text_offsets(event.chunk_text, interpolated)
            self._sync_controller.load_boundaries(event.chunk_index, enhanced)

        if self._app.debug:
            self._app.debug.update_chunk_status(event.chunk_index, "ready")

        # Update milestone synthesis detail
        self._app.update_milestone_detail(
            2, f"{self._synthesis_complete_count} / {event.total_chunks} chunks"
        )

        if len(self._audio_paths) == event.total_chunks:
            self._state_manager.processing_complete()
            if self._transcript_text:
                self._save_session()

        self._schedule_ui_update()

    async def on_playback_started(self, event: PlaybackStarted) -> None:
        self._state_manager.start_playback(event.chunk_index)
        self._current_playing_chunk = event.chunk_index

        if event.chunk_index > 0:
            self._chunk_statuses[event.chunk_index - 1] = "done"
        self._chunk_statuses[event.chunk_index] = "playing"

        if self._app.debug:
            if event.chunk_index > 0:
                self._app.debug.update_chunk_status(event.chunk_index - 1, "done")
            self._app.debug.update_chunk_status(event.chunk_index, "playing")

        if self._app.chunk_progress:
            if event.chunk_index > 0:
                self._app.chunk_progress.update_status(event.chunk_index - 1, "done")
            self._app.chunk_progress.update_status(event.chunk_index, "playing")

        # Milestone complete → switch to playing phase
        self._app.complete_milestone()
        self._app.set_phase("playing")

        self._spectrum.set_active(True)

        if self._time_provider:
            self._time_provider.set_chunk(event.chunk_index)
            self._time_provider.calibrate()

        if self._sync_controller and not self._sync_controller.has_boundaries(event.chunk_index):
            self._sync_controller.wait_for_boundaries(event.chunk_index)

        self._schedule_ui_update()

    async def on_playback_paused(self, event: PlaybackPaused) -> None:
        self._state_manager.pause_playback()
        self._spectrum.set_active(False)
        self._schedule_ui_update()

    async def on_playback_resumed(self, event: PlaybackResumed) -> None:
        self._state_manager.resume_playback()
        self._spectrum.set_active(True)
        self._schedule_ui_update()

    async def on_playback_stopped(self, event: PlaybackStopped) -> None:
        self._spectrum.set_active(False)

        if self._sync_controller:
            self._sync_controller.clear_highlight()
            if self._app.home and self._app.home.transcript:
                self._app.home.transcript.clear_highlight()

        if event.reason == "completed":
            self._state_manager.complete_playback()
        elif event.reason == "error":
            self._state_manager.error_occurred()
        else:
            self._state_manager.stop_playback()

        self._schedule_ui_update()

    async def on_tray_action(self, event: TrayAction) -> None:
        if event.action == TrayActionType.TOGGLE_MODE:
            if event.value in ("widget", "toggle_window"):
                self.show()
            elif event.value == "silent":
                self.hide()

    def _on_highlight_word(self, chunk_idx: int, start_char: int, end_char: int) -> None:
        if self._app.home and self._app.home.transcript:
            self._app.home.transcript.highlight_relative(chunk_idx, start_char, end_char)

    def _publish_event(self, event: object) -> None:
        asyncio.run_coroutine_threadsafe(self._event_bus.publish(event), self._loop)

    def _schedule_ui_update(self) -> None:
        state_info = self._state_manager.get_state_info()
        if self._app.compact_bar:
            self._app.compact_bar.set_status(state_info.status_text, state_info.status_color)
            self._app.compact_bar.set_play_icon(
                state_info.state == PlaybackState.PLAYING,
                state_info.state == PlaybackState.PAUSED,
            )
        if self._app.debug:
            self._app.debug.update_state(state_info.status_text, state_info.status_color)

    async def _ui_loop(self) -> None:
        while self._running:
            try:
                self._tick_count += 1
                is_playing = self._state_manager.state == PlaybackState.PLAYING

                # Spectrum update
                if is_playing and self._audio_service:
                    block = self._audio_service.current_block
                    bars = self._spectrum.update(block, self._audio_service.samplerate)
                else:
                    bars = self._spectrum.update(None)

                self._app.update_spectra(bars)

                # Word sync
                if is_playing and self._sync_controller:
                    self._sync_controller.tick()

                # Queue chunk progress
                if is_playing and self._audio_service and self._app.debug:
                    pos = self._audio_service.position_ms
                    dur = self._audio_service.duration_ms
                    if dur > 0:
                        self._app.debug.update_chunk_progress(
                            self._current_playing_chunk, pos, dur
                        )

                # Time display
                if is_playing and self._audio_service and self._app.home:
                    if self._app.home.transcript:
                        pos = self._audio_service.position_ms
                        m = int(pos / 1000) // 60
                        s = int(pos / 1000) % 60
                        self._app.home.transcript.set_time(f"{m}:{s:02d}")

                # Per-thread activity refresh (every ~2s)
                if self._tick_count % _THREAD_REFRESH_TICKS == 0 and self._app.debug:
                    activity = (
                        self._log_handler.get_thread_activity()
                        if self._log_handler
                        else {}
                    )
                    self._app.debug.update_thread_panel(activity)

                # Drain log entries into log page
                if self._log_handler and self._app.logs:
                    for entry in self._log_handler.drain_new_entries():
                        self._app.logs.append(entry)

            except Exception as e:
                logger.debug("UI loop error: %s", e)

            await asyncio.sleep(0.05)

    def _get_sessions(self):
        return self._session_service.get_recent_sessions()

    def _load_session(self, session) -> None:
        self._transcript_text = session.text_content
        self._publish_event(TextCaptured(raw_text=session.text_content))

    def _save_session(self) -> None:
        if not self._transcript_text:
            return
        try:
            boundaries = {}
            if self._sync_controller:
                for i in range(self._total_chunks):
                    if self._sync_controller.has_boundaries(i):
                        boundaries[i] = []
            self._session_service.save_session(
                text=self._transcript_text,
                audio_paths=list(self._audio_paths),
                word_boundaries=boundaries,
                config=self._config.model_dump(),
            )
            logger.info("Session saved to history")
        except Exception:
            logger.exception("Failed to save session")
