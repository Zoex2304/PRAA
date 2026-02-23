from __future__ import annotations

import logging
import os
from datetime import datetime

from PIL import Image

logger = logging.getLogger(__name__)


class OcrDebugWriter:
    def __init__(self, base_dir: str | None) -> None:
        self._base_dir = base_dir
        self._run_dir: str | None = None

    def start_run(self) -> None:
        if self._base_dir is None:
            self._run_dir = None
            return
        now = datetime.now()
        date_folder = "{}_{}".format(now.strftime("%Y-%m-%d"), now.strftime("%A"))
        run_folder = "run_{}".format(now.strftime("%H-%M-%S"))
        self._run_dir = os.path.join(self._base_dir, date_folder, run_folder)
        try:
            os.makedirs(self._run_dir, exist_ok=True)
        except Exception:
            logger.exception("Failed to create OCR debug run dir: %s", self._run_dir)
            self._run_dir = None

    def save(self, image: Image.Image, filename: str) -> None:
        if self._run_dir is None:
            self.start_run()
        if self._run_dir is None:
            return
        try:
            path = os.path.join(self._run_dir, filename)
            image.save(path)
            logger.debug("[DEBUG] saved → %s", path)
        except Exception:
            logger.exception("OCR debug image save failed: %s", filename)
