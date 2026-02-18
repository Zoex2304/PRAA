"""
PRAA Config Service — Load, Save, and Runtime Config Management

Responsibilities:
- Load config from JSON file (or create default if missing)
- Save config back to JSON
- Emit ConfigChanged events when settings are modified at runtime
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.domain.config.models import AppConfig, VoiceGender
from src.infrastructure.event_bus import EventBus
from src.infrastructure.events import ConfigChanged, TrayAction, TrayActionType

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Manages application configuration lifecycle.

    Loads from disk at startup, provides runtime access, and persists
    changes back to disk. Emits ConfigChanged events so other services
    can react to configuration updates without polling.
    """

    def __init__(self, config_path: Path, event_bus: EventBus) -> None:
        self._config_path = config_path
        self._event_bus = event_bus
        self._config: AppConfig = self._load()

    @property
    def config(self) -> AppConfig:
        """Current application configuration (read-only access)."""
        return self._config

    def _load(self) -> AppConfig:
        """Load config from JSON file, or create defaults if missing."""
        if self._config_path.exists():
            try:
                raw = json.loads(self._config_path.read_text(encoding="utf-8"))
                config = AppConfig(**raw)
                logger.info("Config loaded from %s", self._config_path)
                return config
            except Exception:
                logger.exception(
                    "Failed to load config from %s, using defaults",
                    self._config_path,
                )

        # Create default config and persist it
        config = AppConfig()
        self._save(config)
        logger.info("Default config created at %s", self._config_path)
        return config

    def _save(self, config: AppConfig) -> None:
        """Persist config to JSON file."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(
                config.model_dump_json(indent=2),
                encoding="utf-8",
            )
            logger.debug("Config saved to %s", self._config_path)
        except Exception:
            logger.exception("Failed to save config to %s", self._config_path)

    async def update(self, key: str, value: Any) -> None:
        """
        Update a single config field and emit ConfigChanged event.

        Args:
            key: Field name on AppConfig.
            value: New value for the field.

        Raises:
            AttributeError: If key is not a valid config field.
            ValueError: If value fails Pydantic validation.
        """
        if not hasattr(self._config, key):
            raise AttributeError(f"Unknown config key: {key}")

        old_value = getattr(self._config, key)
        if old_value == value:
            return  # No change, skip event

        # Create new config with updated field (immutable update pattern)
        updated_data = self._config.model_dump()
        updated_data[key] = value
        self._config = AppConfig(**updated_data)
        self._save(self._config)

        logger.info("Config updated: %s = %s (was %s)", key, value, old_value)
        await self._event_bus.publish(
            ConfigChanged(key=key, old_value=old_value, new_value=value)
        )

    async def handle_tray_action(self, event: TrayAction) -> None:
        """
        Handle tray menu actions that modify configuration.

        Responds to CHANGE_SPEED and CHANGE_VOICE actions by updating
        the config and persisting to disk. Other tray actions are ignored.
        """
        if event.action == TrayActionType.CHANGE_SPEED and event.value:
            try:
                new_speed = float(event.value)
                await self.update("speed_rate", new_speed)
            except (ValueError, TypeError):
                logger.warning("Invalid speed value from tray: %s", event.value)

        elif event.action == TrayActionType.CHANGE_VOICE and event.value:
            try:
                new_gender = VoiceGender(event.value)
                await self.update("voice_gender", new_gender)
                # Also update the primary voice_id based on new gender
                new_voice = self._config.get_voice_for_language("id")
                await self.update("voice_id", new_voice)
                new_voice_en = self._config.get_voice_for_language("en")
                await self.update("voice_en", new_voice_en)
            except (ValueError, TypeError):
                logger.warning("Invalid voice value from tray: %s", event.value)
