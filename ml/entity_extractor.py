"""
Entity Extraction Subsystem for Synaptix ML (Phase 1).

Provides:
- extract_entities(text, tokens=None)
- RegexEntityExtractorAdapter (adapter wrapping existing ocr.field_extractor)
- MLEntityExtractor (extensible stub for Phase 2 model integration)
- HybridEntityExtractor (conflict resolution pipeline between regex and ML)

Design Principle:
Adheres strictly to the Open/Closed Principle (OCP). The existing ocr/field_extractor.py
is NOT modified; this module acts as a typed adapter and defines the exact interface
for future deep learning models.
"""

from __future__ import annotations
import logging
import re
import sys
import time
import types
from abc import ABC, abstractmethod
from typing import Any, Optional, Union

# Ensure seamless import of ocr.field_extractor even if pydantic is not installed in the active environment
if "pydantic" not in sys.modules:
    try:
        import pydantic  # noqa: F401
    except ImportError:
        _pydantic_shim = types.ModuleType("pydantic")

        class _BaseModel:
            model_config: dict[str, Any] = {}

            def __init__(self, **kwargs: Any) -> None:
                for k, v in kwargs.items():
                    setattr(self, k, v)

            def model_dump(self) -> dict[str, Any]:
                return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

        def _Field(default: Any = None, default_factory: Any = None, **kwargs: Any) -> Any:
            return default_factory() if default_factory else default

        def _ConfigDict(**kwargs: Any) -> dict[str, Any]:
            return kwargs

        _pydantic_shim.BaseModel = _BaseModel
        _pydantic_shim.Field = _Field
        _pydantic_shim.ConfigDict = _ConfigDict
        sys.modules["pydantic"] = _pydantic_shim

from ocr.field_extractor import LegalFieldExtractor, extract_fields  # type: ignore[import-not-found]
from ml.schemas import (
    ExtractionInput,
    ExtractionEntity,
    ExtractionResult,
    STANDARD_FIELD_NAMES,
)

logger = logging.getLogger("synaptix.ml.entity_extractor")


class BaseEntityExtractor(ABC):
    """Abstract interface for statutory Legal Metrology declaration extractors."""

    @abstractmethod
    def extract(self, input_data: ExtractionInput) -> ExtractionResult:
        """Extract statutory entities from standardized ExtractionInput."""
        pass

    def extract_entities(self, text: str, tokens: Optional[list[dict[str, Any]]] = None) -> ExtractionResult:
        """Convenience method accepting raw text and optional OCR tokens."""
        input_data = ExtractionInput(text=text, tokens=tokens)
        return self.extract(input_data)


