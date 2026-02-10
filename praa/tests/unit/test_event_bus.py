"""
Unit Tests — EventBus

Validates the core pub/sub infrastructure that all domain
communication depends on.
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import HotkeyPressed, HotkeyAction, TextCaptured


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_and_publish(event_bus):
    """Events should be delivered to subscribed handlers."""
    received = []

    async def handler(event: HotkeyPressed):
        received.append(event)

    event_bus.subscribe(HotkeyPressed, handler)
    await event_bus.publish(HotkeyPressed(action=HotkeyAction.READ))

    assert len(received) == 1
    assert received[0].action == HotkeyAction.READ


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus):
    """Multiple handlers for the same event should all be called."""
    results = []

    async def handler_a(event):
        results.append("a")

    async def handler_b(event):
        results.append("b")

    event_bus.subscribe(HotkeyPressed, handler_a)
    event_bus.subscribe(HotkeyPressed, handler_b)
    await event_bus.publish(HotkeyPressed(action=HotkeyAction.READ))

    assert sorted(results) == ["a", "b"]


@pytest.mark.asyncio
async def test_type_isolation(event_bus):
    """Handlers should only receive events of their subscribed type."""
    received_hotkey = []
    received_text = []

    async def hotkey_handler(event):
        received_hotkey.append(event)

    async def text_handler(event):
        received_text.append(event)

    event_bus.subscribe(HotkeyPressed, hotkey_handler)
    event_bus.subscribe(TextCaptured, text_handler)

    await event_bus.publish(HotkeyPressed(action=HotkeyAction.STOP))

    assert len(received_hotkey) == 1
    assert len(received_text) == 0


@pytest.mark.asyncio
async def test_sync_handler(event_bus):
    """Sync (non-async) handlers should also work."""
    received = []

    def sync_handler(event):
        received.append(event)

    event_bus.subscribe(HotkeyPressed, sync_handler)
    await event_bus.publish(HotkeyPressed(action=HotkeyAction.READ))

    assert len(received) == 1


@pytest.mark.asyncio
async def test_handler_isolation(event_bus):
    """One handler's exception should not prevent others from executing."""
    results = []

    async def failing_handler(event):
        raise RuntimeError("Test error")

    async def working_handler(event):
        results.append("ok")

    event_bus.subscribe(HotkeyPressed, failing_handler)
    event_bus.subscribe(HotkeyPressed, working_handler)
    await event_bus.publish(HotkeyPressed(action=HotkeyAction.READ))

    assert results == ["ok"]


@pytest.mark.asyncio
async def test_unsubscribe(event_bus):
    """Unsubscribed handlers should no longer receive events."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe(HotkeyPressed, handler)
    event_bus.unsubscribe(HotkeyPressed, handler)
    await event_bus.publish(HotkeyPressed(action=HotkeyAction.READ))

    assert len(received) == 0


@pytest.mark.asyncio
async def test_clear(event_bus):
    """Clear should remove all subscriptions."""
    async def handler(event):
        pass

    event_bus.subscribe(HotkeyPressed, handler)
    event_bus.subscribe(TextCaptured, handler)
    assert event_bus.subscriber_count == 2

    event_bus.clear()
    assert event_bus.subscriber_count == 0


@pytest.mark.asyncio
async def test_no_subscribers(event_bus):
    """Publishing with no subscribers should not raise."""
    await event_bus.publish(HotkeyPressed(action=HotkeyAction.READ))
    # Should complete without error
