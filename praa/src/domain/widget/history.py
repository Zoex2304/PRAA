"""Widget session history management."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import customtkinter as ctk

from .theme import ACCENT
from src.infrastructure.events import TextCaptured

if TYPE_CHECKING:
    from .service import WidgetService

logger = logging.getLogger(__name__)


class HistoryPanel(ctk.CTkFrame):
    """Inline history list."""
    def __init__(self, master, widget: WidgetService, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._widget = widget
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=30)
        header.pack(fill="x", padx=4, pady=4)
        
        ctk.CTkLabel(
            header, text="Recent Sessions",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8"
        ).pack(side="left", padx=4)
        
        # Refresh button
        ctk.CTkButton(
            header, text="↻", width=24, height=24,
            font=ctk.CTkFont(size=12),
            fg_color="transparent", hover_color="#1e293b",
            text_color="#94a3b8",
            command=self.refresh
        ).pack(side="right", padx=4)

        # Scrollable list
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="#0f172a", corner_radius=4,
            height=200 # Fixed height constraint for inline
        )
        self._scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        
        self.refresh()

    def refresh(self):
        # Clear existing
        for w in self._scroll.winfo_children():
            w.destroy()
            
        sessions = self._widget._session_service.get_recent_sessions()
        if not sessions:
            ctk.CTkLabel(
                self._scroll, text="No history found",
                text_color="#64748b", font=ctk.CTkFont(size=11)
            ).pack(pady=20)
            return

        for sess in sessions:
            card = ctk.CTkFrame(self._scroll, fg_color="#1e293b")
            card.pack(fill="x", pady=2)

            # Timestamp parsing fallback
            try:
                ts = sess.timestamp.replace("T", " ")[:16] # YYYY-MM-DD HH:mm
            except Exception:
                ts = str(sess.timestamp)

            # Top row: Date + Load button
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=6, pady=(4, 0))
            
            ctk.CTkLabel(
                top, text=ts,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=ACCENT
            ).pack(side="left")

            ctk.CTkButton(
                top, text="Load", width=40, height=18,
                font=ctk.CTkFont(size=9),
                fg_color="#334155", hover_color=ACCENT,
                command=lambda s=sess: self._load(s)
            ).pack(side="right")

            # Preview text
            preview = sess.text_content[:60].replace("\n", " ") + "..."
            ctk.CTkLabel(
                card, text=preview,
                font=ctk.CTkFont(size=10),
                text_color="#cbd5e1",
                anchor="w", justify="left"
            ).pack(fill="x", padx=6, pady=(2, 6))

    def _load(self, session):
        logger.info("Loading session: %s", session.id)
        # Restore text
        self._widget._transcript_text = session.text_content
        self._widget._publish_event(TextCaptured(raw_text=session.text_content))
        # Hide history panel after loading (optional, but good UX)
        if hasattr(self._widget, '_toggle_history'):
            self._widget._toggle_history()


class HistoryManager:
    """Session history persistence."""

    # We no longer use toggle_history here to control UI directly.
    # The WidgetService controls the UI state via HistoryPanel.
    # This class now mostly handles saving logic.

    @staticmethod
    def toggle_history(widget: WidgetService) -> None:
        # Legacy/helper if needed, but WidgetService should handle it
        pass

    @staticmethod
    def save_current_session(widget: WidgetService) -> None:
        if not widget._transcript_text:
            return

        current_time = time.time()
        if hasattr(widget, '_last_save_time'):
            time_diff = current_time - widget._last_save_time
            if time_diff < 5.0 and widget._transcript_text == getattr(widget, '_last_save_text', ""):
                logger.info("Skipping duplicate session save (diff=%.2fs)", time_diff)
                return

        try:
            boundaries = {}
            if widget._sync_controller:
                for i in range(widget._total_chunks):
                    if widget._sync_controller.has_boundaries(i):
                        boundaries[i] = []

            widget._session_service.save_session(
                text=widget._transcript_text,
                audio_paths=list(widget._audio_paths),
                word_boundaries=boundaries,
                config=widget._config.model_dump(),
            )

            widget._last_save_time = current_time
            widget._last_save_text = widget._transcript_text
            logger.info("Session saved to history")
        except Exception:
            logger.exception("Failed to save session")
