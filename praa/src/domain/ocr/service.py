from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.domain.ocr.capture import ScreenCaptureService
from src.domain.ocr.overlay import OverlayController, Region
from src.domain.ocr.reader import OcrReaderService
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    OcrCaptureFailed,
    OcrCaptureRequested,
    OcrRegionSelected,
    OcrTextExtracted,
)

logger = logging.getLogger(__name__)

_CAPTURE_DELAY_S = 0.3


class OcrService:

    def __init__(
        self,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        capture_service: ScreenCaptureService,
        overlay: OverlayController,
        reader_service: OcrReaderService,
    ) -> None:
        self._event_bus = event_bus
        self._loop = loop
        self._capture = capture_service
        self._overlay = overlay
        self._reader = reader_service

    async def handle_ocr_requested(self, event: OcrCaptureRequested) -> None:
        logger.info("OCR capture requested — showing overlay")
        self._overlay.show(self._on_region_selected)

    def _on_region_selected(self, region: Optional[Region]) -> None:
        if region is None:
            logger.info("OCR overlay cancelled or drag too small")
            asyncio.run_coroutine_threadsafe(
                self._event_bus.publish(OcrCaptureFailed(reason="cancelled")),
                self._loop,
            )
            return

        x, y, w, h = region
        asyncio.run_coroutine_threadsafe(
            self._event_bus.publish(OcrRegionSelected(x=x, y=y, width=w, height=h)),
            self._loop,
        )
        asyncio.run_coroutine_threadsafe(
            self._process_region(region),
            self._loop,
        )

    async def _process_region(self, region: Region) -> None:
        x, y, w, h = region

        await asyncio.sleep(_CAPTURE_DELAY_S)

        logger.info("OCR: capturing region (%d, %d, %d×%d)", x, y, w, h)
        try:
            image = self._capture.capture_region(x, y, w, h)
        except Exception:
            logger.exception("OCR screen capture failed")
            await self._event_bus.publish(OcrCaptureFailed(reason="error"))
            return

        logger.info("OCR: running text extraction...")
        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(None, self._reader.read, image)
        except Exception:
            logger.exception("OCR text extraction failed")
            await self._event_bus.publish(OcrCaptureFailed(reason="error"))
            return

        if not text:
            logger.info("OCR returned no text for the selected region")
            await self._event_bus.publish(OcrCaptureFailed(reason="empty"))
            return

        logger.info("OCR extracted %d chars", len(text))
        await self._event_bus.publish(OcrTextExtracted(text=text))
