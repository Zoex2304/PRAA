from __future__ import annotations

from pathlib import Path

import flet as ft

from src.domain.config.theme_config import ThemeConfig
from src.domain.upload.models import UploadRecord
from src.presentation.components.upload_record_card import UploadRecordCard


class UploadSectionComponent(ft.Container):

    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        self._cards: dict[str, UploadRecordCard] = {}
        self._cards_list = ft.Column(controls=[], spacing=6)

        self.content = self._cards_list
        self.padding = ft.padding.symmetric(horizontal=4, vertical=4)
        self.visible = False

    def add_record(self, record: UploadRecord) -> UploadRecordCard:
        card = UploadRecordCard(self._theme, record)
        self._cards[str(record.source_path)] = card
        self._cards_list.controls.append(card)
        self.visible = True
        self._safe_update(self._cards_list)
        self._safe_update(self)
        return card

    def advance_card_step(self, source_path: Path, step: int) -> None:
        card = self._cards.get(str(source_path))
        if card:
            card.advance_step(step)

    def complete_card(self, source_path: Path) -> None:
        card = self._cards.get(str(source_path))
        if card:
            card.complete()

    def _safe_update(self, control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass
