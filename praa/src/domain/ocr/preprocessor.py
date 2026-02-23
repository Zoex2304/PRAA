from __future__ import annotations

from PIL import Image, ImageOps, ImageStat

from src.domain.ocr.config import (
    BORDER_PADDING_PX,
    DARK_MEAN_THRESHOLD,
    MAX_SCALED_DIM_PX,
    MIN_SCALED_DIM_PX,
    SCALE_FACTOR,
)


class OcrPreprocessor:

    def process(self, image: Image.Image) -> Image.Image:
        gray = image.convert("L")
        normalized = self._normalize_polarity(gray)
        contrasted = ImageOps.autocontrast(normalized, cutoff=0)
        padded = ImageOps.expand(contrasted, border=BORDER_PADDING_PX, fill=255)
        upscaled = self._scale(padded)
        return upscaled.convert("RGB")

    def _normalize_polarity(self, image: Image.Image) -> Image.Image:
        mean = ImageStat.Stat(image).mean[0]
        if mean < DARK_MEAN_THRESHOLD:
            return ImageOps.invert(image)
        return image

    def _scale(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        new_w = max(MIN_SCALED_DIM_PX, w * SCALE_FACTOR)
        new_h = max(MIN_SCALED_DIM_PX, h * SCALE_FACTOR)
        if max(new_w, new_h) > MAX_SCALED_DIM_PX:
            ratio = MAX_SCALED_DIM_PX / max(new_w, new_h)
            new_w = int(new_w * ratio)
            new_h = int(new_h * ratio)
        return image.resize((new_w, new_h), Image.LANCZOS)
