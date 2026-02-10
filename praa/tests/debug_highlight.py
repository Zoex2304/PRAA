import sys
import os
import asyncio
import logging
import threading
import time
from unittest.mock import MagicMock
import customtkinter as ctk

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.domain.widget.service import WidgetService
from src.domain.config.models import AppConfig
from src.infrastructure.event_bus import EventBus
from src.domain.session.service import SessionService

# Mock Logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("DebugHighlight")

# Mock Event Bus
event_bus = EventBus()

# Mock Session Service
session_service = MagicMock(spec=SessionService)
session_service.get_last_session.return_value = None

# Config
config = AppConfig()

# Text and Boundaries
TEXT = "Halo dunia ini adalah tes highlight yang sangat presisi."

BOUNDARIES = [
    (0.5, 0.5, "Halo", 0, 4),
    (1.1, 0.5, "dunia", 5, 5),
    (1.7, 0.5, "ini", 11, 3),
    (2.3, 0.5, "adalah", 15, 6),
    (2.9, 0.5, "tes", 22, 3),
    (3.5, 0.5, "highlight", 26, 9),
    (4.1, 0.5, "yang", 36, 4),
    (4.7, 0.5, "sangat", 41, 6),
    (5.3, 0.5, "presisi.", 48, 8),
]

def setup_simulation(widget):
    print("Setting up simulation...")
    # Inject data
    widget._transcript_text = TEXT
    widget._transcript_chunks = [TEXT]
    widget._word_boundaries[0] = BOUNDARIES
    
    # Show text
    widget._set_transcript(TEXT)
    widget.show()
    
    # Start sync simulation
    print("Starting sync...")
    widget._start_lyrics_sync(0)

def main():
    # Get current loop
    loop = asyncio.get_event_loop()
    
    # Initialize WidgetService
    widget = WidgetService(config, event_bus, loop, session_service)
    
    # Schedule setup after loop starts
    # We can't access widget._root yet because it's created in start() if we call start()
    # Actually WidgetService.__init__ does NOT create root.
    # start() creates root.
    
    # We can create a root manually and pass it?
    # WidgetService design: self._root = None initially.
    # start() calls: self._root = ctk.CTk() ... self._root.mainloop()
    
    # We can hook into the loop by scheduling a callback before starting?
    # No, we can't schedule on non-existent root.
    
    # Solution: Monkey patch start?
    # Or just subclass?
    
def main():
    # Get current loop
    loop = asyncio.get_event_loop()
    
    # Initialize WidgetService
    widget = WidgetService(config, event_bus, loop, session_service)
    
    print("Starting Widget UI thread...")
    widget.start()
    
    print("Waiting for UI root to initialize...")
    while widget._root is None:
        time.sleep(0.1)
        
    print("UI intialized. Scheduling simulation...")
    # Schedule on UI thread
    widget._root.after(1000, lambda: setup_simulation(widget))
    
    print("Simulation running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
            # Check if window closed
            try:
                if not widget._root.winfo_exists():
                    break
            except:
                break
    except KeyboardInterrupt:
        pass
    finally:
        widget.stop()

if __name__ == "__main__":
    main()
