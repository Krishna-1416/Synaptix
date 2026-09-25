"""
Dedicated RapidOCR (PP-OCRv4 ONNXRuntime) engine adapter for Synaptix.

Provides fast, lightweight, CPU-optimized text detection and recognition:
- Uses PP-OCRv4 (DBNet++ detector + SVTR-LCNet recognizer) via ONNXRuntime
- Low memory footprint (~180 MB - 220 MB RAM), zero heavy C++ compiler dependencies
- Thread-safe singleton accessor
- Automatic polygon-to-bbox coordinate normalization
- Multi-pass adaptive recovery for real-world conditions (glare, shadows, low contrast, tiny fonts)
"""

import logging
import threading
from pathlib import Path
from typing import List, Optional, Union
import numpy as np

from ocr.interfaces import OCREngineProtocol, OCRToken
from ocr.models import OCRRawPayload
from ocr.preprocess_handoff import PreprocessHandoff, load_and_prepare
from cv.adaptive_enhancement import enhance_packaging_image, upscale_if_low_res

logger = logging.getLogger("synaptix.ocr.rapid")


class RapidOCREngine(OCREngineProtocol):
    """
    Dedicated RapidOCR implementation running PP-OCRv4 models via ONNXRuntime.
    Provides fast, standalone inference with a minimal RAM footprint (<250 MB).
    """

    _instance: Optional["RapidOCREngine"] = None
    _lock: threading.Lock = threading.Lock()
    _inference_lock: threading.Lock = threading.Lock()

    def __init__(self, show_log: bool = False):
        """Initialize RapidOCR engine instance."""
        try:
            from pathlib import Path
            from rapidocr_onnxruntime import RapidOCR

            # Check for quantized server models (Improvement #7) or full server models (Improvement #1)
            quantized_det = Path("models/quantized/ch_PP-OCRv4_server_det_infer_int8.onnx")
            quantized_rec = Path("models/quantized/ch_PP-OCRv4_server_rec_doc_infer_int8.onnx")
            server_det = Path("models/ch_PP-OCRv4_server_det_infer.onnx")
            server_rec = Path("models/ch_PP-OCRv4_server_rec_doc_infer.onnx")

            det_path = None
            if quantized_det.exists():
                det_path = str(quantized_det)
            elif server_det.exists():
                det_path = str(server_det)

            rec_path = None
            if quantized_rec.exists():
                rec_path = str(quantized_rec)
            elif server_rec.exists():
                rec_path = str(server_rec)

            # RapidOCR parameter tuning (Improvements #1, #2, #7, #8)
            # min_height=32 adds vertical padding for short/tightly-packed packaging lines
            self._engine = RapidOCR(
                det_model_path=det_path,
                rec_model_path=rec_path,
                det_limit_side_len=1280,
                det_db_thresh=0.20,
                det_db_box_thresh=0.40,
                det_db_unclip_ratio=2.2,
                text_score=0.35,
                min_height=32,
            )
            # Disable aspect ratio cutoff to prevent skipping text on elongated packaging (cans, milk cartons)
            self._engine.width_height_ratio = -1
            logger.info("RapidOCR (PP-OCRv4 ONNXRuntime) engine initialized successfully.")
        except ImportError as err:
            logger.error(f"RapidOCR library is missing: {err}. Please install `rapidocr-onnxruntime`.")
            raise RuntimeError(
                "RapidOCR library is missing. Please run `pip install rapidocr-onnxruntime`."
            ) from err

    @classmethod
    def get_instance(cls, **kwargs) -> "RapidOCREngine":
        """Thread-safe singleton accessor for the RapidOCR engine."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
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

    def detect_and_recognize(
        self,
        image: np.ndarray,
        det_db_thresh: float = 0.20,
        box_thresh: float = 0.40,
        unclip_ratio: float = 2.2,
        text_score: float = 0.35,
        limit_side_len: int = 1280,
    ) -> list[OCRToken]:
        """
        Run PP-OCRv4 detection and recognition on the provided RGB image array.

        Args:
            image: uint8 NumPy array of shape (H, W, 3).
            det_db_thresh: DBNet pixel binarization threshold (lower = captures faint/low-contrast ink).
            box_thresh: DBNet box confidence threshold (higher = suppresses background graphic noise).
            unclip_ratio: Bounding box expansion ratio (preserves diacritics, decimals & edge chars).
            text_score: Recognition confidence threshold (lower = preserves marginal candidates for regex).
            limit_side_len: Max side length for DBNet inference, aligned to TARGET_MAX_DIMENSION.

        Returns:
            list[OCRToken]: Detected tokens with text, confidence, and bounding box.
        """
        if image is None or image.size == 0:
            return []

        try:
            with self._inference_lock:
                # Configure detector limit side length to preserve small fonts
                if hasattr(self._engine, "text_detector") and hasattr(self._engine.text_detector, "preprocess_op"):
                    if len(self._engine.text_detector.preprocess_op) > 0:
                        self._engine.text_detector.preprocess_op[0].limit_side_len = limit_side_len

                raw_out = self._engine(
                    image,
                    det_db_thresh=det_db_thresh,
                    box_thresh=box_thresh,
                    unclip_ratio=unclip_ratio,
                    text_score=text_score,
                )
            # RapidOCR returns (results, elapse_list)
            results = raw_out[0] if isinstance(raw_out, tuple) else raw_out
        except Exception as err:
            logger.error(f"Error during RapidOCR inference: {err}", exc_info=True)
            raise RuntimeError(f"RapidOCR inference failed: {err}") from err

        if not results:
            return []

        tokens: list[OCRToken] = []
        for item in results:
            if not item or len(item) < 2:
                continue

            polygon = item[0]
            if len(item) == 2 and isinstance(item[1], (list, tuple)):
                raw_text, conf = item[1][0], item[1][1]
            elif len(item) >= 3:
                raw_text, conf = item[1], item[2]
            else:
                continue

            text = str(raw_text).strip()
            if not text:
                continue

            bbox = self._polygon_to_bbox(polygon)
            tokens.append(
                OCRToken(
                    text=text,
                    confidence=round(max(0.0, min(1.0, float(conf))), 4),
                    bbox=bbox,
                )
            )
        return tokens


def compute_iou(bbox1: List[int], bbox2: List[int]) -> float:
    """Compute Intersection-over-Union between two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0

    area1 = max(0, bbox1[2] - bbox1[0]) * max(0, bbox1[3] - bbox1[1])
    area2 = max(0, bbox2[2] - bbox2[0]) * max(0, bbox2[3] - bbox2[1])
    union_area = area1 + area2 - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def merge_ocr_tokens(
    tokens_a: List[OCRToken],
    tokens_b: List[OCRToken],
    iou_threshold: float = 0.40,
) -> List[OCRToken]:
    """
    Merges tokens from two OCR passes (e.g. standard + enhanced):
    - When tokens overlap (IoU >= threshold), retains the token with higher confidence.
    - When tokens do not overlap, appends the rescued token.
    """
    merged = list(tokens_a)

    for tb in tokens_b:
        matched_idx = -1
        best_iou = 0.0

        for idx, ma in enumerate(merged):
            iou = compute_iou(ma.bbox, tb.bbox)
            if iou > best_iou:
                best_iou = iou
                matched_idx = idx

        if best_iou >= iou_threshold and matched_idx >= 0:
            # Overlap: keep the one with higher confidence or longer text
            existing = merged[matched_idx]
            if tb.confidence > existing.confidence + 0.10 or len(tb.text) > len(existing.text) + 3:
                merged[matched_idx] = tb
        else:
            # Rescued token not detected in first pass
            merged.append(tb)

    return merged


