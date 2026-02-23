from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from src.domain.audio.service import AudioService
from src.domain.config.models import AppConfig, LanguagePreference
from src.domain.config.theme_config import ThemeConfig
from src.domain.session.service import SessionService
from src.domain.widget.interpolator import WordBoundaryInterpolator
from src.domain.widget.spectrum import SpectrumAnalyzer
from src.domain.widget.state import PlaybackState, PlaybackStateManager
from src.domain.widget.sync import SyncController
from src.domain.widget.time_provider import CalibratedTimeProvider
from src.domain.widget.tips import Feature, TipsManager
from src.infrastructure.activity_tracker import ActivityTracker
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    ConfigChanged,
    FileTextReady,
    FileUploadFailed,
    FileUploadRequested,
    HotkeyAction,
    HotkeyPressed,
    OcrCaptureFailed,
    OcrCaptureRequested,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SplashCompleted,
    SynthesisComplete,
    SynthesisStarted,
    TextCaptured,
    TextProcessed,
    TrayAction,
    TrayActionType,
)
from src.presentation.app import FletApp
from src.presentation.controllers.playback_controller import PlaybackController

logger = logging.getLogger(__name__)

_THREAD_REFRESH_TICKS = 40  # ~2 s at 50 ms tick
_SYSTEM_REFRESH_TICKS = 100  # ~5 s


