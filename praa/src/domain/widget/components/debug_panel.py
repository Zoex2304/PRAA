import customtkinter as ctk
import psutil
import threading
import os

class CollapsibleItem(ctk.CTkFrame):
    def __init__(self, master, label_text, initial_value="", expanded_provider=None, content_widget_cls=None, content_widget_kwargs=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self._expanded = False
        self._expanded_provider = expanded_provider 
        self._content_widget_cls = content_widget_cls
        self._content_widget = None
        self._content_widget_kwargs = content_widget_kwargs or {}
        
        # Header row
        self._header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self._header.pack(fill="x", padx=4, pady=1)
        
        is_collapsible = (expanded_provider is not None) or (content_widget_cls is not None)

        # Expand/Collapse button (only if collapsible)
        if is_collapsible:
            self._btn = ctk.CTkButton(
                self._header, 
                text="▶", 
                width=20, 
                height=20,
                fg_color="transparent", 
                text_color="#94a3b8",
                hover_color="#1e293b",
                font=ctk.CTkFont(size=10),
                command=self._toggle
            )
            self._btn.pack(side="left", padx=(0, 4))
        else:
             # Spacer to align with collapsible items
            ctk.CTkFrame(self._header, width=20, height=1, fg_color="transparent").pack(side="left", padx=(0, 4))
        
        # Label
        ctk.CTkLabel(
            self._header, 
            text=label_text, 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8"
        ).pack(side="left")
        
        # Value (Summary)
        self._value_label = ctk.CTkLabel(
            self._header, 
            text=initial_value, 
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#e2e8f0"
        )
        self._value_label.pack(side="right", padx=4)
        
        # Content frame (hidden by default)
        if is_collapsible:
            self._content_frame = ctk.CTkFrame(self, fg_color="#020617", corner_radius=4)
            
            if self._content_widget_cls:
                self._content_widget = self._content_widget_cls(self._content_frame, **self._content_widget_kwargs)
                self._content_widget.pack(fill="both", expand=True, padx=4, pady=4)
            else:
                 # Default text label
                self._content_label = ctk.CTkLabel(
                    self._content_frame, 
                    text="", 
                    font=ctk.CTkFont(family="Consolas", size=9),
                    text_color="#cbd5e1",
                    anchor="w",
                    justify="left"
                )
                self._content_label.pack(fill="x", padx=8, pady=4)

    def set_value(self, value):
        self._value_label.configure(text=value)
        
    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._btn.configure(text="▼")
            self._content_frame.pack(fill="x", padx=24, pady=(0, 4))
            self._refresh_content()
        else:
            self._btn.configure(text="▶")
            self._content_frame.pack_forget()
            
    def _refresh_content(self):
        if self._expanded and self._expanded_provider:
             # If using provider, update text label
            if hasattr(self, '_content_label'):
                try:
                    content = self._expanded_provider()
                    self._content_label.configure(text=content)
                except Exception as e:
                    self._content_label.configure(text=f"Error: {e}")

    def update_content(self):
        if self._expanded:
            self._refresh_content()
    
    def get_content_widget(self):
        return self._content_widget


class ChunkListPanel(ctk.CTkScrollableFrame):
    """
    Scrollable list of chunks with detailed status, progress bar, and active highlighting.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, height=180, fg_color="transparent", orientation="vertical", **kwargs)
        self._rows = {} # index -> {frame, name_lbl, status_lbl, progress_bar, time_lbl}
        self.grid_columnconfigure(0, weight=1)
        self._current_highlight_idx = -1

    def update_chunk(self, index: int, status: str, name: str = ""):
        if index not in self._rows:
            self._create_row(index, name, status)
        
        row = self._rows[index]
        
        # Update name if provided
        if name:
            row['name_lbl'].configure(text=name)
            
        # Update status text/color
        color = "#94a3b8" # pending
        text = status
        if status == "processing":
            color = "#f59e0b"
            text = "Synth"
        elif status == "ready":
            color = "#06b6d4"
            text = "Ready"
        elif status == "playing":
            color = "#22c55e"
            text = "Play"
        elif status == "done":
            color = "#64748b"
            text = "Done"
            
        row['status_lbl'].configure(text=text, text_color=color)

        # Show/Hide Progress controls based on status
        if status == "playing":
            row['progress_bar'].grid()
            row['time_lbl'].grid()
            row['frame'].configure(fg_color="#1e293b") # Highlight active row
            if self._current_highlight_idx != index:
                # Clear previous highlight
                 if self._current_highlight_idx in self._rows:
                     self._rows[self._current_highlight_idx]['frame'].configure(fg_color="transparent")
                 self._current_highlight_idx = index
                 
                 # Auto-scroll attempt (rough)
                 try:
                     # CTkScrollableFrame doesn't expose easy 'scroll to widget', 
                     # but we can try to ensure visibility if needed. 
                     # For now, just highlighting is good.
                     pass
                 except: pass
        else:
             # If previously playing but now done/ready, hide progress
            if status != "playing":
                row['progress_bar'].grid_remove()
                row['time_lbl'].grid_remove()
                if self._current_highlight_idx == index and status != "playing":
                    row['frame'].configure(fg_color="transparent")


    def update_progress(self, index: int, current_ms: float, total_ms: float):
        if index in self._rows:
            row = self._rows[index]
            # Update guaranteed even if not visible
            # if row['progress_bar'].winfo_viewable():
            if True:
                progress = 0
                if total_ms > 0:
                    progress = min(1.0, max(0.0, current_ms / total_ms))
                row['progress_bar'].set(progress)
                
                # Update timestamp 00:00 / 00:00
                def fmt(ms):
                    s = int(ms / 1000)
                    m = s // 60
                    s = s % 60
                    return f"{m:02}:{s:02}"
                
                row['time_lbl'].configure(text=f"{fmt(current_ms)} / {fmt(total_ms)}")

    def _create_row(self, index, name, status):
        # Container frame for row
        frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=4)
        frame.grid(row=index, column=0, sticky="ew", padx=2, pady=1)
        frame.grid_columnconfigure(1, weight=1)
        
        # Top line: Index | Name | Status
        lbl_idx = ctk.CTkLabel(frame, text=f"#{index+1}", width=24, font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b")
        lbl_idx.grid(row=0, column=0, padx=(4, 2), pady=2, sticky="w")
        
        lbl_name = ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(size=10), text_color="#cbd5e1", anchor="w")
        lbl_name.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        
        lbl_status = ctk.CTkLabel(frame, text=status, font=ctk.CTkFont(size=9, weight="bold"), width=40)
        lbl_status.grid(row=0, column=2, padx=(2, 4), pady=2, sticky="e")
        
        # Bottom line (progress): Progress Bar | Time
        # Hidden by default
        p_bar = ctk.CTkProgressBar(frame, height=4, progress_color="#22c55e", fg_color="#334155")
        p_bar.grid(row=1, column=0, columnspan=2, padx=(30, 4), pady=(0, 4), sticky="ew")
        p_bar.set(0)
        p_bar.grid_remove()
        
        t_lbl = ctk.CTkLabel(frame, text="00:00 / 00:00", font=ctk.CTkFont(family="Consolas", size=8), text_color="#94a3b8")
        t_lbl.grid(row=1, column=2, padx=4, pady=(0, 4), sticky="e")
        t_lbl.grid_remove()
        
        self._rows[index] = {
            'frame': frame,
            'name_lbl': lbl_name,
            'status_lbl': lbl_status,
            'progress_bar': p_bar,
            'time_lbl': t_lbl
        }

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._rows.clear()
        self._current_highlight_idx = -1


class DebugPanel(ctk.CTkFrame):
    
    def __init__(self, master, initial_chunks=None, initial_statuses=None, **kwargs):
        super().__init__(master, fg_color="#0f172a", corner_radius=0, **kwargs)
        
        self._items = {}
        
        # -- Items --
        # Non-collapsible items
        self._add_item("State", "IDLE")
        
        # Collapsible items
        # Queue is now loaded with any initial chunks provided
        queue_item = self._add_item("Queue", "0", content_widget_cls=ChunkListPanel)
        
        # Pre-populate if we have chunks
        if initial_chunks:
            self._populate_initial_chunks(initial_chunks, initial_statuses)

        self._add_item("Threads", "0", provider=self._get_thread_details)
        self._add_item("Memory", "0 MB", provider=self._get_memory_details)
        self._add_item("Position", "0ms", provider=lambda: "Position details...") 
        
        self._create_log_area()
        
        self._queue_snapshot = [] 

    def _add_item(self, label, value, provider=None, content_widget_cls=None, content_widget_kwargs=None):
        item = CollapsibleItem(
            self, label, value, 
            expanded_provider=provider, 
            content_widget_cls=content_widget_cls,
            content_widget_kwargs=content_widget_kwargs
        )
        item.pack(fill="x", padx=4)
        self._items[label] = item
        return item
        
    def _create_log_area(self):
        # ... (Log area same as before)
        sep = ctk.CTkFrame(self, height=2, fg_color="#334155")
        sep.pack(fill="x", padx=8, pady=(8, 4))
        
        lbl = ctk.CTkLabel(
            self, text="System Activity", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8", anchor="w"
        )
        lbl.pack(fill="x", padx=8, pady=(0, 2))

        # Log Textbox
        self._log_text = ctk.CTkTextbox(
            self,
            height=150,
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color="#e2e8f0",
            fg_color="#020617",
            border_width=0,
            activate_scrollbars=True
        )
        self._log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._log_text.configure(state="disabled") 
        
        try:
             self._log_text._textbox.tag_config("INFO", foreground="#22c55e")
             self._log_text._textbox.tag_config("WARNING", foreground="#f59e0b")
             self._log_text._textbox.tag_config("ERROR", foreground="#ef4444")
             self._log_text._textbox.tag_config("DEBUG", foreground="#64748b")
        except Exception:
             pass

    def get_log_widget(self):
        return self._log_text

    def _populate_initial_chunks(self, chunks, statuses=None):
        """Populate the queue with initial chunks."""
        self.reset_chunks()
        for i, chunk in enumerate(chunks):
            name = chunk.strip().replace("\n", " ")[:30] + ("..." if len(chunk) > 30 else "")
            
            # Use tracked status or default to pending
            status = "pending"
            if statuses and i in statuses:
                status = statuses[i]
                
            self.update_chunk_status(i, status, name)
        
        # Update count
        self._items["Queue"].set_value(str(len(chunks)))


    def update_metrics(
        self, 
        state_text: str, 
        queue_size: int, 
        is_playing: bool,
        position_ms: float,
        current_chunk_idx: int = -1,
        chunk_duration_ms: float = 0,
        queue_snapshot: list[str] = None
    ):
        self._queue_snapshot = queue_snapshot or []
        
        self._items["State"].set_value(state_text)
        
        # Update global items
        # Note: Queue size here is pending items. 
        # Since we show ALL items, maybe we should show "Pending: X" or just keep it simple.
        self._items["Queue"].set_value(str(queue_size))
        
        self._items["Threads"].set_value(str(threading.active_count()))
        self._items["Threads"].update_content()
        
        if psutil:
            try:
                process = psutil.Process(os.getpid())
                mem = process.memory_info().rss / 1024 / 1024
                self._items["Memory"].set_value(f"{mem:.1f} MB")
                self._items["Memory"].update_content()
            except Exception:
                pass
        
        self._items["Position"].set_value(f"{int(position_ms)}ms")
        
        # Update detailed chunk progress
        if current_chunk_idx >= 0 and is_playing:
            queue_item = self._items["Queue"]
            chunk_list = queue_item.get_content_widget()
            if chunk_list and isinstance(chunk_list, ChunkListPanel):
                chunk_list.update_progress(current_chunk_idx, position_ms, chunk_duration_ms)

    def update_chunk_status(self, index: int, status: str, name: str = ""):
        queue_item = self._items["Queue"]
        chunk_list = queue_item.get_content_widget()
        if chunk_list and isinstance(chunk_list, ChunkListPanel):
            chunk_list.update_chunk(index, status, name)

    def reset_chunks(self):
        queue_item = self._items["Queue"]
        chunk_list = queue_item.get_content_widget()
        if chunk_list and isinstance(chunk_list, ChunkListPanel):
            chunk_list.clear()

    # --- Providers handled as before ---
    def _get_thread_details(self):
        threads = threading.enumerate()
        
        # Mapping of known thread names to descriptions
        descriptions = {
            "MainThread": "GUI Main Loop (Tkinter)",
            "audio-consumer": "Audio Playback Queue Consumer",
            "widget-ui": "Widget UI Thread",
            "tray-icon": "System Tray Icon",
            "asyncio_0": "Async Event Loop (0)",
            "asyncio_1": "Async Event Loop (1)",
            "AnyIO worker": "AnyIO Background Worker",
        }

        lines = []
        for t in threads:
            desc = descriptions.get(t.name, "Background Thread")
            # If name is unknown but looks like asyncio/ThreadPool
            if "ThreadPoolExecutor" in t.name:
                desc = "Thread Pool Worker"
            
            lines.append(f"- {t.name}: {desc}")
            
        return "\n".join(lines)

    def _get_memory_details(self):
        if not psutil:
            return "psutil not installed"
        try:
            p = psutil.Process(os.getpid())
            mem = p.memory_info()
            return (
                f"RSS:  {mem.rss / 1024 / 1024:.1f} MB\n"
                f"VMS:  {mem.vms / 1024 / 1024:.1f} MB\n"
                f"Page: {mem.num_page_faults}"
            )
        except Exception as e:
            return str(e)