# Alias for backward compatibility across existing references
PaddleOCREngine = RapidOCREngine


def extract_text(image: Union[np.ndarray, str, Path, bytes, bytearray]) -> OCRRawPayload:
    """
    Adaptive multi-condition OCR text extraction facade using RapidOCR (PP-OCRv4).
    
    1. Validates and standardizes input into RGB uint8 ndarray.
    2. Pass 1: Runs RapidOCREngine with tuned detection params (Improvement #2: det_db_thresh=0.20,
       box_thresh=0.40, unclip_ratio=2.2, text_score=0.35, limit_side_len=1280).
    3. Pass 2 (Adaptive Recovery): If Pass 1 yields low tokens (<18) or low confidence (<0.65),
       applies glare suppression, CLAHE contrast enhancement, unsharp sharpening, and upscaling.
    4. Merges & deduplicates tokens via spatial IoU to maximize recall under real packaging conditions.
    
    Returns:
        OCRRawPayload: Container with complete list of OCRToken objects.
    """
    image_np = load_and_prepare(image)

    try:
        engine = RapidOCREngine.get_instance()
        # Pass 1: Tuned-parameter inference (Improvement #2 — aggressive detection)
        # det_db_thresh=0.20: captures faint inkjet/dot-matrix text on colored packaging
        # box_thresh=0.40:    suppresses background graphic noise introduced by lower binarization
        # unclip_ratio=2.2:   expands boxes to prevent edge characters (decimals, units) being clipped
        # text_score=0.35:    passes marginal candidates downstream to deterministic regex filters
        # limit_side_len=1280: aligned to TARGET_MAX_DIMENSION — eliminates redundant scale ops
        pass1_tokens = engine.detect_and_recognize(
            image_np,
            det_db_thresh=0.20,
            box_thresh=0.40,
            unclip_ratio=2.2,
            text_score=0.35,
            limit_side_len=1280,
        )

        h, w = image_np.shape[:2]
        mean_conf = (
            sum(t.confidence for t in pass1_tokens) / len(pass1_tokens)
            if pass1_tokens
            else 0.0
        )

        # Determine if adaptive recovery pass is warranted
        needs_recovery = (
            len(pass1_tokens) < 18
            or mean_conf < 0.65
            or min(h, w) < 500
        )

        if not needs_recovery:
            return OCRRawPayload(texts=pass1_tokens or [])

        # Pass 2: Adaptive recovery pass
        logger.info(
            f"Triggering Pass 2 adaptive OCR recovery (Pass 1 yielded {len(pass1_tokens)} tokens, "
            f"mean_conf={mean_conf:.2f})"
        )

        # Upscale if low-resolution
        up_image, scale_factor = upscale_if_low_res(image_np, min_dimension_threshold=600)
        enhanced_image = enhance_packaging_image(up_image)

        # Pass 2: Aggressive recovery — slightly lower box_thresh to maximize token rescue
        # on contrast-enhanced image where faint text becomes clearer
        pass2_raw_tokens = engine.detect_and_recognize(
            enhanced_image,
            det_db_thresh=0.18,
            box_thresh=0.35,
            unclip_ratio=2.2,
            text_score=0.32,
            limit_side_len=1280,
        )

        # If upscaled, rescale Pass 2 bounding boxes back to original coordinates
        if scale_factor > 1.001 and pass2_raw_tokens:
            rescaled_tokens: List[OCRToken] = []
            for t in pass2_raw_tokens:
                orig_bbox = [int(round(coord / scale_factor)) for coord in t.bbox]
                rescaled_tokens.append(
                    OCRToken(text=t.text, confidence=t.confidence, bbox=orig_bbox)
                )
            pass2_tokens = rescaled_tokens
        else:
            pass2_tokens = pass2_raw_tokens

        # Merge Pass 1 and Pass 2
        final_tokens = merge_ocr_tokens(pass1_tokens, pass2_tokens, iou_threshold=0.40)
        logger.info(
            f"Adaptive OCR recovery complete: {len(pass1_tokens)} (P1) + {len(pass2_tokens)} (P2) -> "
            f"{len(final_tokens)} merged tokens"
        )
        return OCRRawPayload(texts=final_tokens)

    except Exception as err:
        logger.error(f"RapidOCR inference failed: {err}", exc_info=True)
        return OCRRawPayload(texts=[])
