from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class UploadRecord:
    source_path: Path
    file_name: str
    file_size_bytes: int
    word_count: int
    is_image: bool
