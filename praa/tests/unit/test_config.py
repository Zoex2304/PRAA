"""
Unit Tests — AppConfig (Pydantic Model)

Validates configuration loading, defaults, validation rules,
and voice roster mapping.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.domain.config.models import AppConfig, VoiceGender, LanguagePreference


def test_default_config():
    """Default config should have sensible values matching the spec."""
    config = AppConfig()
    assert config.hotkey_read == "<ctrl>+<shift>+r"
    assert config.hotkey_stop == "<ctrl>+<shift>+s"
    assert config.voice_id == "id-ID-ArdiNeural"
    assert config.voice_en == "en-US-BrianNeural"
    assert config.speed_rate == 1.0
    assert config.language_preference == LanguagePreference.AUTO
    assert config.max_chunk_length == 2000


def test_speed_rate_validation():
    """Speed rate should be clamped between 0.5 and 2.0."""
    config = AppConfig(speed_rate=1.5)
    assert config.speed_rate == 1.5

    with pytest.raises(Exception):
        AppConfig(speed_rate=0.1)  # Below minimum

    with pytest.raises(Exception):
        AppConfig(speed_rate=3.0)  # Above maximum


def test_speed_rate_rounding():
    """Speed rate should be rounded to 2 decimal places."""
    config = AppConfig(speed_rate=1.333)
    assert config.speed_rate == 1.33


def test_invalid_voice_id():
    """Voice ID without 'Neural' should be rejected."""
    with pytest.raises(Exception):
        AppConfig(voice_id="invalid-voice")


def test_voice_roster_male():
    """Male roster should map to Ardi (ID) and Brian (EN)."""
    config = AppConfig(voice_gender=VoiceGender.MALE)
    assert config.get_voice_for_language("id") == "id-ID-ArdiNeural"
    assert config.get_voice_for_language("en") == "en-US-BrianNeural"


def test_voice_roster_female():
    """Female roster should map to Gadis (ID) and Jenny (EN)."""
    config = AppConfig(voice_gender=VoiceGender.FEMALE)
    assert config.get_voice_for_language("id") == "id-ID-GadisNeural"
    assert config.get_voice_for_language("en") == "en-US-JennyNeural"


def test_voice_roster_unknown_language():
    """Unknown language should fall back to default voice_id."""
    config = AppConfig()
    result = config.get_voice_for_language("fr")
    assert result == config.voice_id


def test_json_serialization():
    """Config should serialize/deserialize cleanly to JSON."""
    config = AppConfig(speed_rate=1.25, voice_gender=VoiceGender.FEMALE)
    json_str = config.model_dump_json()
    data = json.loads(json_str)

    restored = AppConfig(**data)
    assert restored.speed_rate == 1.25
    assert restored.voice_gender == VoiceGender.FEMALE


def test_from_json_file():
    """Config should load correctly from a JSON file."""
    data = {
        "hotkey_read": "<ctrl>+<shift>+r",
        "hotkey_stop": "<ctrl>+<shift>+s",
        "voice_id": "id-ID-ArdiNeural",
        "voice_en": "en-US-BrianNeural",
        "voice_gender": "male",
        "speed_rate": 1.0,
        "language_preference": "auto",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = Path(f.name)

    try:
        raw = json.loads(temp_path.read_text())
        config = AppConfig(**raw)
        assert config.voice_id == "id-ID-ArdiNeural"
    finally:
        temp_path.unlink()
