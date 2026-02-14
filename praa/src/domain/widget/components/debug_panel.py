import customtkinter as ctk
import psutil
import threading
import os

class DebugPanel(ctk.CTkFrame):
    """
    Collapsible panel showing system internals.
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#0f172a", corner_radius=0, **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Labels
        self._labels = {}
        self._add_row(0, "State:", "IDLE")
        self._add_row(1, "Queue:", "0")
        self._add_row(2, "Player:", "Stopped")
        self._add_row(3, "Threads:", "0")
        self._add_row(4, "Memory:", "0 MB")
        self._add_row(5, "Position:", "0ms")
        
    def _add_row(self, row, label, value):
        ctk.CTkLabel(
            self, text=label, 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8", anchor="w"
        ).grid(row=row, column=0, padx=8, pady=1, sticky="w")
        
        lbl = ctk.CTkLabel(
            self, text=value, 
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#e2e8f0", anchor="e"
        )
        lbl.grid(row=row, column=1, padx=8, pady=1, sticky="e")
        self._labels[label] = lbl
        
    def update_metrics(
        self, 
        state_text: str, 
        queue_size: int, 
        is_playing: bool,
        position_ms: float
    ):
        """Update displayed metrics."""
        self._labels["State:"].configure(text=state_text)
        self._labels["Queue:"].configure(text=str(queue_size))
        self._labels["Player:"].configure(
            text="Playing" if is_playing else "Stopped",
            text_color="#22c55e" if is_playing else "#94a3b8"
        )
        self._labels["Threads:"].configure(text=str(threading.active_count()))
        
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        self._labels["Memory:"].configure(text=f"{mem:.1f} MB")
        
        self._labels["Position:"].configure(text=f"{int(position_ms)}ms")
