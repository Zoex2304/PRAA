"""
Clipboard Domain — tkinter-based Clipboard Service

Concrete implementation of IClipboardReader using tkinter (stdlib).
Zero-install, reliable on Windows. Publishes TextCaptured events.
"""

from __future__ import annotations

import logging
import tkinter as tk

from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import TextCaptured

logger = logging.getLogger(__name__)


class TkinterClipboardService:
    """
    Clipboard reader using tkinter's built-in clipboard access.

    tkinter is part of Python stdlib and provides reliable clipboard
    access on Windows without any additional dependencies.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._root: tk.Tk | None = None

    def _get_root(self) -> tk.Tk:
        """Lazily create a hidden tkinter root window for clipboard access."""
        if self._root is None:
            self._root = tk.Tk()
            self._root.withdraw()  # Hide the window
        return self._root

    def read(self) -> str | None:
        """
        Read text content from the system clipboard.

        Returns:
            The clipboard text, or None if empty or non-text.
        """
        try:
            root = self._get_root()
            text = root.clipboard_get()

            if text and text.strip():
                logger.debug("Clipboard captured: %d characters", len(text))
                return text.strip()

            logger.debug("Clipboard is empty or whitespace-only")
            return None

        except tk.TclError:
            # Clipboard contains non-text data (e.g., image)
            logger.debug("Clipboard contains non-text data")
            return None
        except Exception:
            logger.exception("Unexpected error reading clipboard")
            return None

    async def capture_and_publish(self) -> None:
        """
        Read clipboard and publish TextCaptured event if text exists.

        This is the event handler called when HotkeyPressed(READ) is received.
        """
        text = self.read()
        if text:
            preview = text[:80].replace("\n", " ")
            logger.info(
                "Clipboard captured: %d chars — %s%s",
                len(text),
                preview,
                "..." if len(text) > 80 else "",
            )
            await self._event_bus.publish(TextCaptured(raw_text=text))
        else:
            logger.warning("[yellow]Clipboard empty[/] — no text to capture")

    def cleanup(self) -> None:
        """Destroy the hidden tkinter root window."""
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None