class WidgetController:
    def __init__(
        self,
        config: AppConfig,
        theme: ThemeConfig,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        session_service: SessionService,
        audio_service: AudioService | None = None,
        config_service=None,
        activity_tracker: ActivityTracker | None = None,
        is_first_run: bool = False,
        on_first_run_complete: Callable[[], None] | None = None,
        tips_manager: TipsManager | None = None,
    ):
        self._config = config
        self._theme = theme
        self._event_bus = event_bus
        self._loop = loop
        self._session_service = session_service
        self._audio_service = audio_service
        self._config_service = config_service
        self._activity_tracker = activity_tracker or ActivityTracker()
        self._is_first_run = is_first_run
        self._on_first_run_complete = on_first_run_complete
        self._tips_manager = tips_manager
        # Feature gate: block all hotkey/OCR actions until splash is dismissed.
        self._splash_active = is_first_run

        self._state_manager = PlaybackStateManager()
        self._spectrum = SpectrumAnalyzer(num_bands=theme.dimensions.spectrum_bar_count)
        self._interpolator = WordBoundaryInterpolator()
        self._playback_controller = PlaybackController(event_bus, self._state_manager)
        self._log_handler = None
        self._tick_count = 0
        self._current_playing_chunk = 0
        self._synthesis_complete_count = 0
        self._total_chunks = 0

        self._time_provider: CalibratedTimeProvider | None = None
        self._sync_controller: SyncController | None = None
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
        self._has_been_activated = False
        self._active_upload_path: Path | None = None
        self._current_source: str = "USER_BLOCK"

        self._speed_seek_chunk: int | None = None
        self._resynthesizing_for_speed: bool = False

        self._app = FletApp(
            theme=theme,
            config=config,
            get_sessions=self._get_sessions,
            on_load_session=self._load_session,
            on_toggle_play=self._handle_toggle_play,
            on_settings_voice=self._handle_voice_change,
            on_settings_language=self._handle_language_change,
            on_play_chunk=self._handle_play_chunk,
            on_pause_chunk=self._handle_pause_chunk,
            on_seek_chunk=self._handle_seek_chunk,
            on_seek_position=self._handle_seek_position,
            on_download_audio_requested=self._handle_download_request,
            on_download_save=self._handle_download_save,
            on_file_uploaded=self._handle_file_uploaded,
            on_ocr_capture=self._handle_ocr_capture,
            on_speed_change=self._handle_speed_change,
            show_splash=is_first_run,
            on_splash_dismissed=self._handle_splash_dismissed,
            on_history_viewed=self._mark_history_viewed,
            on_settings_opened=self._mark_settings_opened,
        )

    @property
    def app(self) -> FletApp:
        return self._app

    def set_log_handler(self, handler) -> None:
        self._log_handler = handler
        if self._app.debug:
            self._app.debug.set_log_handler(handler)
        if self._activity_tracker and self._app.debug:
            self._app.debug.set_activity_tracker(self._activity_tracker)

    def start(self) -> None:
        self._running = True
        self._ui_task = self._loop.create_task(self._ui_loop())
        self._activity_tracker.report("WidgetController", "Idle", "Waiting for input")

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

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_hotkey_pressed(self, event: HotkeyPressed) -> None:
        if self._splash_active:
            return
        if event.action == HotkeyAction.READ:
            self.show()

    def is_splash_active(self) -> bool:
        """True while the first-run splash is displayed; features are blocked."""
        return self._splash_active

    async def on_splash_completed(self, event: SplashCompleted) -> None:
        """No-op — splash dismissal is handled synchronously via _handle_splash_dismissed."""
        pass

    async def on_text_captured(self, event: TextCaptured) -> None:
        logger.info(
            "Text captured: %d chars (source=%s)",
            len(event.raw_text),
            event.source_type,
        )
        self._activity_tracker.report("WidgetController", "Processing", "Text captured")
        self._current_source = getattr(event, "source_type", "USER_BLOCK")

        # Mark the corresponding feature as tried (eliminates its tip).
        if self._tips_manager and not self._resynthesizing_for_speed:
            if self._current_source == "OCR":
                self._tips_manager.mark_feature_used(Feature.OCR)
            elif self._current_source == "FILE_UPLOAD":
                self._tips_manager.mark_feature_used(Feature.UPLOAD)
            elif self._current_source == "USER_BLOCK":
                self._tips_manager.mark_feature_used(Feature.READ)

        if not self._has_been_activated:
            self._app.activate_bar()
            self._has_been_activated = True

        # Speed re-synthesis preserves seek position; any other capture clears it.
        if self._resynthesizing_for_speed:
            self._resynthesizing_for_speed = False
        else:
            self._speed_seek_chunk = None

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

        # Show processing phase (no auto-expand)
        if self._app.compact_milestone:
            self._app.compact_milestone.reset()
        self._app.set_phase("processing")
        self._app.advance_milestone(0, "Reading clipboard…")
        self._app.reset_queue()
        self._app.reset_transcript_audio()

        self._schedule_ui_update()

    async def on_text_processed(self, event: TextProcessed) -> None:
        self._text_chunks = list(event.chunks)
        self._chunk_statuses.clear()
        n = len(event.chunks)
        self._activity_tracker.report(
            "WidgetController", "Processing", f"Synthesizing {n} chunks"
        )

        self._app.advance_milestone(2, f"0 / {n} chunks")
        self._app.setup_queue(n)
        self._app.set_audio_pending()

        if self._app.home and self._app.home.transcript:
            self._app.home.transcript.set_content(self._text_chunks)
        self._playback_controller.set_transcript(self._transcript_text)

        for i, chunk in enumerate(event.chunks):
            name = chunk.strip().replace("\n", " ")[:30] + (
                "…" if len(chunk) > 30 else ""
            )
            self._app.update_queue_status(i, "pending", name)
            self._chunk_statuses[i] = "pending"

        if self._active_upload_path:
            self._app.advance_upload_step(self._active_upload_path, 3)

    async def on_synthesis_started(self, event: SynthesisStarted) -> None:
        self._total_chunks = event.total_chunks
        self._chunk_statuses[event.chunk_index] = "processing"
        self._app.update_queue_status(event.chunk_index, "processing")

        if self._state_manager.state == PlaybackState.IDLE:
            self._state_manager.start_processing(event.total_chunks)

        self._schedule_ui_update()

    async def on_synthesis_complete(self, event: SynthesisComplete) -> None:
        self._audio_paths.append(event.audio_path)
        self._chunk_statuses[event.chunk_index] = "ready"
        self._synthesis_complete_count += 1

        if event.word_boundaries and self._sync_controller:
            self._sync_controller.load_boundaries(
                event.chunk_index, event.word_boundaries
            )
        elif event.sentence_boundaries and self._sync_controller:
            interpolated = self._interpolator.interpolate_from_sentences(
                event.sentence_boundaries
            )
            from src.domain.processor.text_offset_mapper import calculate_text_offsets

            enhanced = calculate_text_offsets(event.chunk_text, interpolated)
            self._sync_controller.load_boundaries(event.chunk_index, enhanced)

        self._app.update_queue_status(event.chunk_index, "ready")
        self._app.update_milestone_detail(
            2, f"{self._synthesis_complete_count} / {event.total_chunks} chunks"
        )

        if len(self._audio_paths) == event.total_chunks:
            self._state_manager.processing_complete()
            # Skip session save for speed re-syntheses to avoid duplicate records.
            if self._transcript_text and self._speed_seek_chunk is None:
                self._save_session()
            self._app.set_audio_ready(list(self._audio_paths))
            if self._active_upload_path:
                self._app.advance_upload_step(self._active_upload_path, 4)
            if self._speed_seek_chunk is not None and self._audio_service:
                seek = self._speed_seek_chunk
                self._speed_seek_chunk = None
                paths = list(self._audio_paths)
                self._audio_service.play_from_chunk(min(seek, len(paths) - 1), paths)

        self._schedule_ui_update()

    async def on_playback_started(self, event: PlaybackStarted) -> None:
        self._state_manager.start_playback(event.chunk_index)
        self._current_playing_chunk = event.chunk_index
        self._activity_tracker.report(
            "WidgetController",
            "Playing",
            f"Chunk {event.chunk_index + 1}/{event.total_chunks}",
        )

        if event.chunk_index > 0:
            self._chunk_statuses[event.chunk_index - 1] = "done"
            self._app.update_queue_status(event.chunk_index - 1, "done")
        self._chunk_statuses[event.chunk_index] = "playing"
        self._app.update_queue_status(event.chunk_index, "playing")

        # Milestone complete → switch to playing phase
        self._app.complete_milestone()
        self._app.set_phase("playing")

        if self._active_upload_path:
            self._app.complete_upload_card(self._active_upload_path)
            self._active_upload_path = None

        self._spectrum.set_active(True)

        if self._time_provider:
            self._time_provider.set_chunk(event.chunk_index)
            self._time_provider.calibrate()

        if self._sync_controller and not self._sync_controller.has_boundaries(
            event.chunk_index
        ):
            self._sync_controller.wait_for_boundaries(event.chunk_index)

        self._schedule_ui_update()

    async def on_playback_paused(self, event: PlaybackPaused) -> None:
        self._state_manager.pause_playback()
        self._spectrum.set_active(False)
        self._activity_tracker.report("WidgetController", "Paused")
        if self._app.compact_bar:
            self._app.compact_bar.set_play_icon(False)
        self._app.update_queue_status(self._current_playing_chunk, "paused")
        self._schedule_ui_update()

    async def on_playback_resumed(self, event: PlaybackResumed) -> None:
        self._state_manager.resume_playback()
        self._spectrum.set_active(True)
        self._activity_tracker.report(
            "WidgetController", "Playing", f"Chunk {self._current_playing_chunk + 1}"
        )
        self._app.update_queue_status(self._current_playing_chunk, "playing")
        self._schedule_ui_update()

    async def on_playback_stopped(self, event: PlaybackStopped) -> None:
        self._spectrum.set_active(False)
        self._activity_tracker.report("WidgetController", "Idle", "Playback stopped")

        if self._sync_controller:
            self._sync_controller.clear_highlight()
            if self._app.home and self._app.home.transcript:
                self._app.home.transcript.clear_highlight()

        if event.reason == "completed":
            self._state_manager.complete_playback()
            if self._tips_manager and self._tips_manager.should_show():
                self._loop.create_task(self._show_tip_after_playback())
        elif event.reason == "error":
            self._state_manager.error_occurred()
        else:
            self._state_manager.stop_playback()

        self._schedule_ui_update()

    async def on_ocr_failed(self, event: OcrCaptureFailed) -> None:
        """Show a brief status notification for non-cancellation OCR failures."""
        if event.reason == "cancelled":
            return
        msg = "No text found" if event.reason == "empty" else "OCR error"
        if self._app.compact_bar:
            self._app.compact_bar.set_status(msg, "#ef4444")
        await asyncio.sleep(2.0)
        # Restore normal status after notification
        state_info = self._state_manager.get_state_info()
        if self._app.compact_bar:
            self._app.compact_bar.set_status(
                state_info.status_text, state_info.status_color
            )

    async def on_file_text_ready(self, event: FileTextReady) -> None:
        from src.domain.upload.models import UploadRecord

        record = UploadRecord(
            source_path=event.source_path,
            file_name=event.source_path.name,
            file_size_bytes=event.file_size_bytes,
            word_count=event.word_count,
            is_image=event.is_image,
        )
        self._active_upload_path = event.source_path
        self._app.add_upload_record(record)
        self._app.advance_upload_step(event.source_path, 2)

    async def on_file_upload_failed(self, event: FileUploadFailed) -> None:
        logger.warning(
            "File upload failed: %s — %s", event.source_path.name, event.reason
        )
        if self._app.compact_bar:
            self._app.compact_bar.set_status(
                f"Upload failed: {event.reason}", "#ef4444"
            )
        await asyncio.sleep(2.0)
        state_info = self._state_manager.get_state_info()
        if self._app.compact_bar:
            self._app.compact_bar.set_status(
                state_info.status_text, state_info.status_color
            )

    async def on_config_changed(self, event: ConfigChanged) -> None:
        """Sync UI when config changes (e.g. speed slider in another path)."""
        if event.key == "speed_rate":
            try:
                speed = float(event.new_value)
                self._app.update_speed_display(speed)
            except (TypeError, ValueError):
                pass

    async def on_tray_action(self, event: TrayAction) -> None:
        if event.action == TrayActionType.TOGGLE_MODE:
            if event.value in ("widget", "toggle_window"):
                self.show()
            elif event.value == "silent":
                self.hide()

    # ------------------------------------------------------------------
    # Playback control callbacks (from UI buttons)
    # ------------------------------------------------------------------

    def _handle_toggle_play(self) -> None:
        self._playback_controller.toggle_play(self._publish_event)

    def _handle_play_chunk(self, chunk_index: int) -> None:
        if not self._audio_service or not self._audio_paths:
            return
        if chunk_index >= len(self._audio_paths):
            return
        # If paused on exactly this chunk, resume rather than restart
        paused_here = (
            self._audio_service.is_playing
            and not self._audio_service.is_actively_playing
            and self._current_playing_chunk == chunk_index
        )
        if paused_here:
            self._publish_event(TrayAction(action=TrayActionType.RESUME))
            return
        self._audio_service.play_from_chunk(chunk_index, self._audio_paths)

    def _handle_pause_chunk(self, chunk_index: int) -> None:
        # Pause current playback regardless of which chunk triggered it
        self._publish_event(TrayAction(action=TrayActionType.PAUSE))

    def _handle_seek_chunk(self, chunk_index: int) -> None:
        """Seek to a chunk by clicking the timeline."""
        self._handle_play_chunk(chunk_index)

    def _handle_seek_position(self, chunk_index: int, fraction: float) -> None:
        """Seek within the currently playing chunk via timeline drag."""
        if not self._audio_service:
            return
        if chunk_index == self._current_playing_chunk:
            self._audio_service.seek_within_chunk(fraction)
        else:
            self._handle_play_chunk(chunk_index)

    def _handle_voice_change(self, voice_id: str) -> None:
        self._publish_event(
            TrayAction(action=TrayActionType.CHANGE_VOICE, value=voice_id)
        )

    def _handle_language_change(self, lang_code: str) -> None:
        if self._config_service:
            asyncio.run_coroutine_threadsafe(
                self._config_service.update(
                    "language_preference", LanguagePreference(lang_code)
                ),
                self._loop,
            )

    def _handle_download_request(self, paths: list[Path]) -> None:
        self._app.save_audio_dialog(paths)

    def _handle_download_save(self, paths: list[Path], save_path: Path) -> None:
        asyncio.run_coroutine_threadsafe(
            self._merge_and_save(paths, save_path), self._loop
        )

    async def _merge_and_save(self, paths: list[Path], save_path: Path) -> None:
        try:
            import numpy as np
            import soundfile as sf

            chunks = []
            samplerate = 24000
            for p in paths:
                data, sr = sf.read(str(p))
                chunks.append(data)
                samplerate = sr
            merged = np.concatenate(chunks, axis=0)
            sf.write(str(save_path), merged, samplerate)
            logger.info("Audio saved: %s", save_path)
        except Exception:
            logger.exception("Failed to merge/save audio")

    def _handle_file_uploaded(self, path: Path) -> None:
        self._publish_event(FileUploadRequested(source_path=path))

    def _handle_ocr_capture(self) -> None:
        self._publish_event(OcrCaptureRequested())

    def _handle_speed_change(self, new_speed: float) -> None:
        if self._config_service:
            asyncio.run_coroutine_threadsafe(
                self._config_service.update("speed_rate", new_speed),
                self._loop,
            )
        # If actively playing or paused, re-synthesize at new speed and resume
        # from the current chunk position so the change is instant.
        state = self._state_manager.state
        is_active = state in (PlaybackState.PLAYING, PlaybackState.PAUSED)
        if self._transcript_text and is_active and self._audio_paths:
            self._speed_seek_chunk = self._current_playing_chunk
            self._resynthesizing_for_speed = True
            if self._tips_manager:
                self._tips_manager.mark_feature_used(Feature.SPEED)
            self._publish_event(TextCaptured(raw_text=self._transcript_text))

    def _handle_splash_dismissed(self) -> None:
        self._splash_active = False
        self._activity_tracker.report(
            "WidgetController", "Ready", "Awaiting first input"
        )
        if self._on_first_run_complete:
            self._on_first_run_complete()

    def _mark_history_viewed(self) -> None:
        if self._tips_manager:
            self._tips_manager.mark_feature_used(Feature.HISTORY)

    def _mark_settings_opened(self) -> None:
        if self._tips_manager:
            self._tips_manager.mark_feature_used(Feature.SETTINGS)

    async def _show_tip_after_playback(self) -> None:
        """Show the next untried-feature tip after a completed reading."""
        await asyncio.sleep(0.8)
        if not self._tips_manager:
            return
        tip = self._tips_manager.get_next_tip()
        if tip is None:
            return
        self._app.show_tip(
            tip.text,
            on_skip=self._tips_manager.mark_skipped,
            on_understand=lambda: (
                None
            ),  # Dismissed — tip shows again until feature is tried
        )

    # ------------------------------------------------------------------
    # Word sync callback
    # ------------------------------------------------------------------

    def _on_highlight_word(
        self, chunk_idx: int, start_char: int, end_char: int
    ) -> None:
        if self._app.home and self._app.home.transcript:
            self._app.home.transcript.highlight_relative(
                chunk_idx, start_char, end_char
            )

    def _publish_event(self, event: object) -> None:
        asyncio.run_coroutine_threadsafe(self._event_bus.publish(event), self._loop)

    def _schedule_ui_update(self) -> None:
        state_info = self._state_manager.get_state_info()
        if self._app.compact_bar:
            self._app.compact_bar.set_status(
                state_info.status_text, state_info.status_color
            )
            self._app.compact_bar.set_play_icon(
                state_info.state == PlaybackState.PLAYING,
                state_info.state == PlaybackState.PAUSED,
            )
        if self._app.debug:
            self._app.debug.update_state(
                state_info.status_text, state_info.status_color
            )

    # ------------------------------------------------------------------
    # UI loop
    # ------------------------------------------------------------------

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

                # Queue + timeline progress
                if is_playing and self._audio_service:
                    pos = self._audio_service.position_ms
                    dur = self._audio_service.duration_ms
                    if dur > 0:
                        self._app.update_queue_progress(
                            self._current_playing_chunk, pos, dur
                        )

                # Time display
                if (
                    is_playing
                    and self._audio_service
                    and self._app.home
                    and self._app.home.transcript
                ):
                    pos = self._audio_service.position_ms
                    m = int(pos / 1000) // 60
                    s = int(pos / 1000) % 60
                    self._app.home.transcript.set_time(f"{m}:{s:02d}")

                # Thread activity + system KPI refresh
                if self._tick_count % _THREAD_REFRESH_TICKS == 0 and self._app.debug:
                    log_act = (
                        self._log_handler.get_thread_activity()
                        if self._log_handler
                        else {}
                    )
                    self._app.debug.update_thread_panel(log_act)

                if self._tick_count % _SYSTEM_REFRESH_TICKS == 0 and self._app.debug:
                    self._app.debug.refresh_system()

                # Log drain → log page
                if self._log_handler and self._app.logs:
                    for entry in self._log_handler.drain_new_entries():
                        self._app.logs.append(entry)

            except Exception as e:
                logger.debug("UI loop error: %s", e)

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

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
                source_type=self._current_source,
            )
            logger.info("Session saved to history")
        except Exception:
            logger.exception("Failed to save session")
