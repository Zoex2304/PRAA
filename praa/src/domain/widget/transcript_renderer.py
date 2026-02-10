"""
TranscriptRenderer - Thread-Safe Transcript UI Manager

SINGLE RESPONSIBILITY:
- Render transcript text with word-level highlighting
- Manage tag styling (active/spoken/unspoken)
- Guarantee thread-safe UI updates
- Calculate text positions for chunks

GUARANTEES:
- All UI updates via single thread (tk mainloop)
- No race conditions on text widget
- Immutable chunk data
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)

# Theme
TEXT_PRIMARY = "#e2e8f0"
TEXT_DIM = "#94a3b8"
ACCENT_GLOW = "#FFFF00"


@dataclass(frozen=True)
class ChunkData:
    """Immutable chunk text data."""
    index: int
    text: str
    char_offset: int  # Absolute character position in full transcript
    
    @property
    def char_end(self) -> int:
        return self.char_offset + len(self.text)


class TranscriptRenderer:
    """
    Manages transcript display with word-level highlighting.
    
    ARCHITECTURE:
    - Owns the CTkTextbox widget
    - Maintains chunk offset mapping
    - Provides thread-safe update API
    - Encapsulates all tag manipulation
    """
    
    def __init__(self, textbox: ctk.CTkTextbox) -> None:
        """
        Args:
            textbox: The CTkTextbox widget to manage
        """
        self._textbox = textbox
        self._tk_text = textbox._textbox  # Internal tk.Text widget
        
        # Chunk mapping: chunk_idx → ChunkData
        self._chunks: dict[int, ChunkData] = {}
        self._full_text = ""
        
        # Configure tags
        self._configure_tags()
        
    # ----------------------------------------------------------------
    # PUBLIC API: Content Management
    # ----------------------------------------------------------------
    
    def set_content(self, chunks: list[str]) -> None:
        """
        Set transcript content from chunk list.
        
        Thread-safe: Can be called from any thread.
        """
        # Build chunk data with offsets
        chunk_data = []
        offset = 0
        
        for idx, text in enumerate(chunks):
            chunk_data.append(ChunkData(
                index=idx,
                text=text,
                char_offset=offset,
            ))
            # Account for "\n\n" separator
            offset += len(text) + 2
        
        # Update internal state
        self._chunks = {c.index: c for c in chunk_data}
        self._full_text = "\n\n".join(chunks)
        
        # Render to UI
        self._render_text()
        
        logger.info("Transcript loaded: %d chunks, %d chars", len(chunks), len(self._full_text))
    
    def clear_content(self) -> None:
        """Clear all transcript content."""
        self._chunks.clear()
        self._full_text = ""
        self._textbox.delete("1.0", "end")
    
    def highlight_relative(self, chunk_idx: int, start: int, end: int) -> None:
        """
        Highlight a word using relative offsets within a chunk.
        
        Thread-safe: Must be called from UI thread.
        
        Args:
            chunk_idx: Chunk containing the word
            start: Character start position relative to chunk start
            end: Character end position relative to chunk start
        """
        if chunk_idx not in self._chunks:
            logger.warning("Highlight requested for unknown chunk %d", chunk_idx)
            return
        
        chunk = self._chunks[chunk_idx]
        abs_start = chunk.char_offset + start
        abs_end = chunk.char_offset + end
        
        # Convert to Tk indices
        start_idx = f"1.0 + {abs_start} chars"
        end_idx = f"1.0 + {abs_end} chars"
        
        try:
            # Clear previous highlight
            self._tk_text.tag_remove("active", "1.0", "end")
            
            # Apply new highlight
            self._tk_text.tag_add("active", start_idx, end_idx)
            
            # Mark previous words as spoken
            self._tk_text.tag_remove("unspoken", "1.0", start_idx)
            self._tk_text.tag_add("spoken", "1.0", start_idx)
            
            # Auto-scroll to keep word visible
            self._tk_text.see(start_idx)
            
        except Exception:
            logger.exception("Failed to highlight word at chunk %d [%d:%d]", chunk_idx, start, end)
    
    def clear_highlight(self) -> None:
        """Remove all highlighting."""
        try:
            self._tk_text.tag_remove("active", "1.0", "end")
            self._tk_text.tag_remove("spoken", "1.0", "end")
            self._tk_text.tag_add("unspoken", "1.0", "end")
        except Exception:
            logger.exception("Failed to clear highlight")
    
    # ----------------------------------------------------------------
    # QUERY API
    # ----------------------------------------------------------------
    
    def get_text(self) -> str:
        """Get full transcript text."""
        return self._full_text
    
    def get_chunk(self, chunk_idx: int) -> Optional[ChunkData]:
        """Get chunk data by index."""
        return self._chunks.get(chunk_idx)
    
    def get_chunk_offset(self, chunk_idx: int) -> int:
        """Get absolute character offset for chunk."""
        chunk = self._chunks.get(chunk_idx)
        return chunk.char_offset if chunk else 0
    
    @property
    def chunk_count(self) -> int:
        """Number of chunks loaded."""
        return len(self._chunks)
    
    # ----------------------------------------------------------------
    # PRIVATE: Implementation
    # ----------------------------------------------------------------
    
    def _configure_tags(self) -> None:
        """Configure text widget tags for styling."""
        # Active word (currently speaking)
        self._tk_text.tag_config(
            "active",
            foreground=ACCENT_GLOW,
            background="#1e293b",
        )
        
        # Already spoken words
        self._tk_text.tag_config(
            "spoken",
            foreground=TEXT_PRIMARY,
        )
        
        # Not yet spoken words
        self._tk_text.tag_config(
            "unspoken",
            foreground=TEXT_DIM,
        )
        
        # Ensure active tag has highest priority
        self._tk_text.tag_raise("active")
    
    def _render_text(self) -> None:
        """Render full text to widget."""
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", self._full_text)
        
        # Apply default unspoken style
        self._tk_text.tag_add("unspoken", "1.0", "end")
