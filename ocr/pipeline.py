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
import gc
from pathlib import Path
from typing import Union
import numpy as np

import cv2
from ocr.interfaces import OCRToken
from ocr.models import (
    LegalMetrologyFields,
    OCRRawPayload,
    OCRResult,
    OCRTelemetry,
)
from ocr.paddle_ocr_engine import extract_text, RapidOCREngine
from ocr.normalizer import TokenNormalizer
from ocr.field_extractor import LegalFieldExtractor, repair_fields
from ocr.preprocess_handoff import load_and_prepare

logger = logging.getLogger("synaptix.ocr.pipeline")


def retry_on_regions(
    image: np.ndarray,
    engine: RapidOCREngine,
    missing_fields: list[str],
) -> dict[str, str]:
    """
    Improvement #5: Targeted fallback OCR on cropped sub-regions.
    Re-OCRs cropped regions for specific missing fields at 1.5x upscaling.
    """
    h, w = image.shape[:2]
    regions = {
        # field: (y_start_pct, y_end_pct, x_start_pct, x_end_pct)
        "mrp": (0.5, 1.0, 0.4, 1.0),               # bottom-right
        "net_quantity": (0.4, 0.9, 0.0, 0.6),      # middle-left
        "manufacture_date": (0.5, 1.0, 0.0, 0.6),  # bottom-left
    }
    recovered = {}
    for field in missing_fields:
        if field not in regions:
            continue
        y1, y2, x1, x2 = regions[field]
        crop = image[int(h * y1):int(h * y2), int(w * x1):int(w * x2)]
        if crop.size == 0:
            continue
        # Upscale the crop for better OCR
        crop = cv2.resize(crop, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        tokens = engine.detect_and_recognize(crop)
        text = " ".join(t.text for t in tokens)
        # Re-run the field extractor on the crop text
        extractor = LegalFieldExtractor()
        partial = extractor.extract(text)
        if isinstance(partial, dict) and partial.get(field):
            recovered[field] = partial[field]
        elif hasattr(partial, field) and getattr(partial, field):
            recovered[field] = getattr(partial, field)
    return recovered


def run_ocr_pipeline(image: Union[np.ndarray, str, Path, bytes, bytearray]) -> OCRResult:
    """
    Executes the full end-to-end OCR and Rule 6 compliance extraction pipeline.

    Args:
        image: Image input as raw bytes, NumPy array, or file path.

    Returns:
        OCRResult: Standardized schema object containing ocr_raw, fields, and telemetry.
    """
    start_time = time.perf_counter()

    # Preprocess image array for primary inference & fallback crops
    image_np = load_and_prepare(image)

    # 1. Detect & Recognize raw text tokens
    raw_payload: OCRRawPayload = extract_text(image_np)
    tokens: list[OCRToken] = raw_payload.texts

    # 2. Reading-order line normalization
    lines = TokenNormalizer.normalize(tokens)

    # 3. Deterministic Rule 6 statutory extraction
    fields: LegalMetrologyFields = LegalFieldExtractor.extract_all_fields(lines)
    raw_text = " ".join(t.text for t in tokens)
    fields = repair_fields(fields, raw_text)

    # 4. Improvement #5: Targeted retry for critical missing fields
    critical_fields = ["mrp", "net_quantity", "manufacture_date"]
    missing = [f for f in critical_fields if not getattr(fields, f, None)]
    if missing:
        engine = RapidOCREngine.get_instance()
        retry_fields = retry_on_regions(image_np, engine, missing)
        if retry_fields:
            fields = fields.model_copy(update={k: v for k, v in retry_fields.items() if v})

    # 5. Telemetry metrics
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    mean_conf = (
        round(sum(t.confidence for t in tokens) / len(tokens), 4)
        if tokens
        else 1.0
    )

    telemetry = OCRTelemetry(
        engine_name="RapidOCR-PP-OCRv4",
        inference_latency_ms=elapsed_ms,
        total_tokens_detected=len(tokens),
        mean_confidence=mean_conf,
    )

    logger.info(
        f"OCR Pipeline completed: {len(tokens)} tokens, {len(lines)} lines, "
        f"{elapsed_ms}ms latency, mean_confidence={mean_conf}"
    )

    # Release cyclic references and native memory back to the OS
    gc.collect()

    return OCRResult(
        ocr_raw=raw_payload,
        fields=fields,
        telemetry=telemetry,
    )
