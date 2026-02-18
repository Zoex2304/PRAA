"""
GUI Logger — Thread-safe Tkinter Logging with Cargo-style Formatting
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import customtkinter as ctk


@dataclass
class LogRecord:
    """Structured log record for display."""
    level: str
    message: str
    timestamp: float
    module: str


class CargoFormatter(logging.Formatter):
    """
    Formatter that mimics Cargo/Rust build output style.
    
    Format:
    [ISOTIME]  ACTION   Message...
    """
    
    # Cargo-like distinct colors/tags aren't directly supported in plain Text widget without tags.
    # We will format the text structure here. The UI component will handle coloring if possible.
    # For a simple CTkTextbox, we rely on text layout.
    
    def format(self, record: logging.LogRecord) -> str:
        # Map log levels/messages to "Cargo-like" verbs where possible?
        # Or just use Level as the verb.
        
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level_name = record.levelname.rjust(7) # Align like "   INFO"
        
        # We can try to parse the message for a "verb" if we want to be fancy,
        # but standard logging is usually "Subject - Predicate".
        # Let's just do:  HH:MM:SS  LEVEL   Message
        
        return f"{timestamp}  {level_name}  {record.getMessage()}"


class TkinterLogHandler(logging.Handler):
    """
    Thread-safe logging handler that queues records for UI consumption.
    """
    
    def __init__(self, max_records: int = 1000) -> None:
        super().__init__()
        self._queue: queue.Queue[str] = queue.Queue()
        self._max_records = max_records
        self.setFormatter(CargoFormatter())
        
    def emit(self, record: logging.LogRecord) -> None:
        """Format and enqueue the record."""
        try:
            msg = self.format(record)
            self._queue.put(msg)
        except Exception:
            self.handleError(record)
            
    def poll(self, widget: ctk.CTkTextbox) -> None:
        """
        Poll the queue and update the widget.
        Must be called from the main UI thread (e.g., via .after()).
        """
        while not self._queue.empty():
            try:
                msg = self._queue.get_nowait()
                
                # Auto-scroll logic
                widget.configure(state="normal")
                
                # Insert text
                # Simple cargo coloring simulation using basic tags if CTk supports it (it doesn't fully support tags like standard Tk).
                # Start with just text.
                widget.insert("end", msg + "\n")
                
                # Keep buffer size in check (expensive in Tkinter, maybe just clear if too huge)
                # For now, let it grow slightly or simplistic truncation
                # widget.delete("1.0", "end-1000l") # Keep last 1000 lines?
                
                widget.see("end")
                widget.configure(state="disabled")
            except queue.Empty:
                break
