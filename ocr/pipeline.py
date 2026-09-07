"""
Unified OCR & Legal Metrology extraction pipeline facade.

Coordinates:
1. PreprocessHandoff (validation, RGB standardization)
2. Text detection & recognition (PaddleOCR with resilient fallbacks)
3. Coordinate-based line normalization (reading-order reconstruction)
4. Rule 6 statutory field extraction
5. Telemetry calculation
"""

import time
import logging
from pathlib import Path
from typing import Union
import numpy as np

from ocr.interfaces import OCRToken
from ocr.models import (
    LegalMetrologyFields,
    OCRRawPayload,
    OCRResult,
    OCRTelemetry,
)
from ocr.paddle_ocr_engine import extract_text
from ocr.normalizer import TokenNormalizer
from ocr.field_extractor import LegalFieldExtractor

logger = logging.getLogger("synaptix.ocr.pipeline")


def run_ocr_pipeline(image: Union[np.ndarray, str, Path, bytes, bytearray]) -> OCRResult:
    """
    Executes the full end-to-end OCR and Rule 6 compliance extraction pipeline.

    Args:
        image: Image input as raw bytes, NumPy array, or file path.

    Returns:
        OCRResult: Standardized schema object containing ocr_raw, fields, and telemetry.
    """
    start_time = time.perf_counter()

    # 1. Detect & Recognize raw text tokens
    raw_payload: OCRRawPayload = extract_text(image)
    tokens: list[OCRToken] = raw_payload.texts

    # 2. Reading-order line normalization
    lines = TokenNormalizer.normalize(tokens)

    # 3. Deterministic Rule 6 statutory extraction
    fields: LegalMetrologyFields = LegalFieldExtractor.extract_all_fields(lines)

    # 4. Telemetry metrics
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    mean_conf = (
        round(sum(t.confidence for t in tokens) / len(tokens), 4)
        if tokens
        else 1.0
    )

    telemetry = OCRTelemetry(
        engine_name="PaddleOCR-PP-OCRv4",
        inference_latency_ms=elapsed_ms,
        total_tokens_detected=len(tokens),
        mean_confidence=mean_conf,
    )

    logger.info(
        f"OCR Pipeline completed: {len(tokens)} tokens, {len(lines)} lines, "
        f"{elapsed_ms}ms latency, mean_confidence={mean_conf}"
    )

    return OCRResult(
        ocr_raw=raw_payload,
        fields=fields,
        telemetry=telemetry,
    )
