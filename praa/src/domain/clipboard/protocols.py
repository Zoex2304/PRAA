"""
Clipboard Domain — Protocols (Interface Segregation)

Defines the contract for any clipboard reader implementation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IClipboardReader(Protocol):
    """
    Contract for a clipboard reader.

    Implementations must:
    - Read the current system clipboard text content
    - Return None if clipboard is empty or contains non-text data
    - Handle errors gracefully without crashing
    """

    def read(self) -> str | None:
        """
        Read text content from the system clipboard.

        Returns:
            The clipboard text content, or None if empty/non-text.
        """
        ...
