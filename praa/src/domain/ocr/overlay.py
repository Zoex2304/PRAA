from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable

from src.domain.ocr.config import (
    OVERLAY_BACKGROUND_COLOR,
    OVERLAY_MIN_DRAG_PX,
    OVERLAY_OPACITY,
    OVERLAY_SELECTION_COLOR,
    OVERLAY_SELECTION_LINE_WIDTH,
    OVERLAY_TRANSPARENT_COLOR,
)

logger = logging.getLogger(__name__)

Region = tuple[int, int, int, int]
RegionCallback = Callable[[Region | None], None]


class OverlayController:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None

    def show(self, on_region_selected: RegionCallback) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_overlay,
            args=(on_region_selected,),
            name="ocr-overlay",
            daemon=True,
        )
        self._thread.start()

    def _run_overlay(self, callback: RegionCallback) -> None:
        try:
            root = tk.Tk()
            _OverlayWindow(root, callback)
            root.mainloop()
        except Exception:
            logger.exception("Overlay error")
            callback(None)


class _OverlayWindow:
    def __init__(self, root: tk.Tk, callback: RegionCallback) -> None:
        self._root = root
        self._callback = callback
        self._start_x = 0
        self._start_y = 0
        self._rect_id: int | None = None

        self._setup_window()
        self._setup_canvas()
        self._bind_events()

    def _setup_window(self) -> None:
        self._root.attributes("-fullscreen", True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", OVERLAY_OPACITY)
        self._root.attributes("-transparentcolor", OVERLAY_TRANSPARENT_COLOR)
        self._root.overrideredirect(True)
        self._root.configure(cursor="crosshair", bg=OVERLAY_BACKGROUND_COLOR)
        self._root.focus_force()

    def _setup_canvas(self) -> None:
        self._canvas = tk.Canvas(
            self._root,
            bg=OVERLAY_BACKGROUND_COLOR,
            cursor="crosshair",
            highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

    def _bind_events(self) -> None:
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._root.bind("<Escape>", self._on_cancel)

    def _on_press(self, event: tk.Event) -> None:
        self._start_x = event.x_root
        self._start_y = event.y_root
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event: tk.Event) -> None:
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)

        rx = self._root.winfo_rootx()
        ry = self._root.winfo_rooty()
        x0 = self._start_x - rx
        y0 = self._start_y - ry
        x1 = event.x_root - rx
        y1 = event.y_root - ry

        self._rect_id = self._canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline=OVERLAY_SELECTION_COLOR,
            width=OVERLAY_SELECTION_LINE_WIDTH,
            fill=OVERLAY_TRANSPARENT_COLOR,
        )

    def _on_release(self, event: tk.Event) -> None:
        x = min(self._start_x, event.x_root)
        y = min(self._start_y, event.y_root)
        w = abs(event.x_root - self._start_x)
        h = abs(event.y_root - self._start_y)

        self._root.destroy()

        if w >= OVERLAY_MIN_DRAG_PX and h >= OVERLAY_MIN_DRAG_PX:
            logger.debug("Region selected: (%d, %d, %dx%d)", x, y, w, h)
            self._callback((x, y, w, h))
        else:
            logger.debug("Drag too small — treated as cancel")
            self._callback(None)

    def _on_cancel(self, _event: tk.Event) -> None:
        self._root.destroy()
        logger.debug("OCR overlay cancelled via Escape")
        self._callback(None)
