from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from src.domain.upload.extractor import FileTextExtractor
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import (
    FileTextReady,
    FileUploadFailed,
    FileUploadRequested,
    TextCaptured,
)

logger = logging.getLogger(__name__)


class UploadService:
    def __init__(
        self,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop,
        ocr_reader=None,
    ) -> None:
        self._event_bus = event_bus
        self._loop = loop
        self._ocr_reader = ocr_reader
        self._extractor = FileTextExtractor()

    async def handle_file_upload_requested(self, event: FileUploadRequested) -> None:
        path = event.source_path
        if not path.exists():
            await self._event_bus.publish(
                FileUploadFailed(source_path=path, reason="not_found")
            )
            return

        file_size = path.stat().st_size
        loop = asyncio.get_running_loop()

        if self._extractor.is_image(path):
            await self._handle_image(path, file_size, loop)
        else:
            await self._handle_document(path, file_size, loop)

    async def _handle_document(
        self, path: Path, file_size: int, loop: asyncio.AbstractEventLoop
    ) -> None:
        try:
            text = await loop.run_in_executor(None, self._extractor.extract_text, path)
        except Exception:
            logger.exception("Text extraction failed: %s", path)
            await self._event_bus.publish(
                FileUploadFailed(source_path=path, reason="extract_error")
            )
            return

        word_count = len(text.split()) if text else 0
        await self._event_bus.publish(
            FileTextReady(
                source_path=path,
                text=text,
                file_size_bytes=file_size,
                word_count=word_count,
                is_image=False,
            )
        )

        if text.strip():
            await self._event_bus.publish(
                TextCaptured(raw_text=text, source_type="FILE_UPLOAD")
            )
        else:
            await self._event_bus.publish(
                FileUploadFailed(source_path=path, reason="empty")
            )

    async def _handle_image(
        self, path: Path, file_size: int, loop: asyncio.AbstractEventLoop
    ) -> None:
        if self._ocr_reader is None:
            await self._event_bus.publish(
                FileUploadFailed(source_path=path, reason="no_ocr")
            )
            return

        try:
            from PIL import Image

            image = await loop.run_in_executor(
                None, lambda: Image.open(str(path)).convert("RGB")
            )
            text = await loop.run_in_executor(None, self._ocr_reader.read, image)
        except Exception:
            logger.exception("OCR failed for image: %s", path)
            await self._event_bus.publish(
                FileUploadFailed(source_path=path, reason="ocr_error")
            )
            return

        word_count = len(text.split()) if text else 0
        await self._event_bus.publish(
            FileTextReady(
                source_path=path,
                text=text,
                file_size_bytes=file_size,
                word_count=word_count,
                is_image=True,
            )
        )

        if text.strip():
            await self._event_bus.publish(
                TextCaptured(raw_text=text, source_type="FILE_UPLOAD")
            )
        else:
            await self._event_bus.publish(
                FileUploadFailed(source_path=path, reason="empty")
            )
