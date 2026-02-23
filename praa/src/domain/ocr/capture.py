from __future__ import annotations

import logging

import mss
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCaptureService:

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        logger.debug("Captured region %dx%d at (%d, %d)", width, height, x, y)
        return image
