from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceEntry:
    """A single TTS voice in the catalog."""

    voice_id: str
    name: str
    language_code: str  # ISO 639-1: "id", "en"
    language_label: str  # Human-readable: "Indonesian"
    gender: str  # "male" | "female"

    @property
    def display_label(self) -> str:
        return f"{self.name} — {self.language_label}"

    @property
    def gender_label(self) -> str:
        return self.gender.capitalize()


@dataclass(frozen=True)
class LanguageOption:
    code: str  # "auto" | ISO 639-1
    label: str


# ---------------------------------------------------------------------------
# Voice catalog — add new voices here; no structural changes required.
# ---------------------------------------------------------------------------

VOICE_CATALOG: list[VoiceEntry] = [
    VoiceEntry("id-ID-ArdiNeural", "Ardi", "id", "Indonesian", "male"),
    VoiceEntry("id-ID-GadisNeural", "Gadis", "id", "Indonesian", "female"),
    VoiceEntry("en-US-BrianNeural", "Brian", "en", "English (US)", "male"),
    VoiceEntry("en-US-JennyNeural", "Jenny", "en", "English (US)", "female"),
    VoiceEntry("en-GB-RyanNeural", "Ryan", "en", "English (UK)", "male"),
    VoiceEntry("en-GB-SoniaNeural", "Sonia", "en", "English (UK)", "female"),
]

LANGUAGE_OPTIONS: list[LanguageOption] = [
    LanguageOption("auto", "Auto-detect"),
    LanguageOption("id", "Indonesian"),
    LanguageOption("en", "English"),
]


def find_voice(voice_id: str) -> VoiceEntry | None:
    return next((v for v in VOICE_CATALOG if v.voice_id == voice_id), None)


def get_voices_for_language(language_code: str) -> list[VoiceEntry]:
    if language_code == "auto":
        return VOICE_CATALOG
    return [v for v in VOICE_CATALOG if v.language_code == language_code]
