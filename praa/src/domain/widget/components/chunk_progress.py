import customtkinter as ctk

class ChunkProgressMap(ctk.CTkFrame):
    """
    Visual map of audio chunks.
    
    Displays a row of blocks representing each text chunk.
    Colors indicate state:
    - Grey: Pending
    - Orange: Synthesizing (Processing)
    - Cyan: Ready (Synthesized)
    - Green: Playing
    """
    
    COLOR_PENDING = "#334155"
    COLOR_PROCESSING = "#f59e0b"
    COLOR_READY = "#06b6d4"
    COLOR_PLAYING = "#22c55e"
    
    def __init__(self, master, height=24, **kwargs):
        super().__init__(master, height=height, fg_color="transparent", **kwargs)
        self._chunks: list[ctk.CTkLabel] = []
        self._states: list[str] = []
        
    def setup(self, total_chunks: int) -> None:
        """Initialize the map with total chunks."""
        # Clear existing
        for widget in self._chunks:
            widget.destroy()
        self._chunks.clear()
        self._states = ["pending"] * total_chunks
        
        # Create new blocks
        for i in range(total_chunks):
            # Create a frame/label for the block
            # Weighted width using pack/grid? 
            # Grid is better for equal sizing
            block = ctk.CTkLabel(
                self, 
                text="", 
                fg_color=self.COLOR_PENDING,
                corner_radius=2,
                height=16
            )
            block.grid(row=0, column=i, padx=1, pady=2, sticky="ew")
            self.grid_columnconfigure(i, weight=1)
            self._chunks.append(block)
            
    def update_status(self, chunk_idx: int, status: str) -> None:
        """
        Update status of a specific chunk.
        status: 'pending', 'processing', 'ready', 'playing'
        """
        if 0 <= chunk_idx < len(self._chunks):
            self._states[chunk_idx] = status
            color = self.COLOR_PENDING
            
            if status == "processing":
                color = self.COLOR_PROCESSING
            elif status == "ready":
                color = self.COLOR_READY
            elif status == "playing":
                color = self.COLOR_PLAYING
                
            self._chunks[chunk_idx].configure(fg_color=color)
            
    def reset(self) -> None:
        """Clear the map."""
        for widget in self._chunks:
            widget.destroy()
        self._chunks.clear()
        self._states.clear()
