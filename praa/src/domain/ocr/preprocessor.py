from __future__ import annotations

import logging

from PIL import Image, ImageOps

from src.domain.ocr.config import (
    BORDER_PADDING_PX,
    MAX_SCALED_DIM_PX,
    MIN_SCALED_DIM_PX,
    SCALE_FACTOR,
)

logger = logging.getLogger(__name__)


class OcrPreprocessor:
    def process(self, image: Image.Image) -> Image.Image:
        padded = ImageOps.expand(image, border=BORDER_PADDING_PX, fill=(255, 255, 255))
        scaled = self._scale(padded)
        logger.debug(
            "[SCALE] scale_factor=%d  result=%dx%dpx",
            SCALE_FACTOR,
            scaled.width,
            scaled.height,
        )
        return scaled

    def _scale(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        new_w = max(MIN_SCALED_DIM_PX, w * SCALE_FACTOR)
        new_h = max(MIN_SCALED_DIM_PX, h * SCALE_FACTOR)
        if max(new_w, new_h) > MAX_SCALED_DIM_PX:
            ratio = MAX_SCALED_DIM_PX / max(new_w, new_h)
            new_w = int(new_w * ratio)
            new_h = int(new_h * ratio)
        return image.resize((new_w, new_h), Image.LANCZOS)
