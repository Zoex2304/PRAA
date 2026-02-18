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


class HistoryManager:
    """Session history display and persistence."""

    @staticmethod
    def toggle_history(widget: WidgetService) -> None:
        HistoryManager.show_history_menu(widget)

    @staticmethod
    def show_history_menu(widget: WidgetService) -> None:
        sessions = widget._session_service.get_recent_sessions()
        if not sessions:
            logger.info("No history found")
            return

        popup = ctk.CTkToplevel(widget._root)
        popup.title("History")
        popup.geometry("400x300")
        popup.attributes("-topmost", True)

        ctk.CTkLabel(
            popup, text="Recent Sessions",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=10)

        scroll = ctk.CTkScrollableFrame(popup)
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        for sess in sessions:
            card = ctk.CTkFrame(scroll, fg_color="#1e293b")
            card.pack(fill="x", pady=2)

            ts = sess.timestamp.replace("T", " ")
            ctk.CTkLabel(
                card, text=ts,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=ACCENT
            ).pack(anchor="w", padx=8, pady=(4, 0))

            preview = sess.text_content[:50].replace("\n", " ") + "..."
            ctk.CTkLabel(
                card, text=preview,
                font=ctk.CTkFont(size=11),
                text_color="#cbd5e1",
                anchor="w"
            ).pack(anchor="w", padx=8, pady=(0, 4))

            def load_session(s=sess, p=popup):
                HistoryManager._load_session_from_history(widget, s)
                p.destroy()

            ctk.CTkButton(
                card, text="Load", width=60, height=20,
                font=ctk.CTkFont(size=10),
                fg_color="#334155", hover_color=ACCENT,
                command=load_session
            ).pack(anchor="e", padx=8, pady=(0, 4))

    @staticmethod
    def _load_session_from_history(widget: WidgetService, session) -> None:
        logger.info("Loading session: %d", session.id)
        widget._transcript_text = session.text_content
        widget._publish_event(TextCaptured(raw_text=session.text_content))

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
