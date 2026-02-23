"""
PRAA Event Definitions — Single Source of Truth

All domain events are defined here. No other module should define events.
Each event is an immutable dataclass carrying only the data its consumers need (ISP).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    """Origin of the text that was captured for TTS."""
    USER_BLOCK = "USER_BLOCK"    # Clipboard via hotkey
    OCR = "OCR"                  # Screen region OCR
    FILE_UPLOAD = "FILE_UPLOAD"  # Uploaded file


class HotkeyAction(Enum):
    """Actions that can be triggered by a global hotkey."""
    READ = auto()
    STOP = auto()
    OCR = auto()   # Screen region OCR capture


class TrayActionType(Enum):
    """Actions that can be triggered from the system tray or widget."""
    PLAY_LAST = auto()
    PAUSE = auto()
    RESUME = auto()
    STOP = auto()
    EXIT = auto()
    CHANGE_SPEED = auto()
    CHANGE_VOICE = auto()
    TOGGLE_MODE = auto()
    SAVE_AUDIO = auto()


class PlaybackState(Enum):
    """Current state of the audio playback system."""
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()


class DetectedLanguage(Enum):
    """Supported languages for TTS voice selection."""
    INDONESIAN = "id"
    ENGLISH = "en"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Events — Input Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HotkeyPressed:
    """Emitted when a registered global hotkey is pressed."""
    action: HotkeyAction


@dataclass(frozen=True)
class TextCaptured:
    """Emitted when clipboard text is successfully captured."""
    raw_text: str
    source_type: str = SourceType.USER_BLOCK


# ---------------------------------------------------------------------------
# Events — Processing Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextProcessed:
    """Emitted when raw text has been cleaned, language-detected, and chunked."""
    chunks: list[str]
    language: DetectedLanguage
    voice_id: str
    speed_rate: float = 1.0


# ---------------------------------------------------------------------------
# Events — TTS Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SynthesisStarted:
    """Emitted when TTS synthesis begins for a chunk."""
    chunk_index: int
    total_chunks: int


@dataclass(frozen=True)
class SynthesisComplete:
    """Emitted when a single chunk has been synthesized to an audio file."""
    audio_path: Path
    chunk_index: int
    total_chunks: int
    chunk_text: str = ""
    word_boundaries: list[tuple[float, float, str, int, int]] = field(default_factory=list)
    # Each tuple: (offset_seconds, duration_seconds, word, text_offset, word_len)
    
    sentence_boundaries: list[tuple[float, float, str]] = field(default_factory=list)
    # Each tuple: (offset_seconds, duration_seconds, sentence_text)


# ---------------------------------------------------------------------------
# Events — Output Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlaybackStarted:
    """Emitted when audio playback begins."""
    chunk_index: int = 0
    total_chunks: int = 1
    timestamp: float = 0.0


@dataclass(frozen=True)
class PlaybackStopped:
    """Emitted when audio playback completes or is stopped."""
    reason: str = "completed"  # "completed" | "stopped" | "error"


@dataclass(frozen=True)
class PlaybackPaused:
    """Emitted when audio playback is paused."""
    pass


@dataclass(frozen=True)
class PlaybackResumed:
    """Emitted when audio playback resumes from pause."""
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Events — Control Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrayAction:
    """Emitted when the user interacts with the system tray menu."""
    action: TrayActionType
    value: Optional[str] = None  # For CHANGE_SPEED ("1.25") or CHANGE_VOICE ("Gadis")


@dataclass(frozen=True)
class ConfigChanged:
    """Emitted when configuration is modified at runtime."""
    key: str
    old_value: object
    new_value: object


# ---------------------------------------------------------------------------
# Events — Widget Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WidgetAction:
    """Emitted when the user interacts with the floating widget."""
    action: TrayActionType
    value: Optional[str] = None


# ---------------------------------------------------------------------------
# Events — OCR Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OcrCaptureRequested:
    """Emitted when the OCR hotkey (Ctrl+Shift+O) is pressed."""
    pass


@dataclass(frozen=True)
class OcrRegionSelected:
    """Emitted when the user finishes drag-selecting a screen region."""
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrTextExtracted:
    """Emitted when OCR successfully extracts text from the captured region."""
    text: str


@dataclass(frozen=True)
class OcrCaptureFailed:
    """Emitted when OCR returns empty text, errors, or is cancelled."""
    reason: str  # "empty" | "error" | "cancelled"


# ---------------------------------------------------------------------------
# Events — Upload Layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileUploadRequested:
    source_path: Path


@dataclass(frozen=True)
class FileTextReady:
    source_path: Path
    text: str
    file_size_bytes: int
    word_count: int
    is_image: bool


@dataclass(frozen=True)
class FileUploadFailed:
    source_path: Path
    reason: str


# ---------------------------------------------------------------------------
# Events — Lifecycle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppStarted:
    """Emitted when the application has completed initialization."""
    pass


@dataclass(frozen=True)
class AppShutdown:
    """Emitted when the application is shutting down gracefully."""
    reason: str = "user_exit"
