import customtkinter as ctk
import psutil
import threading
import os

class DebugPanel(ctk.CTkFrame):
    """
    Collapsible panel showing system internals and logs.
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
        
        self._create_log_area()
        
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
        
    def _create_log_area(self):
        """Create log output area."""
        # Separator
        sep = ctk.CTkFrame(self, height=2, fg_color="#334155")
        sep.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        
        lbl = ctk.CTkLabel(
            self, text="System Activity", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8", anchor="w"
        )
        lbl.grid(row=7, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 2))

        # Log Textbox
        self._log_text = ctk.CTkTextbox(
            self,
            height=200,
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color="#e2e8f0",
            fg_color="#020617",
            border_width=0,
            activate_scrollbars=True
        )
        self._log_text.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=8, pady=(0, 8))
        self._log_text.configure(state="disabled") # readonly by default
        
        # Configure tags for basic coloring
        try:
             # Access underlying tkinter widget for tag configuration
             self._log_text._textbox.tag_config("INFO", foreground="#22c55e")
             self._log_text._textbox.tag_config("WARNING", foreground="#f59e0b")
             self._log_text._textbox.tag_config("ERROR", foreground="#ef4444")
             self._log_text._textbox.tag_config("DEBUG", foreground="#64748b")
        except Exception:
             pass

    def get_log_widget(self):
        """Return the log textbox widget."""
        return self._log_text

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
        
        if psutil:
            try:
                process = psutil.Process(os.getpid())
                mem = process.memory_info().rss / 1024 / 1024
                self._labels["Memory:"].configure(text=f"{mem:.1f} MB")
            except Exception:
                pass
        
        self._labels["Position:"].configure(text=f"{int(position_ms)}ms")
