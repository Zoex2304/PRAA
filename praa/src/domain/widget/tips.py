from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from src.infrastructure.database.unit_of_work import UnitOfWork


class Feature(StrEnum):
    """Trackable features whose tips are eliminated once the user tries them."""

    READ = "read"
    OCR = "ocr"
    UPLOAD = "upload"
    SPEED = "speed"
    HISTORY = "history"
    SETTINGS = "settings"


@dataclass(frozen=True)
class Tip:
    feature: Feature
    text: str


_TIPS: list[Tip] = [
    Tip(
        Feature.READ,
        "Select any text in any app, then press Ctrl+Shift+R to read it aloud.",
    ),
    Tip(
        Feature.OCR,
        "Press Ctrl+Shift+O or click the scanner icon to capture screen text via OCR.",
    ),
    Tip(
        Feature.UPLOAD,
        "Upload .txt, .pdf, .docx or images - PRAA reads them all aloud.",
    ),
    Tip(
        Feature.SPEED,
        "Use [-] [+] while playing to change speed. PRAA re-synthesizes at the new speed instantly.",
    ),
    Tip(
        Feature.HISTORY,
        "Completed readings are saved in History. Open the History tab to replay any session.",
    ),
    Tip(
        Feature.SETTINGS,
        "The gear button lets you switch between Indonesian and English voices in real time.",
    ),
]

_KEY_SKIPPED = "tips_skipped"
_FEATURE_KEY_PREFIX = "feature_used_"


class TipsManager:
    """
    Manages feature-linked tips.

    Each tip is associated with a specific feature.  A tip is permanently
    eliminated once the user performs that feature (mark_feature_used).
    Tips that have not been tied to any tried feature keep cycling.
    Calling mark_skipped() suppresses the entire system forever.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def should_show(self) -> bool:
        """True if tips are not globally suppressed and at least one feature is untried."""
        with self._uow_factory() as uow:
            if uow.app_state.get(_KEY_SKIPPED) == "true":
                return False
        return self.get_next_tip() is not None

    def get_next_tip(self) -> Tip | None:
        """Return the first tip whose associated feature has not been tried yet."""
        for tip in _TIPS:
            if not self._is_feature_used(tip.feature):
                return tip
        return None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def mark_feature_used(self, feature: Feature) -> None:
        """Permanently eliminate the tip for this feature."""
        with self._uow_factory() as uow:
            uow.app_state.set(f"{_FEATURE_KEY_PREFIX}{feature.value}", "true")
            uow.commit()

    def mark_skipped(self) -> None:
        """User chose to suppress all future tips globally."""
        with self._uow_factory() as uow:
            uow.app_state.set(_KEY_SKIPPED, "true")
            uow.commit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _is_feature_used(self, feature: Feature) -> bool:
        with self._uow_factory() as uow:
            return uow.app_state.get(f"{_FEATURE_KEY_PREFIX}{feature.value}") == "true"
