"""
Integration Test — Full Processing Pipeline

Tests the end-to-end flow: raw text → cleaner → detector → chunker → TextProcessed event.
TTS is not tested here (requires network). This validates the event-driven pipeline wiring.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.domain.config.models import AppConfig
from src.domain.processor.service import ProcessorService
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import TextCaptured, TextProcessed


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    return AppConfig()


@pytest.fixture
def processor(config, event_bus):
    return ProcessorService(config, event_bus)


@pytest.mark.asyncio
async def test_full_pipeline_indonesian(processor, event_bus):
    """Indonesian text should flow through the full pipeline correctly."""
    results = []

    async def capture_result(event: TextProcessed):
        results.append(event)

    event_bus.subscribe(TextProcessed, capture_result)

    await processor.handle_text_captured(
        TextCaptured(raw_text="Selamat pagi, apa kabar hari ini? Saya baik-baik saja.")
    )

    assert len(results) == 1
    event = results[0]
    assert len(event.chunks) >= 1
    assert event.voice_id in ("id-ID-ArdiNeural", "id-ID-GadisNeural")
    assert event.speed_rate == 1.0


@pytest.mark.asyncio
async def test_pipeline_cleans_urls(processor, event_bus):
    """URLs should be stripped before chunking."""
    results = []

    async def capture_result(event: TextProcessed):
        results.append(event)

    event_bus.subscribe(TextProcessed, capture_result)

    await processor.handle_text_captured(
        TextCaptured(
            raw_text="Visit https://example.com for more info about this topic"
        )
    )

    assert len(results) == 1
    combined = " ".join(results[0].chunks)
    assert "https" not in combined
    assert "example.com" not in combined


@pytest.mark.asyncio
async def test_pipeline_empty_after_cleaning(processor, event_bus):
    """If text is empty after cleaning, no TextProcessed should be published."""
    results = []

    async def capture_result(event: TextProcessed):
        results.append(event)

    event_bus.subscribe(TextProcessed, capture_result)

    # Only a URL — should be empty after cleaning
    await processor.handle_text_captured(TextCaptured(raw_text="https://example.com"))

    assert len(results) == 0
