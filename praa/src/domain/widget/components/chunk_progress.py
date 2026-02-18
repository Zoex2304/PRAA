import customtkinter as ctk


class ChunkProgressMap(ctk.CTkFrame):
    """Visual map of audio chunks with status text labels."""

    COLOR_PENDING = "#334155"
    COLOR_PROCESSING = "#f59e0b"
    COLOR_READY = "#06b6d4"
    COLOR_PLAYING = "#22c55e"

    STATUS_TEXT = {
        "pending": "",
        "processing": "Synth",
        "ready": "Ready",
        "playing": "\u25b6",
    }

    def __init__(self, master, height=22, **kwargs):
        super().__init__(master, height=height, fg_color="transparent", **kwargs)
        self._chunks: list[ctk.CTkLabel] = []
        self._states: list[str] = []

    def setup(self, total_chunks: int) -> None:
        for widget in self._chunks:
            widget.destroy()
        self._chunks.clear()
        self._states = ["pending"] * total_chunks

        for i in range(total_chunks):
            block = ctk.CTkLabel(
                self,
                text="",
                fg_color=self.COLOR_PENDING,
                text_color="#ffffff",
                font=ctk.CTkFont(size=8, weight="bold"),
                corner_radius=4,
                height=18,
            )
            block.grid(row=0, column=i, padx=1, pady=2, sticky="ew")
            self.grid_columnconfigure(i, weight=1)
            self._chunks.append(block)

    def update_status(self, chunk_idx: int, status: str) -> None:
        if 0 <= chunk_idx < len(self._chunks):
            self._states[chunk_idx] = status

            color = self.COLOR_PENDING
            if status == "processing":
                color = self.COLOR_PROCESSING
            elif status == "ready":
                color = self.COLOR_READY
            elif status == "playing":
                color = self.COLOR_PLAYING

            label = self.STATUS_TEXT.get(status, "")
            self._chunks[chunk_idx].configure(fg_color=color, text=label)

    def reset(self) -> None:
        for widget in self._chunks:
            widget.destroy()
        self._chunks.clear()
        self._states.clear()
