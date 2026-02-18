"""Widget button action handlers."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING

from src.infrastructure.events import TextCaptured, TrayAction, TrayActionType

if TYPE_CHECKING:
    from .service import WidgetService

logger = logging.getLogger(__name__)


class WidgetActions:
    """Handles user-initiated button callbacks."""

    @staticmethod
    def on_toggle_play(widget: WidgetService) -> None:
        if not widget._state_manager:
            return
        info = widget._state_manager.get_state_info()
        if info.can_pause:
            widget._publish_event(TrayAction(action=TrayActionType.PAUSE))
        elif info.can_resume:
            widget._publish_event(TrayAction(action=TrayActionType.RESUME))
        elif info.can_play and widget._transcript_text:
            widget._publish_event(TextCaptured(raw_text=widget._transcript_text))

    @staticmethod
    def on_voice_change(widget: WidgetService, value: str) -> None:
        gender = "male" if value == "Ardi" else "female"
        widget._publish_event(TrayAction(action=TrayActionType.CHANGE_VOICE, value=gender))
        logger.info("Voice changed: %s", value)
        if widget._transcript_text and widget._state_manager and not widget._state_manager.is_idle:
            widget._publish_event(TextCaptured(raw_text=widget._transcript_text))

    @staticmethod
    def on_speed_change(widget: WidgetService, value: str) -> None:
        speed = value.replace("x", "")
        widget._publish_event(TrayAction(action=TrayActionType.CHANGE_SPEED, value=speed))
        if hasattr(widget, '_speed_label'):
            widget._speed_label.configure(text=value)
        logger.info("Speed changed: %s", value)
        if widget._transcript_text and widget._state_manager and not widget._state_manager.is_idle:
            widget._publish_event(TextCaptured(raw_text=widget._transcript_text))

    @staticmethod
    def on_save_audio(widget: WidgetService) -> None:
        session = widget._session_service.get_last_session()
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

    @staticmethod
    def on_copy_transcript(widget: WidgetService) -> None:
        if not widget._transcript_renderer:
            return
        text = widget._transcript_renderer.get_text()
        if text and widget._root:
            try:
                widget._root.clipboard_clear()
                widget._root.clipboard_append(text)
                widget._copy_btn.configure(text="Copied!")
                widget._root.after(1500, lambda: widget._copy_btn.configure(text="Copy"))
                logger.info("Transcript copied")
            except Exception:
                logger.exception("Failed to copy transcript")

    @staticmethod
    def on_toggle_mode(widget: WidgetService) -> None:
        widget._publish_event(TrayAction(action=TrayActionType.TOGGLE_MODE, value="silent"))
        if widget._root:
            widget._root.withdraw()

    @staticmethod
    def on_close(widget: WidgetService) -> None:
        if widget._log_handler:
            try:
                logging.getLogger().removeHandler(widget._log_handler)
            except Exception:
                pass
        if widget._root:
            widget._root.withdraw()
