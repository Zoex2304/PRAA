from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class TextCleaner:
    # Pre-compiled regex patterns for performance
    _EMOJI_PATTERN = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # Emoticons
        "\U0001f300-\U0001f5ff"  # Symbols & pictographs
        "\U0001f680-\U0001f6ff"  # Transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # Flags
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"  # Enclosed characters
        "\U0001f900-\U0001f9ff"  # Supplemental symbols
        "\U0001fa00-\U0001fa6f"  # Chess symbols
        "\U0001fa70-\U0001faff"  # Symbols extended-A
        "]+",
        re.UNICODE,
    )
    _MULTIPLE_SPACES = re.compile(r"[ \t]+")
    _MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
    _BULLET_PATTERN = re.compile(r"^\s*[-•·]\s+", re.MULTILINE)
    _NUMBERED_LIST = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)

    def clean(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        original_length = len(text)

        # 1. Remove emojis
        text = self._EMOJI_PATTERN.sub("", text)

        # 2. Clean up list markers (but keep the text content)
        text = self._BULLET_PATTERN.sub("", text)
        text = self._NUMBERED_LIST.sub("", text)

        # 3. Normalize whitespace
        text = self._MULTIPLE_SPACES.sub(" ", text)
        text = self._MULTIPLE_NEWLINES.sub("\n\n", text)
        text = text.strip()

        if text:
            logger.debug(
                "Text cleaned: %d → %d characters",
                original_length,
                len(text),
            )
        else:
            logger.debug("Text cleaned to empty string")

        return text
