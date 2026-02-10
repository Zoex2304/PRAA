"""
PRAA Config Models — Pydantic v2 Settings

Single source of truth for all application configuration.
Validated at startup, serializable to/from JSON.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal


class UIMode(str, Enum):
    """Application UI mode."""
    WIDGET = "widget"
    SILENT = "silent"

from pydantic import BaseModel, Field, field_validator


class VoiceGender(str, Enum):
    """Available voice gender options."""
    MALE = "male"
    FEMALE = "female"


class LanguagePreference(str, Enum):
    """Language detection behavior."""
    AUTO = "auto"
    INDONESIAN = "id"
    ENGLISH = "en"


class AppConfig(BaseModel):
    """
    Central application configuration.

    This model is the single source of truth for all configurable behavior.
    Loaded from config.json at startup, and can be modified at runtime
    via tray menu actions (which emit ConfigChanged events).
    """

    # --- Hotkey bindings ---
    hotkey_read: str = Field(
        default="<ctrl>+<shift>+r",
        description="Global hotkey to trigger clipboard read-aloud",
    )
    hotkey_stop: str = Field(
        default="<ctrl>+<shift>+s",
        description="Global hotkey to stop current playback",
    )

    # --- Voice settings ---
    voice_id: str = Field(
        default="id-ID-ArdiNeural",
        description="Default Indonesian voice ID for edge-tts",
    )
    voice_en: str = Field(
        default="en-US-BrianNeural",
        description="English fallback voice ID for edge-tts",
    )
    voice_gender: VoiceGender = Field(
        default=VoiceGender.MALE,
        description="Preferred voice gender (affects voice_id selection)",
    )

    # --- Playback settings ---
    speed_rate: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="TTS speech rate multiplier (0.5x to 2.0x)",
    )

    # --- UI settings ---
    ui_mode: UIMode = Field(
        default=UIMode.WIDGET,
        description="UI mode: 'widget' (floating window) or 'silent' (tray only)",
    )
    auto_copy: bool = Field(
        default=True,
        description="Auto-copy selected text when READ hotkey is pressed",
    )

    # --- Language settings ---
    language_preference: LanguagePreference = Field(
        default=LanguagePreference.AUTO,
        description="Language detection mode: auto-detect or force a language",
    )

    # --- Processing settings ---
    max_chunk_length: int = Field(
        default=2000,
        ge=100,
        le=10000,
        description="Maximum character count per TTS chunk",
    )

    @field_validator("speed_rate")
    @classmethod
    def validate_speed_rate(cls, v: float) -> float:
        """Round speed rate to 2 decimal places for consistency."""
        return round(v, 2)

    @field_validator("voice_id", "voice_en")
    @classmethod
    def validate_voice_id(cls, v: str) -> str:
        """Ensure voice IDs follow the expected format (xx-XX-NameNeural)."""
        if not v or "Neural" not in v:
            raise ValueError(
                f"Invalid voice ID '{v}': must contain 'Neural' "
                f"(e.g., 'id-ID-ArdiNeural')"
            )
        return v

    # --- Voice roster mapping ---
    VOICE_ROSTER: dict[str, dict[str, str]] = {
        "male": {
            "id": "id-ID-ArdiNeural",
            "en": "en-US-BrianNeural",
        },
        "female": {
            "id": "id-ID-GadisNeural",
            "en": "en-US-JennyNeural",
        },
    }

    def get_voice_for_language(self, lang_code: str) -> str:
        """
        Get the appropriate voice ID for a detected language.

        Args:
            lang_code: Language code ('id' or 'en').

        Returns:
            Voice ID string for edge-tts.
        """
        gender = self.voice_gender.value
        roster = self.VOICE_ROSTER.get(gender, self.VOICE_ROSTER["male"])
        return roster.get(lang_code, self.voice_id)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "hotkey_read": "<ctrl>+<shift>+r",
                    "hotkey_stop": "<ctrl>+<shift>+s",
                    "voice_id": "id-ID-ArdiNeural",
                    "voice_en": "en-US-BrianNeural",
                    "voice_gender": "male",
                    "speed_rate": 1.0,
                    "language_preference": "auto",
                }
            ]
        }
    }
