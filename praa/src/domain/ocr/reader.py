from __future__ import annotations

import logging
import threading

import numpy as np
from PIL import Image

from src.domain.ocr.config import (
    PADDLE_DET_DB_BOX_THRESH,
    PADDLE_DET_DB_THRESH,
    PADDLE_DET_DB_UNCLIP_RATIO,
    PADDLE_DET_LIMIT_SIDE_LEN,
    PADDLE_LANG,
    PADDLE_MIN_CONFIDENCE,
    PADDLE_USE_ANGLE_CLS,
    PADDLE_USE_DILATION,
    PADDLE_USE_GPU,
    SCALE_FACTOR,
)
from src.domain.ocr.debug_writer import OcrDebugWriter
from src.domain.ocr.preprocessor import OcrPreprocessor

logger = logging.getLogger(__name__)


class OcrReaderService:
    def __init__(self, debug_writer: OcrDebugWriter) -> None:
        self._ocr = None
        self._lock = threading.Lock()
        self._preprocessor = OcrPreprocessor()
        self._debug_writer = debug_writer

    def read(self, image: Image.Image) -> str:
        self._ensure_engine()
        processed = self._preprocessor.process(image)
        self._debug_writer.save(processed, "02_scaled.png")
        self._debug_writer.save(processed, "03_preprocessed.png")
        return self._recognize(processed)

    def _ensure_engine(self) -> None:
        if self._ocr is not None:
            return
        with self._lock:
            if self._ocr is not None:
                return
            logger.debug(
                "[CONFIG] SCALE_FACTOR=%d  PADDLE_LANG=%s"
                "  DET_DB_THRESH=%.2f  DET_DB_BOX_THRESH=%.2f"
                "  USE_GPU=%s  USE_ANGLE_CLS=%s",
                SCALE_FACTOR,
                PADDLE_LANG,
                PADDLE_DET_DB_THRESH,
                PADDLE_DET_DB_BOX_THRESH,
                PADDLE_USE_GPU,
                PADDLE_USE_ANGLE_CLS,
            )
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                use_angle_cls=PADDLE_USE_ANGLE_CLS,
                lang=PADDLE_LANG,
                use_gpu=PADDLE_USE_GPU,
                show_log=False,
                det_db_thresh=PADDLE_DET_DB_THRESH,
                det_db_box_thresh=PADDLE_DET_DB_BOX_THRESH,
                det_db_unclip_ratio=PADDLE_DET_DB_UNCLIP_RATIO,
                use_dilation=PADDLE_USE_DILATION,
                det_limit_side_len=PADDLE_DET_LIMIT_SIDE_LEN,
            )
            logging.disable(logging.NOTSET)
            logger.info("PaddleOCR engine ready (lang=%s)", PADDLE_LANG)

    def _recognize(self, image: Image.Image) -> str:
        logger.debug(
            "[INFERENCE] input_image_size=%dx%dpx  color_space=RGB→BGR",
            image.width,
            image.height,
        )
        self._debug_writer.save(image, "04_pre_inference.png")
        img_array = np.array(image)[:, :, ::-1]
        result = self._ocr.ocr(img_array, cls=PADDLE_USE_ANGLE_CLS)
        return self._extract_text(result)

    def _extract_text(self, result) -> str:
        if not result or result[0] is None:
            logger.debug("[PADDLE] total_detections=0")
            logger.debug("[OUTPUT] accepted_lines=0 / total_lines=0  final_text=''")
            return ""

        lines = sorted(result[0], key=lambda line: line[0][0][1])
        logger.debug("[PADDLE] total_detections=%d", len(lines))

        texts = []
        rejected = []
        for i, (bbox, (text, confidence)) in enumerate(lines):
            tl, br = bbox[0], bbox[2]
            logger.debug(
                "[PADDLE] line_%d: conf=%.3f  bbox=(%d,%d)→(%d,%d)  text=%r",
                i,
                confidence,
                int(tl[0]),
                int(tl[1]),
                int(br[0]),
                int(br[1]),
                text,
            )
            if confidence >= PADDLE_MIN_CONFIDENCE:
                texts.append(text)
            else:
                rejected.append(f"{text!r}@conf={confidence:.3f}")

        final = " ".join(texts).strip()
        logger.debug(
            "[OUTPUT] accepted_lines=%d / total_lines=%d", len(texts), len(lines)
        )
        if rejected:
            logger.debug("[OUTPUT] rejected_lines=%s", rejected)
        logger.debug("[OUTPUT] final_text=%r", final)
        return final
