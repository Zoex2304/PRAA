from __future__ import annotations

import logging

import mss
from PIL import Image

from src.domain.ocr.debug_writer import OcrDebugWriter

logger = logging.getLogger(__name__)

_DPI_SCALE: float | None = None


def _detect_dpi_scale() -> float:
    """
    Compute the scale from tkinter logical coordinates to mss physical coordinates.

    Derived by comparing tkinter's reported primary-monitor width against mss's
    always-physical width.  This handles all DPI-awareness modes correctly:

    - DPI-unaware process (compiled .exe without manifest): tkinter returns logical
      pixels; scale > 1.0 converts them to physical for mss.
    - DPI-aware process (Python 3.8+ interpreter): tkinter already returns physical
      pixels; scale = 1.0, no conversion needed.

    The result is cached for the lifetime of the process.
    """
    try:
        import tkinter as _tk
        _root = _tk.Tk()
        _root.withdraw()
        tk_w = _root.winfo_screenwidth()
        _root.destroy()

        with mss.mss() as sct:
            monitors = sct.monitors
            phys_w = monitors[1]["width"] if len(monitors) > 1 else monitors[0]["width"]

        if tk_w <= 0:
            return 1.0

        scale = phys_w / tk_w
        logger.info(
            "[CAPTURE] DPI scale detected: tk_screen_w=%d  mss_phys_w=%d  scale=%.3f",
            tk_w, phys_w, scale,
        )
        return scale
    except Exception:
        logger.exception("[CAPTURE] DPI scale detection failed; defaulting to 1.0")
        return 1.0


def _windows_dpi_scale() -> float:
    global _DPI_SCALE
    if _DPI_SCALE is None:
        _DPI_SCALE = _detect_dpi_scale()
    return _DPI_SCALE


class ScreenCaptureService:

    def __init__(self, debug_writer: OcrDebugWriter) -> None:
        self._debug_writer = debug_writer

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        dpi = _windows_dpi_scale()
        px = int(x * dpi)
        py = int(y * dpi)
        pw = int(width * dpi)
        ph = int(height * dpi)

        logger.debug("[CAPTURE] logical_region=(%d, %d, %d×%d)", x, y, width, height)
        logger.debug("[CAPTURE] physical_region=(%d, %d, %d×%d)", px, py, pw, ph)
        logger.debug("[CAPTURE] dpi_scale_factor=%.2f", dpi)

        with mss.mss() as sct:
            logger.debug("[CAPTURE] mss_monitor_0=%s", sct.monitors[0])
            monitor = {"top": py, "left": px, "width": pw, "height": ph}
            screenshot = sct.grab(monitor)
            image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        logger.debug("[CROP] raw_image_size=%d×%dpx  color_space=RGB", image.width, image.height)
        self._debug_writer.save(image, "01_raw_crop.png")

        return image
