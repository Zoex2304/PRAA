"""
Tray Domain — Protocols (Interface Segregation)

Defines the contract for any system tray manager implementation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.infrastructure.events import PlaybackState


@runtime_checkable
class ITrayManager(Protocol):
    """
    Contract for a system tray icon manager.

    Implementations must:
    - Display a persistent system tray icon
    - Provide a right-click context menu with playback controls
    - Update tooltip to reflect current playback state
    - Publish TrayAction events for user interactions
    """

    def start(self) -> None:
        """Show the system tray icon and begin handling interactions."""
        ...

    def stop(self) -> None:
        """Remove the system tray icon and clean up."""
        ...

    def update_status(self, state: PlaybackState) -> None:
        """
        Update the tray icon's tooltip to reflect playback state.

        Args:
            state: Current playback state (idle, playing, paused, stopped).
        """
        ...
