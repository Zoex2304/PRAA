"""Widget domain event handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.infrastructure.events import (
    HotkeyAction,
    HotkeyPressed,
    PlaybackPaused,
    PlaybackResumed,
    PlaybackStarted,
    PlaybackStopped,
    SynthesisComplete,
    TextCaptured,
    TrayAction,
    TrayActionType,
)
from .state import PlaybackState

if TYPE_CHECKING:
    from .service import WidgetService

logger = logging.getLogger(__name__)


class WidgetEventHandler:
    """Processes domain events for the widget."""

    @staticmethod
    async def on_hotkey_pressed(widget: WidgetService, event: HotkeyPressed) -> None:
        if event.action == HotkeyAction.READ:
            widget.show()

    @staticmethod
    async def on_text_captured(widget: WidgetService, event: TextCaptured) -> None:
        logger.info("Text captured: %d chars", len(event.raw_text))

        if widget._sync_controller:
            widget._sync_controller.reset()
        if widget._state_manager:
            widget._state_manager.reset()

        if widget._audio_service and widget._audio_service.is_playing:
            widget._publish_event(TrayAction(action=TrayActionType.STOP))

        widget._transcript_text = event.raw_text
        widget._audio_paths.clear()

        if widget._state_manager:
            widget._state_manager.start_processing(total_chunks=0)

        widget._schedule_ui_update()
        widget._refresh_content_visibility()

        if not widget._expanded and widget._root:
            widget._root.after(0, widget._toggle_expand)

    @staticmethod
    async def on_synthesis_started(widget: WidgetService, event) -> None:
        widget._total_chunks = event.total_chunks
        widget._chunk_statuses[event.chunk_index] = "processing"

        if widget._debug_panel:
            if event.chunk_index == 0:
                pass # Reset handled by on_text_processed
            widget._debug_panel.update_chunk_status(event.chunk_index, "processing")

        if widget._state_manager and widget._state_manager.state == PlaybackState.IDLE:
            widget._state_manager.start_processing(event.total_chunks)

        widget._update_progress(f"Synthesizing chunk {event.chunk_index + 1}/{event.total_chunks}")
        widget._schedule_ui_update()

    @staticmethod
    async def on_synthesis_complete(widget: WidgetService, event: SynthesisComplete) -> None:
        logger.info("Synthesis complete: chunk=%d", event.chunk_index)

        widget._audio_paths.append(event.audio_path)
        widget._chunk_statuses[event.chunk_index] = "ready"

        if event.word_boundaries and widget._sync_controller:
            widget._sync_controller.load_boundaries(event.chunk_index, event.word_boundaries)
        elif event.sentence_boundaries and widget._sync_controller:
            interpolated = widget._interpolator.interpolate_from_sentences(event.sentence_boundaries)
            from src.domain.processor.text_offset_mapper import calculate_text_offsets
            enhanced = calculate_text_offsets(event.chunk_text, interpolated)
            widget._sync_controller.load_boundaries(event.chunk_index, enhanced)

        widget._update_progress(f"Synthesized {event.chunk_index + 1}/{event.total_chunks}")

        if widget._debug_panel:
            widget._debug_panel.update_chunk_status(event.chunk_index, "ready")

        if len(widget._audio_paths) == event.total_chunks:
            if widget._state_manager:
                widget._state_manager.processing_complete()
            if widget._transcript_text:
                widget._save_current_session()
            widget._schedule_ui_update()

    @staticmethod
    async def on_text_processed(widget: WidgetService, event) -> None:
        if widget._transcript_renderer and widget._root:
            widget._root.after(0, widget._transcript_renderer.set_content, list(event.chunks))
            
        widget._text_chunks = list(event.chunks)
        widget._chunk_statuses.clear()
            
        # Populate debug panel queue with chunk names
        if widget._debug_panel:
            widget._debug_panel.reset_chunks()
            for i, chunk in enumerate(event.chunks):
                name = chunk.strip().replace("\n", " ")[:30] + ("..." if len(chunk) > 30 else "")
                widget._debug_panel.update_chunk_status(i, "pending", name)
                widget._chunk_statuses[i] = "pending"
        else:
             for i, chunk in enumerate(event.chunks):
                widget._chunk_statuses[i] = "pending"

    @staticmethod
    async def on_playback_started(widget: WidgetService, event: PlaybackStarted) -> None:
        logger.info("Playback started: chunk=%d", event.chunk_index)

        if widget._state_manager:
            widget._state_manager.start_playback(event.chunk_index)

        if event.chunk_index > 0:
            widget._chunk_statuses[event.chunk_index - 1] = "done"
        widget._chunk_statuses[event.chunk_index] = "playing"

        if widget._debug_panel:
            # Mark previous as done
            if event.chunk_index > 0:
                widget._debug_panel.update_chunk_status(event.chunk_index - 1, "done")
            widget._debug_panel.update_chunk_status(event.chunk_index, "playing")


        if widget._spectrum:
            widget._spectrum.set_active(True)

        if widget._time_provider:
            widget._time_provider.set_chunk(event.chunk_index)
            widget._time_provider.calibrate()

        if widget._sync_controller and not widget._sync_controller.has_boundaries(event.chunk_index):
            widget._sync_controller.wait_for_boundaries(event.chunk_index)
            logger.warning("Sync waiting - boundaries not ready for chunk %d", event.chunk_index)

        widget._schedule_ui_update()

    @staticmethod
    async def on_playback_paused(widget: WidgetService, event: PlaybackPaused) -> None:
        if widget._state_manager:
            widget._state_manager.pause_playback()
        if widget._spectrum:
            widget._spectrum.set_active(False)
        widget._schedule_ui_update()

    @staticmethod
    async def on_playback_resumed(widget: WidgetService, event: PlaybackResumed) -> None:
        if widget._state_manager:
            widget._state_manager.resume_playback()
        if widget._spectrum:
            widget._spectrum.set_active(True)
        widget._schedule_ui_update()

    @staticmethod
    async def on_playback_stopped(widget: WidgetService, event: PlaybackStopped) -> None:
        logger.info("Playback stopped: reason=%s", event.reason)

        if widget._spectrum:
            widget._spectrum.set_active(False)
        if widget._sync_controller:
            widget._sync_controller.clear_highlight()

        if widget._state_manager:
            if event.reason == "completed":
                widget._state_manager.complete_playback()
            elif event.reason == "error":
                widget._state_manager.error_occurred()
            else:
                widget._state_manager.stop_playback()

        widget._schedule_ui_update()

    @staticmethod
    async def on_tray_action(widget: WidgetService, event: TrayAction) -> None:
        if event.action == TrayActionType.TOGGLE_MODE:
            if event.value == "widget":
                widget.show()
            elif event.value == "toggle_window":
                if widget._root and widget._root.winfo_viewable():
                    widget.hide()
                else:
                    widget.show()
            elif event.value == "silent":
                widget.hide()
