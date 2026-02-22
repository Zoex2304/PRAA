from __future__ import annotations

import logging

from src.domain.widget.state import PlaybackStateManager
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import TextCaptured, TrayAction, TrayActionType

logger = logging.getLogger(__name__)


class PlaybackController:
    def __init__(self, event_bus: EventBus, state_manager: PlaybackStateManager):
        self._event_bus = event_bus
        self._state_manager = state_manager
        self._transcript_text = ""

    def set_transcript(self, text: str):
        self._transcript_text = text

    def toggle_play(self, publish: callable):
        info = self._state_manager.get_state_info()
        if info.can_pause:
            publish(TrayAction(action=TrayActionType.PAUSE))
        elif info.can_resume:
            publish(TrayAction(action=TrayActionType.RESUME))
        elif info.can_play and self._transcript_text:
            publish(TextCaptured(raw_text=self._transcript_text))

    def change_voice(self, value: str, publish: callable):
        gender = "male" if value == "Ardi" else "female"
        publish(TrayAction(action=TrayActionType.CHANGE_VOICE, value=gender))
        logger.info("Voice changed: %s", value)
        if self._transcript_text and not self._state_manager.is_idle:
            publish(TextCaptured(raw_text=self._transcript_text))

    def change_speed(self, value: str, publish: callable):
        speed = value.replace("x", "")
        publish(TrayAction(action=TrayActionType.CHANGE_SPEED, value=speed))
        logger.info("Speed changed: %s", value)
        if self._transcript_text and not self._state_manager.is_idle:
            publish(TextCaptured(raw_text=self._transcript_text))
