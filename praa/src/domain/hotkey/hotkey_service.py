
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from pynput import keyboard

from src.domain.config.models import AppConfig
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import HotkeyAction, HotkeyPressed

logger = logging.getLogger(__name__)


def _parse_hotkey(hotkey_str: str) -> frozenset[keyboard.Key | keyboard.KeyCode]:
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

    def __init__(self, config: AppConfig, event_bus: EventBus, loop: asyncio.AbstractEventLoop) -> None:
        self._event_bus = event_bus
        self._loop = loop

        # Parse configured hotkeys into key sets
        self._hotkey_read = _parse_hotkey(config.hotkey_read)
        self._hotkey_stop = _parse_hotkey(config.hotkey_stop)

        # Track currently pressed keys
        self._pressed: set[keyboard.Key | keyboard.KeyCode] = set()
        self._listener: keyboard.Listener | None = None

        # Controller for simulating Ctrl+C (auto-copy)
        self._controller = keyboard.Controller()

        logger.info(
            "[bold]Hotkey service[/]: READ=[cyan]%s[/], STOP=[cyan]%s[/]",
            config.hotkey_read,
            config.hotkey_stop,
        )

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return

        self._pressed.add(key)

        # Normalize: treat ctrl_r as ctrl_l for matching
        normalized = self._normalize_pressed()

        if self._hotkey_read.issubset(normalized):
            logger.info("[bold green]READ hotkey[/] triggered — auto-copying selection")
            self._pressed.clear()
            self._auto_copy_and_publish(HotkeyAction.READ)

        elif self._hotkey_stop.issubset(normalized):
            logger.info("[bold red]STOP hotkey[/] triggered")
            self._publish_event(HotkeyAction.STOP)
            self._pressed.clear()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        self._pressed.discard(key)

    def _normalize_pressed(self) -> set[keyboard.Key | keyboard.KeyCode]:
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

    def _auto_copy_and_publish(self, action: HotkeyAction) -> None:
        try:
            # Release currently held modifier keys to avoid Ctrl+Shift+C
            self._controller.release(keyboard.Key.shift)
            self._controller.release(keyboard.Key.ctrl_l)
            time.sleep(0.05)

            # Simulate Ctrl+C
            with self._controller.pressed(keyboard.Key.ctrl_l):
                self._controller.tap(keyboard.KeyCode.from_vk(0x43))  # 'C'
            time.sleep(0.15)  # Wait for clipboard to update

        except Exception:
            logger.exception("Auto-copy failed, proceeding with existing clipboard")

        # Publish event regardless — clipboard service will read whatever is there
        self._publish_event(action)

    def _publish_event(self, action: HotkeyAction) -> None:
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(HotkeyPressed(action=action)),
            self._loop,
        )

    def start(self) -> None:
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
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            self._pressed.clear()
            logger.info("Hotkey listener stopped")
