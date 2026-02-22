from __future__ import annotations

from typing import Callable, Optional

import flet as ft
import flet.canvas as cv

from src.domain.config.theme_config import ThemeConfig

_HEIGHT = 6

_STATUS_COLORS: dict[str, str] = {
    "pending":    "#1e293b",
    "processing": "#78350f",
    "ready":      "#164e63",
    "playing":    "#14532d",
    "done":       "#334155",
}


class ChunkTimelineComponent(ft.Container):
    """YouTube-style multi-state chunk progress bar.

    Each chunk is a colored segment:
      pending   → dark slate
      processing → amber-dark
      ready     → cyan-dark
      playing   → green-dark (with a white playhead)
      done      → gray

    Clicking a ready/done/playing segment seeks to its start.
    Clicking pending/processing is silently blocked.

    The playhead (thin white bar) reflects position within the playing chunk.
    Within-chunk sub-sample scrubbing requires soundfile-based seeking
    in the audio player (not yet implemented); clicking returns to chunk start.
    """

    def __init__(
        self,
        theme: ThemeConfig,
        on_seek_chunk: Optional[Callable[[int], None]] = None,
        on_seek_position: Optional[Callable[[int, float], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._theme = theme
        self._on_seek_chunk = on_seek_chunk
        self._on_seek_position = on_seek_position
        self._n_chunks = 0
        self._statuses: dict[int, str] = {}
        self._playing_chunk = -1
        self._playhead_frac = 0.0
        self._draw_width = theme.dimensions.widget_width - 32

        self._canvas = cv.Canvas(
            shapes=[],
            width=self._draw_width,
            height=_HEIGHT,
        )
        self.content = ft.GestureDetector(
            content=self._canvas,
            on_tap_down=self._handle_tap,
            on_pan_update=self._handle_drag,
        )
        self.height = _HEIGHT
        self.border_radius = 4
        self.clip_behavior = ft.ClipBehavior.ANTI_ALIAS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self, n_chunks: int) -> None:
        self._n_chunks = n_chunks
        self._statuses = {i: "pending" for i in range(n_chunks)}
        self._playing_chunk = -1
        self._playhead_frac = 0.0
        self._redraw()

    def update_chunk_status(self, index: int, status: str) -> None:
        self._statuses[index] = status
        if status == "playing":
            self._playing_chunk = index
        self._redraw()

    def update_playback(self, chunk_idx: int, pos_ms: float, dur_ms: float) -> None:
        self._playing_chunk = chunk_idx
        self._playhead_frac = (pos_ms / dur_ms) if dur_ms > 0 else 0.0
        self._redraw()

    def reset(self) -> None:
        self._n_chunks = 0
        self._statuses.clear()
        self._playing_chunk = -1
        self._playhead_frac = 0.0
        self._canvas.shapes = []
        self._safe_update(self._canvas)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        if self._n_chunks == 0:
            self._canvas.shapes = []
            self._safe_update(self._canvas)
            return

        shapes: list[cv.Shape] = []
        w = self._draw_width
        h = _HEIGHT
        gap = 2
        seg_w = max(4.0, (w - gap * (self._n_chunks - 1)) / self._n_chunks)

        for i in range(self._n_chunks):
            x = i * (seg_w + gap)
            color = _STATUS_COLORS.get(self._statuses.get(i, "pending"), _STATUS_COLORS["pending"])
            shapes.append(cv.Rect(
                x=x, y=2,
                width=seg_w, height=h - 4,
                paint=ft.Paint(color=color, style=ft.PaintingStyle.FILL),
            ))
            # Playhead within the playing chunk (2px white rect, no circle cap)
            if i == self._playing_chunk:
                px = x + seg_w * max(0.0, min(1.0, self._playhead_frac))
                shapes.append(cv.Rect(
                    x=px - 1, y=0,
                    width=2, height=h,
                    paint=ft.Paint(color="#ffffff", style=ft.PaintingStyle.FILL),
                ))

        self._canvas.shapes = shapes
        self._safe_update(self._canvas)

    def _handle_tap(self, e: ft.TapEvent) -> None:
        if self._n_chunks == 0 or not self._on_seek_chunk:
            return
        gap = 2
        seg_w = max(4.0, (self._draw_width - gap * (self._n_chunks - 1)) / self._n_chunks)
        chunk_idx = int(e.local_position.x / (seg_w + gap))
        chunk_idx = max(0, min(self._n_chunks - 1, chunk_idx))
        status = self._statuses.get(chunk_idx, "pending")
        if status in ("ready", "done", "playing"):
            self._on_seek_chunk(chunk_idx)

    def _handle_drag(self, e: ft.DragUpdateEvent) -> None:
        if self._n_chunks == 0:
            return
        gap = 2
        seg_w = max(4.0, (self._draw_width - gap * (self._n_chunks - 1)) / self._n_chunks)
        chunk_idx = int(e.local_position.x / (seg_w + gap))
        chunk_idx = max(0, min(self._n_chunks - 1, chunk_idx))
        status = self._statuses.get(chunk_idx, "pending")
        if status not in ("ready", "done", "playing"):
            return
        if chunk_idx == self._playing_chunk and self._on_seek_position:
            x_in_seg = e.local_position.x - chunk_idx * (seg_w + gap)
            frac = max(0.0, min(1.0, x_in_seg / seg_w))
            self._on_seek_position(chunk_idx, frac)
        elif self._on_seek_chunk:
            self._on_seek_chunk(chunk_idx)

    def _safe_update(self, control) -> None:
        try:
            control.update()
        except Exception:
            pass
