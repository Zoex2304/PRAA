from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def calculate_text_offsets(
    text: str,
    boundaries: list[tuple[float, float, str]],
) -> list[tuple[float, float, str, int, int]]:
    enhanced: list[tuple[float, float, str, int, int]] = []
    current_pos = 0
    text_lower = text.lower()

    for offset, duration, word in boundaries:
        word_clean = word.strip()
        if not word_clean:
            continue

        # Try exact match first
        idx = text.find(word_clean, current_pos)
        if idx == -1:
            # Try case-insensitive
            idx = text_lower.find(word_clean.lower(), current_pos)

        if idx != -1:
            enhanced.append((offset, duration, word_clean, idx, len(word_clean)))
            current_pos = idx + len(word_clean)
        else:
            # Fallback: use current position
            enhanced.append(
                (offset, duration, word_clean, current_pos, len(word_clean))
            )

    return enhanced
