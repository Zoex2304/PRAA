from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from pathlib import Path

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(StrEnum):
    USER_BLOCK = "USER_BLOCK"  # Clipboard via hotkey
    OCR = "OCR"  # Screen region OCR
    FILE_UPLOAD = "FILE_UPLOAD"  # Uploaded file


class HotkeyAction(Enum):
    READ = auto()
    STOP = auto()
    OCR = auto()  # Screen region OCR capture


class TrayActionType(Enum):
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
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()


class DetectedLanguage(Enum):
    INDONESIAN = "id"
    ENGLISH = "en"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Events — Input Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HotkeyPressed:
    action: HotkeyAction


@dataclass(frozen=True)
class TextCaptured:
    raw_text: str
    source_type: str = SourceType.USER_BLOCK


# ---------------------------------------------------------------------------
# Events — Processing Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextProcessed:
    chunks: list[str]
    language: DetectedLanguage
    voice_id: str
    speed_rate: float = 1.0


# ---------------------------------------------------------------------------
# Events — TTS Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SynthesisStarted:
    chunk_index: int
    total_chunks: int


@dataclass(frozen=True)
class SynthesisComplete:
    audio_path: Path
    chunk_index: int
    total_chunks: int
    chunk_text: str = ""
    word_boundaries: list[tuple[float, float, str, int, int]] = field(
        default_factory=list
    )
    # Each tuple: (offset_seconds, duration_seconds, word, text_offset, word_len)

    sentence_boundaries: list[tuple[float, float, str]] = field(default_factory=list)
    # Each tuple: (offset_seconds, duration_seconds, sentence_text)


# ---------------------------------------------------------------------------
# Events — Output Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlaybackStarted:
    chunk_index: int = 0
    total_chunks: int = 1
    timestamp: float = 0.0


@dataclass(frozen=True)
class PlaybackStopped:
    reason: str = "completed"  # "completed" | "stopped" | "error"


@dataclass(frozen=True)
class PlaybackPaused:
    pass


@dataclass(frozen=True)
class PlaybackResumed:
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Events — Control Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrayAction:
    action: TrayActionType
    value: str | None = None  # For CHANGE_SPEED ("1.25") or CHANGE_VOICE ("Gadis")


@dataclass(frozen=True)
class ConfigChanged:
    key: str
    old_value: object
    new_value: object


# ---------------------------------------------------------------------------
# Events — Widget Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WidgetAction:
    action: TrayActionType
    value: str | None = None


# ---------------------------------------------------------------------------
# Events — OCR Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OcrCaptureRequested:
    pass


@dataclass(frozen=True)
class OcrRegionSelected:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrTextExtracted:
    text: str


@dataclass(frozen=True)
class OcrCaptureFailed:
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
class SplashCompleted:
    pass


@dataclass(frozen=True)
class AppStarted:
    pass


@dataclass(frozen=True)
class AppShutdown:
    reason: str = "user_exit"