class RegexEntityExtractorAdapter(BaseEntityExtractor):
    """
    Phase 1 Adapter around the existing deterministic Rule 6 regex extractor
    (ocr.field_extractor.LegalFieldExtractor).
    """

    def __init__(self, default_confidence: float = 0.95) -> None:
        self.default_confidence = default_confidence

    def extract(self, input_data: ExtractionInput) -> ExtractionResult:
        start_time = time.perf_counter()
        text = input_data.text or ""
        tokens = input_data.tokens or []

        # Prepare tokens for ocr.field_extractor.extract_fields
        payload_tokens: list[dict[str, Any]] = []
        if tokens:
            payload_tokens = tokens
        elif text:
            # Reconstruct synthetic line tokens from multiline text for spatial line parser
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            for idx, line in enumerate(lines):
                # Assign distinct synthetic vertical coordinates to preserve line order
                y_coord = idx * 25
                payload_tokens.append({
                    "text": line,
                    "confidence": 1.0,
                    "bbox": [10, y_coord, 500, y_coord + 20],
                })

        # Delegate to existing OCR field extractor without altering it
        raw_result = extract_fields({"texts": payload_tokens})

        # Map to typed ExtractionEntity instances with provenance
        entities: list[ExtractionEntity] = []
        fields_dict: dict[str, Optional[str]] = {}

        for field_name in STANDARD_FIELD_NAMES:
            val = raw_result.get(field_name)
            fields_dict[field_name] = val
            if val is not None:
                # Find matching token bbox if available
                entity_bbox = self._find_matching_bbox(val, payload_tokens)
                entities.append(
                    ExtractionEntity(
                        field_name=field_name,
                        value=val,
                        confidence=self.default_confidence,
                        source="regex",
                        bbox=entity_bbox,
                    )
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ExtractionResult(
            entities=entities,
            fields=fields_dict,
            raw_input=input_data,
            execution_time_ms=elapsed_ms,
            extractor_name="regex_adapter",
            metadata={"token_count": len(payload_tokens)},
        )

    def _find_matching_bbox(
        self,
        value: str,
        tokens: list[dict[str, Any]],
    ) -> Optional[list[Union[int, float]]]:
        """Heuristic search to locate the bounding box of tokens containing the extracted value."""
        if not tokens or not value:
            return None

        # Check for token containing substring of value
        value_lower = value.lower()
        for tok in tokens:
            t_text = str(tok.get("text", "")).lower()
            if t_text and (t_text in value_lower or value_lower in t_text):
                bbox = tok.get("bbox")
                if bbox and len(bbox) == 4:
                    return list(bbox)
        return None


class MLEntityExtractor(BaseEntityExtractor):
    """
    Placeholder and interface contract for Phase 2 Deep Learning / NER models
    (e.g., LayoutLMv3, Donut, BioBERT/RoBERTa sequence taggers).
    """

    def __init__(self, model_path: Optional[str] = None, is_ready: bool = False) -> None:
        self.model_path = model_path
        self.is_ready = is_ready

    def extract(self, input_data: ExtractionInput) -> ExtractionResult:
        start_time = time.perf_counter()

        if not self.is_ready:
            # In Phase 1, ML models are not yet trained or deployed
            logger.info("MLEntityExtractor invoked in Phase 1: Model weights not loaded. Returning empty result.")
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ExtractionResult(
                entities=[],
                fields={fn: None for fn in STANDARD_FIELD_NAMES},
                raw_input=input_data,
                execution_time_ms=elapsed_ms,
                extractor_name="ml_extractor_phase2_stub",
                metadata={"status": "deferred_to_phase_2", "is_ready": False},
            )

        # Phase 2 implementation will execute model inference here
        raise NotImplementedError("Real ML model inference is scheduled for Phase 2.")


class HybridEntityExtractor(BaseEntityExtractor):
    """
    Arbitration pipeline between Regex and ML extraction outputs:

        OCR Tokens / Text
               ↓
        Regex Extractor  ──> Regex Entities
               ↓
        ML Extractor     ──> ML Entities
               ↓
        Conflict Resolution Strategy
               ↓
        Final Structured Declarations (source="hybrid")
    """

    def __init__(
        self,
        regex_extractor: Optional[BaseEntityExtractor] = None,
        ml_extractor: Optional[BaseEntityExtractor] = None,
        ml_confidence_threshold: float = 0.70,
    ) -> None:
        self.regex_extractor = regex_extractor or RegexEntityExtractorAdapter()
        self.ml_extractor = ml_extractor or MLEntityExtractor()
        self.ml_confidence_threshold = ml_confidence_threshold

    def extract(self, input_data: ExtractionInput) -> ExtractionResult:
        start_time = time.perf_counter()

        # Step 1: Run deterministic regex extraction
        regex_result = self.regex_extractor.extract(input_data)

        # Step 2: Run ML extraction
        ml_result = self.ml_extractor.extract(input_data)

        # Step 3: Conflict resolution & arbitration
        merged_entities, merged_fields = self._resolve_conflicts(
            regex_entities=regex_result.entities,
            ml_entities=ml_result.entities,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ExtractionResult(
            entities=merged_entities,
            fields=merged_fields,
            raw_input=input_data,
            execution_time_ms=elapsed_ms,
            extractor_name="hybrid_extractor",
            metadata={
                "regex_entity_count": len(regex_result.entities),
                "ml_entity_count": len(ml_result.entities),
                "arbitrated_count": len(merged_entities),
            },
        )

    def _resolve_conflicts(
        self,
        regex_entities: list[ExtractionEntity],
        ml_entities: list[ExtractionEntity],
    ) -> tuple[list[ExtractionEntity], dict[str, Optional[str]]]:
        """
        Arbitration Rules:
        1. Format-rigid declarations (mrp, net_quantity, manufacture_date, unit_sale_price):
           - Regex takes precedence due to strict statutory formatting rules.
           - ML is used as fallback if regex produces null and ML confidence >= threshold.
        2. Unconstrained text declarations (manufacturer, generic_name, consumer_care):
           - If both predict and match canonically -> merge with source="hybrid".
           - If both predict and conflict -> choose candidate with higher confidence.
           - If only one predicts -> accept that candidate.
        """
        regex_map: dict[str, ExtractionEntity] = {e.field_name: e for e in regex_entities if e.value is not None}
        ml_map: dict[str, ExtractionEntity] = {e.field_name: e for e in ml_entities if e.value is not None}

        final_entities: list[ExtractionEntity] = []
        final_fields: dict[str, Optional[str]] = {fn: None for fn in STANDARD_FIELD_NAMES}

        for field_name in STANDARD_FIELD_NAMES:
            reg_ent = regex_map.get(field_name)
            ml_ent = ml_map.get(field_name)

            chosen_entity: Optional[ExtractionEntity] = None

            if reg_ent is not None and ml_ent is not None:
                # Both extractors found candidate
                if self._values_agree(reg_ent.value, ml_ent.value):
                    # Agreement: create hybrid entity with boosted confidence
                    chosen_entity = ExtractionEntity(
                        field_name=field_name,
                        value=reg_ent.value,
                        confidence=min(1.0, max(reg_ent.confidence, ml_ent.confidence) + 0.03),
                        source="hybrid",
                        bbox=reg_ent.bbox or ml_ent.bbox,
                    )
                else:
                    # Disagreement: apply field-specific precedence
                    if field_name in ("mrp", "net_quantity", "manufacture_date", "unit_sale_price"):
                        # Prefer regex for structured numbers/dates
                        chosen_entity = ExtractionEntity(
                            field_name=field_name,
                            value=reg_ent.value,
                            confidence=reg_ent.confidence,
                            source="hybrid",
                            bbox=reg_ent.bbox,
                        )
                    else:
                        # For text fields, choose higher confidence candidate
                        winner = ml_ent if ml_ent.confidence > reg_ent.confidence else reg_ent
                        chosen_entity = ExtractionEntity(
                            field_name=field_name,
                            value=winner.value,
                            confidence=winner.confidence,
                            source="hybrid",
                            bbox=winner.bbox,
                        )
            elif reg_ent is not None:
                chosen_entity = reg_ent
            elif ml_ent is not None:
                if ml_ent.confidence >= self.ml_confidence_threshold:
                    chosen_entity = ml_ent

            if chosen_entity is not None:
                final_entities.append(chosen_entity)
                final_fields[field_name] = chosen_entity.value

        return final_entities, final_fields

    @staticmethod
    def _values_agree(v1: Optional[str], v2: Optional[str]) -> bool:
        if v1 is None or v2 is None:
            return False
        # Normalize whitespace and lowercase for comparison
        c1 = re.sub(r"\s+", " ", v1).strip().lower()
        c2 = re.sub(r"\s+", " ", v2).strip().lower()
        return c1 == c2 or c1 in c2 or c2 in c1


# Global default adapter instance
_default_extractor: BaseEntityExtractor = RegexEntityExtractorAdapter()


def extract_entities(
    text: str,
    tokens: Optional[list[dict[str, Any]]] = None,
) -> ExtractionResult:
    """
    Standard top-level entrypoint for entity extraction.

    For Phase 1, acts as an adapter around the existing OCR regex extraction.
    Designed so that a real ML model or Hybrid pipeline can replace it in Phase 2
    without modifying client code.

    Args:
        text: Raw transcribed OCR text or multiline document string.
        tokens: Optional list of raw OCR tokens with 'text', 'confidence', 'bbox'.

    Returns:
        ExtractionResult: Typed extraction result containing entities, fields, and provenance.
    """
    return _default_extractor.extract_entities(text=text, tokens=tokens)
