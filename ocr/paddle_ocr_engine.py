"""
Primary OCR engine implementation using PaddleOCR (PP-OCRv4).

Implements OCREngineProtocol with:
- Singleton instance caching to avoid weight reload overhead
- 4-corner polygon to axis-aligned bounding box transformation
- Graceful empty-image and low-confidence handling
"""

import logging
import threading
from typing import Any, Optional
import numpy as np

from ocr.interfaces import OCREngineProtocol, OCRToken

logger = logging.getLogger("synaptix.ocr.paddle")


class PaddleOCREngine(OCREngineProtocol):
    """
    PaddleOCR PP-OCRv4 implementation with thread-safe singleton initialization.
    """

    _instance: Optional["PaddleOCREngine"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, lang: str = "en", use_angle_cls: bool = True, show_log: bool = False):
        """
        Initialize PaddleOCR engine instance.
        Note: Use get_instance() for shared singleton in production service.
        """
        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            logger.error("PaddleOCR is not installed. Install via `pip install paddlepaddle paddleocr`.")
            raise RuntimeError(
                "PaddleOCR library is missing. Please run `pip install paddlepaddle paddleocr`."
            ) from e

        logger.info(f"Initializing PaddleOCR engine (lang={lang}, use_angle_cls={use_angle_cls})...")
        self._ocr_engine = PaddleOCR(
            lang=lang,
            use_angle_cls=use_angle_cls,
            show_log=show_log,
        )
        logger.info("PaddleOCR engine initialized successfully.")

    @classmethod
    def get_instance(cls, lang: str = "en", use_angle_cls: bool = True) -> "PaddleOCREngine":
        """Thread-safe singleton accessor for the PaddleOCR engine."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(lang=lang, use_angle_cls=use_angle_cls, show_log=False)
        return cls._instance

    @staticmethod
    def _polygon_to_bbox(polygon: list[list[float]]) -> list[int]:
        """
        Convert 4-point polygon [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        to axis-aligned bounding box [x_min, y_min, x_max, y_max].
        """
        xs = [pt[0] for pt in polygon]
        ys = [pt[1] for pt in polygon]
        return [int(round(min(xs))), int(round(min(ys))), int(round(max(xs))), int(round(max(ys)))]

    def detect_and_recognize(self, image: np.ndarray) -> list[OCRToken]:
        """
        Run PP-OCRv4 detection and recognition on the provided RGB image array.

        Args:
            image: uint8 NumPy array of shape (H, W, 3).

        Returns:
            list[OCRToken]: Detected tokens with text, confidence, and bounding box.
        """
        if image is None or image.size == 0:
            return []

        try:
            # PaddleOCR returns: [ [ [ [x1,y1],... ], (text, confidence) ], ... ]
            raw_results = self._ocr_engine.ocr(image, cls=True)
        except Exception as err:
            logger.error(f"Error during PaddleOCR inference: {err}", exc_info=True)
            raise RuntimeError(f"PaddleOCR inference failed: {err}") from err

        tokens: list[OCRToken] = []

        # PaddleOCR returns [None] or empty list if no text detected
        if not raw_results or raw_results[0] is None:
            logger.debug("PaddleOCR detected no text lines in image.")
            return []

        for line in raw_results[0]:
            if not line or len(line) < 2:
                continue

            polygon, text_conf = line[0], line[1]
            if not text_conf or len(text_conf) < 2:
                continue

            raw_text = str(text_conf[0]).strip()
            confidence = float(text_conf[1])

            if not raw_text:
                continue

            # Convert 4-point polygon to [x_min, y_min, x_max, y_max]
            bbox = self._polygon_to_bbox(polygon)

            token = OCRToken(
                text=raw_text,
                confidence=round(max(0.0, min(1.0, confidence)), 4),
                bbox=bbox,
            )
            tokens.append(token)

        return tokens
