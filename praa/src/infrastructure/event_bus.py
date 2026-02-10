"""
PRAA EventBus — Generic Typed Pub/Sub Dispatcher

The backbone of the decoupled architecture. All inter-domain communication
flows through this bus. No domain module calls another directly.

Design decisions:
- Thread-safe via asyncio event loop integration
- Supports both sync and async handlers (auto-wrapped)
- Type-based dispatch: subscribe to an event CLASS, receive instances of it
- Handler isolation: one handler's failure does not block others
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Handler type: either sync (T -> None) or async (T -> Coroutine)
SyncHandler = Callable[[Any], None]
AsyncHandler = Callable[[Any], Coroutine[Any, Any, None]]
Handler = SyncHandler | AsyncHandler


class EventBus:
    """
    Central event dispatcher using typed pub/sub pattern.

    Usage:
        bus = EventBus()
        bus.subscribe(HotkeyPressed, my_handler)
        await bus.publish(HotkeyPressed(action=HotkeyAction.READ))
    """

    def __init__(self) -> None:
        self._subscribers: dict[Type, list[Handler]] = defaultdict(list)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def subscribe(self, event_type: Type[T], handler: Handler) -> None:
        """
        Register a handler for a specific event type.

        Args:
            event_type: The event class to subscribe to.
            handler: Callable that accepts an instance of event_type.
        """
        self._subscribers[event_type].append(handler)
        self._logger.debug(
            "Subscribed %s to %s",
            getattr(handler, "__qualname__", repr(handler)),
            event_type.__name__,
        )

    def unsubscribe(self, event_type: Type[T], handler: Handler) -> None:
        """Remove a handler from an event type's subscriber list."""
        try:
            self._subscribers[event_type].remove(handler)
            self._logger.debug(
                "Unsubscribed %s from %s",
                getattr(handler, "__qualname__", repr(handler)),
                event_type.__name__,
            )
        except ValueError:
            self._logger.warning(
                "Handler %s was not subscribed to %s",
                getattr(handler, "__qualname__", repr(handler)),
                event_type.__name__,
            )

    async def publish(self, event: Any) -> None:
        """
        Dispatch an event to all registered handlers of its type.

        Each handler is invoked independently — one handler's exception
        does not prevent other handlers from executing.

        Args:
            event: An instance of a registered event class.
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        if not handlers:
            self._logger.debug("No subscribers for %s", event_type.__name__)
            return

        self._logger.debug(
            "Publishing %s to %d handler(s)",
            event_type.__name__,
            len(handlers),
        )

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                self._logger.exception(
                    "Handler %s failed for event %s",
                    getattr(handler, "__qualname__", repr(handler)),
                    event_type.__name__,
                )

    def clear(self) -> None:
        """Remove all subscriptions. Used during shutdown or testing."""
        self._subscribers.clear()
        self._logger.debug("All subscriptions cleared")

    @property
    def subscriber_count(self) -> int:
        """Total number of registered handler subscriptions."""
        return sum(len(handlers) for handlers in self._subscribers.values())
