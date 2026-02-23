from __future__ import annotations

import asyncio
import io
import logging
import threading

from PIL import Image

from src.domain.ocr.config import CANDIDATE_LANGUAGES
from src.domain.ocr.preprocessor import OcrPreprocessor

logger = logging.getLogger(__name__)


class OcrReaderService:

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()
        self._preprocessor = OcrPreprocessor()

    def read(self, image: Image.Image) -> str:
        self._ensure_engine()
        processed = self._preprocessor.process(image)
        return asyncio.run(self._recognize(processed))

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return
        with self._lock:
            if self._engine is not None:
                return
            import winrt.windows.globalization as globalization
            import winrt.windows.media.ocr as ocr
            for tag in CANDIDATE_LANGUAGES:
                lang = globalization.Language(tag)
                engine = ocr.OcrEngine.try_create_from_language(lang)
                if engine is not None:
                    self._engine = engine
                    logger.info("Windows OCR engine ready: %s", tag)
                    return
            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                raise RuntimeError("No Windows OCR language pack available")
            self._engine = engine
            logger.info("Windows OCR engine ready (user profile language)")

    async def _recognize(self, image: Image.Image) -> str:
        import winrt.windows.graphics.imaging as wgi
        import winrt.windows.storage.streams as wss

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        win_stream = wss.InMemoryRandomAccessStream()
        writer = wss.DataWriter(win_stream.get_output_stream_at(0))
        writer.write_bytes(png_bytes)
        await writer.store_async()
        win_stream.seek(0)

        decoder = await wgi.BitmapDecoder.create_async(win_stream)
        soft_bmp = await decoder.get_software_bitmap_converted_async(
            wgi.BitmapPixelFormat.BGRA8,
            wgi.BitmapAlphaMode.PREMULTIPLIED,
        )

        result = await self._engine.recognize_async(soft_bmp)
        return self._extract_text(result)

    def _extract_text(self, result) -> str:
        lines = [
            " ".join(word.text for word in line.words)
            for line in result.lines
        ]
        return " ".join(lines).strip()
