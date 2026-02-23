from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class ContentFilter:
    # --- HTML ---
    _HTML_IMG_TAG = re.compile(
        r"<(?:img|picture|figure|source|video|audio|canvas|svg|embed|object)"
        r"[^>]*>(?:.*?</(?:picture|figure|video|audio|svg|object)>)?",
        re.IGNORECASE | re.DOTALL,
    )
    _HTML_GENERIC_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
    _HTML_ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
    _HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

    # --- Markdown images & links ---
    # ![alt text](url) or ![alt text][ref]
    _MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
    _MD_IMAGE_REF = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")
    # [link text](url) — replace with just link text
    _MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")

    # --- Data URIs ---
    _DATA_URI = re.compile(
        r"data:[a-zA-Z]+/[a-zA-Z0-9.+\-]+;?[^,\s]*,?[A-Za-z0-9+/=\s]{10,}",
        re.IGNORECASE,
    )

    # --- URLs ---
    _URL_PATTERN = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+", re.IGNORECASE)
    _EMAIL_PATTERN = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
    )

    # --- Media file paths ---
    _MEDIA_EXT = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".bmp",
        ".ico",
        ".tiff",
        ".tif",
        ".avif",
        ".mp4",
        ".mp3",
        ".wav",
        ".ogg",
        ".avi",
        ".mkv",
        ".mov",
    )
    _FILE_PATH = re.compile(
        r"(?:[A-Za-z]:[/\\]|/|\\\\|\.{0,2}/)"  # Drive letter, unix path, UNC, relative
        r"[^\s<>\"'|]*"
        r"\.(?:png|jpe?g|gif|svg|webp|bmp|ico|tiff?|avif|mp[34]|wav|ogg|avi|mkv|mov)\b",
        re.IGNORECASE,
    )

    # --- Standalone media filenames ---
    _STANDALONE_MEDIA = re.compile(
        r"^\s*\S+\.(?:png|jpe?g|gif|svg|webp|bmp|ico|tiff?|avif)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    # --- Browser artifacts ---
    _BROWSER_IMAGE_MARKERS = re.compile(
        r"\[(?:image|img|photo|picture|icon|logo|thumbnail|avatar|banner|screenshot)\]"
        r"|\((?:image|img|photo|picture)\)"
        r"|📷|📸|🖼️|🖼|🎨|🏞️|🌄|🌅",
        re.IGNORECASE,
    )

    # --- Markdown formatting ---
    _MD_FORMATTING = re.compile(r"[*_~`#>\[\]!|]+")

    def filter(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        original_length = len(text)

        # 1. Strip HTML comments first (may contain anything)
        text = self._HTML_COMMENT.sub("", text)

        # 2. Strip HTML media tags (img, picture, figure, video, etc.)
        text = self._HTML_IMG_TAG.sub("", text)

        # 3. Strip remaining HTML tags
        text = self._HTML_GENERIC_TAG.sub("", text)

        # 4. Decode HTML entities
        text = self._HTML_ENTITY.sub(" ", text)

        # 5. Strip data URIs / base64 blobs
        text = self._DATA_URI.sub("", text)

        # 6. Strip markdown images (keep alt text only if meaningful)
        text = self._MD_IMAGE.sub("", text)
        text = self._MD_IMAGE_REF.sub("", text)

        # 7. Convert markdown links to plain text
        text = self._MD_LINK.sub(r"\1", text)

        # 8. Strip markdown formatting
        text = self._MD_FORMATTING.sub("", text)

        # 9. Strip URLs and emails
        text = self._URL_PATTERN.sub("", text)
        text = self._EMAIL_PATTERN.sub("", text)

        # 10. Strip file paths to media
        text = self._FILE_PATH.sub("", text)

        # 11. Strip standalone media filenames
        text = self._STANDALONE_MEDIA.sub("", text)

        # 12. Strip browser image markers
        text = self._BROWSER_IMAGE_MARKERS.sub("", text)

        filtered_length = len(text.strip())
        if filtered_length < original_length:
            removed = original_length - filtered_length
            logger.debug(
                "Content filtered: %d → %d chars (%d removed)",
                original_length,
                filtered_length,
                removed,
            )

        return text
