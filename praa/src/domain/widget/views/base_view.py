import customtkinter as ctk

class AbstractView(ctk.CTkFrame):
    """Base class for all widget views."""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

    def on_show(self):
        """Called when the view becomes active."""
        pass

    def on_hide(self):
        """Called when the view becomes inactive."""
        pass

    def refresh(self):
        """Update UI state (optional)."""
        pass
