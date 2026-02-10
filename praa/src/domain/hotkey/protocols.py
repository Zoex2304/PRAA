"""
Hotkey Domain — Protocols (Interface Segregation)

Defines the contract for any hotkey listener implementation.
The application layer depends on this protocol, not the concrete pynput service.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IHotkeyListener(Protocol):
    """
    Contract for a global hotkey listener.

    Implementations must:
    - Register platform-specific global hotkeys
    - Publish HotkeyPressed events via EventBus when triggered
    - Support clean start/stop lifecycle
    """

    def start(self) -> None:
        """Begin listening for registered hotkeys."""
        ...

    def stop(self) -> None:
        """Stop listening and release all hotkey registrations."""
        ...
