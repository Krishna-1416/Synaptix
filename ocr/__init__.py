"""
Synaptix OCR Subsystem (Member 3 - OCR Engineer).

Provides Optical Character Recognition, text cleaning, coordinate ordering,
and deterministic Legal Metrology declaration extraction conforming to
Rule 6 of the Packaged Commodities Rules, 2011.
"""

from ocr.field_extractor import LegalFieldExtractor
from ocr.interfaces import OCREngineProtocol, OCRToken
from ocr.models import (
    LegalMetrologyFields,
    OCRRawPayload,
    OCRResult,
    OCRTelemetry,
)
from ocr.normalizer import TextLine, TokenNormalizer
from ocr.paddle_ocr_engine import PaddleOCREngine
from ocr.preprocess_handoff import ImageValidationError, PreprocessHandoff

__all__ = [
    "OCREngineProtocol",
    "OCRToken",
    "OCRRawPayload",
    "LegalMetrologyFields",
    "OCRTelemetry",
    "OCRResult",
    "PreprocessHandoff",
    "ImageValidationError",
    "PaddleOCREngine",
    "TokenNormalizer",
    "TextLine",
    "LegalFieldExtractor",
]
