from __future__ import annotations

import asyncio
import io
import logging
import threading
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

_CANDIDATE_LANGUAGES = ("en-US", "id-ID", "en-GB")
_SCALE_FACTOR = 2
_MIN_DIM_PX = 100
_MAX_DIM_PX = 4096


class OcrReaderService:

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def read(self, image: Image.Image) -> str:
        self._ensure_engine()
        upscaled = self._preprocess(image)
        return asyncio.run(self._recognize(upscaled))

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return
        with self._lock:
            if self._engine is not None:
                return
            import winrt.windows.globalization as globalization
            import winrt.windows.media.ocr as ocr
            for tag in _CANDIDATE_LANGUAGES:
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

    def _preprocess(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        new_w = max(_MIN_DIM_PX, w * _SCALE_FACTOR)
        new_h = max(_MIN_DIM_PX, h * _SCALE_FACTOR)
        if max(new_w, new_h) > _MAX_DIM_PX:
            ratio = _MAX_DIM_PX / max(new_w, new_h)
            new_w = int(new_w * ratio)
            new_h = int(new_h * ratio)
        return image.resize((new_w, new_h), Image.LANCZOS)

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
