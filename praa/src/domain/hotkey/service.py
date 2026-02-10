"""
Hotkey Domain — pynput-based Global Hotkey Service

Concrete implementation of IHotkeyListener using pynput.
Publishes HotkeyPressed events — knows nothing about clipboard, TTS, or audio (SRP).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from pynput import keyboard

from src.domain.config.models import AppConfig
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import HotkeyAction, HotkeyPressed

logger = logging.getLogger(__name__)


def _parse_hotkey(hotkey_str: str) -> frozenset[keyboard.Key | keyboard.KeyCode]:
    """
    Parse a hotkey string like '<ctrl>+<shift>+r' into a frozenset of pynput keys.

    Args:
        hotkey_str: Hotkey string in pynput format.

    Returns:
        Frozen set of key objects for combination matching.
    """
    keys: set[keyboard.Key | keyboard.KeyCode] = set()
    for part in hotkey_str.lower().split("+"):
        part = part.strip()
        if part == "<ctrl>":
            keys.add(keyboard.Key.ctrl_l)
        elif part == "<shift>":
            keys.add(keyboard.Key.shift)
        elif part == "<alt>":
            keys.add(keyboard.Key.alt_l)
        elif part.startswith("<") and part.endswith(">"):
            # Try to resolve as a named key
            key_name = part[1:-1]
            try:
                keys.add(keyboard.Key[key_name])
            except KeyError:
                logger.warning("Unknown key name: %s", key_name)
        else:
            # Single character key — use vk (virtual key code) for reliable
            # matching when modifier keys are held (Ctrl+Shift changes char)
            keys.add(keyboard.KeyCode.from_vk(ord(part.upper())))
    return frozenset(keys)


class PynputHotkeyService:
    """
    Global hotkey listener using pynput.

    Registers Ctrl+Shift+R (read) and Ctrl+Shift+S (stop) by default.
    When a registered combination is pressed, publishes a HotkeyPressed event
    to the EventBus. This service has no knowledge of what happens after
    the event is published — pure SRP.
    """

    def __init__(self, config: AppConfig, event_bus: EventBus, loop: asyncio.AbstractEventLoop) -> None:
        self._event_bus = event_bus
        self._loop = loop

        # Parse configured hotkeys into key sets
        self._hotkey_read = _parse_hotkey(config.hotkey_read)
        self._hotkey_stop = _parse_hotkey(config.hotkey_stop)

        # Track currently pressed keys
        self._pressed: set[keyboard.Key | keyboard.KeyCode] = set()
        self._listener: keyboard.Listener | None = None

        logger.info(
            "Hotkey service initialized: READ=%s, STOP=%s",
            config.hotkey_read,
            config.hotkey_stop,
        )

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key press: track pressed keys and check for hotkey matches."""
        if key is None:
            return

        self._pressed.add(key)

        # Normalize: treat ctrl_r as ctrl_l for matching
        normalized = self._normalize_pressed()

        if self._hotkey_read.issubset(normalized):
            logger.debug("Hotkey READ triggered")
            self._publish_event(HotkeyAction.READ)
            self._pressed.clear()

        elif self._hotkey_stop.issubset(normalized):
            logger.debug("Hotkey STOP triggered")
            self._publish_event(HotkeyAction.STOP)
            self._pressed.clear()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key release: remove from tracked set."""
        if key is None:
            return
        self._pressed.discard(key)

    def _normalize_pressed(self) -> set[keyboard.Key | keyboard.KeyCode]:
        """Normalize modifier keys and character keys for consistent matching.

        Modifier normalization: ctrl_r → ctrl_l, shift_r → shift, alt_r → alt_l.
        Character normalization: KeyCode(char, vk) → KeyCode.from_vk(vk) so that
        hash values match those produced by _parse_hotkey. This is necessary
        because pynput's KeyCode.__hash__ differs between from_char and from_vk
        forms even when __eq__ returns True.
        """
        normalized: set[keyboard.Key | keyboard.KeyCode] = set()
        for key in self._pressed:
            if key == keyboard.Key.ctrl_r:
                normalized.add(keyboard.Key.ctrl_l)
            elif key == keyboard.Key.shift_r:
                normalized.add(keyboard.Key.shift)
            elif key == keyboard.Key.alt_r:
                normalized.add(keyboard.Key.alt_l)
            elif isinstance(key, keyboard.KeyCode) and key.vk is not None:
                normalized.add(keyboard.KeyCode.from_vk(key.vk))
            else:
                normalized.add(key)
        return normalized

    def _publish_event(self, action: HotkeyAction) -> None:
        """Thread-safe event publishing from pynput's listener thread."""
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(HotkeyPressed(action=action)),
            self._loop,
        )

    def start(self) -> None:
        """Begin listening for global hotkeys."""
        if self._listener is not None:
            logger.warning("Hotkey listener already running")
            return

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started")

    def stop(self) -> None:
        """Stop listening and release all hotkey registrations."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            self._pressed.clear()
            logger.info("Hotkey listener stopped")
