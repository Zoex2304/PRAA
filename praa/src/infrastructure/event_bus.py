from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Handler type: either sync (T -> None) or async (T -> Coroutine)
SyncHandler = Callable[[Any], None]
AsyncHandler = Callable[[Any], Coroutine[Any, Any, None]]
Handler = SyncHandler | AsyncHandler


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Handler]] = defaultdict(list)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def subscribe(self, event_type: type[T], handler: Handler) -> None:
        self._subscribers[event_type].append(handler)
        self._logger.debug(
            "Subscribed %s to %s",
            getattr(handler, "__qualname__", repr(handler)),
            event_type.__name__,
        )

    def unsubscribe(self, event_type: type[T], handler: Handler) -> None:
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
        self._subscribers.clear()
        self._logger.debug("All subscriptions cleared")

    @property
    def subscriber_count(self) -> int:
        return sum(len(handlers) for handlers in self._subscribers.values())
