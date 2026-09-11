"""
Data contracts and typed schemas for the Synaptix ML subsystem.

Adheres to shared/schemas/inspection_schema.json and provides typed interfaces
for model inputs, entity extraction, hybrid arbitration, and benchmark evaluation.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Union, Literal

ALLOWED_SOURCES = frozenset({"regex", "ml", "hybrid"})

# Standard Legal Metrology Rule 6 declaration field names
STANDARD_FIELD_NAMES = (
    "manufacturer",
    "country_of_origin",
    "generic_name",
    "net_quantity",
    "manufacture_date",
    "mrp",
    "unit_sale_price",
    "consumer_care",
)


@dataclass
class ExtractionInput:
    """
    Input structure passed into entity extractors.

    Attributes:
        text: Raw OCR transcription or concatenated document text.
        tokens: Optional list of token dictionaries containing 'text', 'confidence', 'bbox'.
        metadata: Optional contextual metadata (e.g. image_id, product_name, category).
    """
    text: str = ""
    tokens: Optional[list[dict[str, Any]]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "tokens": self.tokens,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionInput:
        return cls(
            text=str(data.get("text", "")),
            tokens=data.get("tokens"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ExtractionEntity:
    """
    Represents an extracted entity / declaration candidate.

    Attributes:
        field_name: The statutory field name (e.g. 'mrp', 'net_quantity').
        value: The extracted string declaration, or None if not found.
        confidence: Confidence score strictly between 0.0 and 1.0.
        source: Extraction provenance. Must be one of {'regex', 'ml', 'hybrid'}.
        bbox: Optional axis-aligned bounding box coordinates [x_min, y_min, x_max, y_max].
    """
    field_name: str
    value: Optional[str] = None
    confidence: float = 1.0
    source: str = "regex"
    bbox: Optional[list[Union[int, float]]] = None

    def __post_init__(self) -> None:
        # Validate and normalize source
        if self.source not in ALLOWED_SOURCES:
            raise ValueError(
                f"Invalid source '{self.source}'. Allowed sources are: {sorted(ALLOWED_SOURCES)}"
            )

        # Validate and clamp confidence
        if not isinstance(self.confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(self.confidence).__name__}")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

        # Validate bbox if provided
        if self.bbox is not None:
            if not isinstance(self.bbox, (list, tuple)) or len(self.bbox) != 4:
                raise ValueError(f"bbox must be a 4-element sequence [x_min, y_min, x_max, y_max], got {self.bbox}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "confidence": round(float(self.confidence), 4),
            "source": self.source,
            "bbox": list(self.bbox) if self.bbox is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionEntity:
        return cls(
            field_name=str(data["field_name"]),
            value=data.get("value"),
            confidence=float(data.get("confidence", 1.0)),
            source=str(data.get("source", "regex")),
            bbox=data.get("bbox"),
        )


@dataclass
class ExtractionResult:
    """
    Aggregated extraction result encapsulating entities, standardized fields, and provenance.

    Attributes:
        entities: List of individual ExtractionEntity objects.
        fields: Standardized key-value map conforming to inspection_schema.json fields.
        raw_input: The ExtractionInput processed.
        execution_time_ms: Latency of extraction in milliseconds.
        extractor_name: Name/identifier of the extractor engine used.
        metadata: Optional diagnostic telemetry or intermediate states.
    """
    entities: list[ExtractionEntity] = field(default_factory=list)
    fields: dict[str, Optional[str]] = field(default_factory=dict)
    raw_input: Optional[ExtractionInput] = None
    execution_time_ms: float = 0.0
    extractor_name: str = "regex_adapter"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Populate fields dictionary from entities if not explicitly provided
        if not self.fields and self.entities:
            for entity in self.entities:
                if entity.field_name not in self.fields:
                    self.fields[entity.field_name] = entity.value

    def get_entity(self, field_name: str) -> Optional[ExtractionEntity]:
        """Retrieve the first matching ExtractionEntity for a given field name."""
        for ent in self.entities:
            if ent.field_name == field_name:
                return ent
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractor_name": self.extractor_name,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "fields": dict(self.fields),
            "entities": [e.to_dict() for e in self.entities],
            "metadata": dict(self.metadata),
        }


@dataclass
class FieldMetric:
    """
    Evaluation metrics for a single Legal Metrology field.

    Attributes:
        field_name: The statutory declaration field evaluated.
        exact_match: Ratio of strictly identical predictions to ground truth.
        normalized_match: Ratio of canonically matched predictions to ground truth.
        precision: TP / (TP + FP) or 0.0 if no predictions.
        recall: TP / (TP + FN) or 0.0 if no ground truth.
        f1: Harmonic mean of precision and recall.
        support: Total number of ground-truth annotations available for this field.
        predicted_count: Total number of non-null predictions made.
        true_positives: Count of correct predictions matching ground truth.
        false_positives: Count of spurious or mismatched predictions.
        false_negatives: Count of missing predictions where ground truth was present.
        insufficient_data: True if support is too low for statistically valid evaluation.
        notes: Contextual explanation or warnings.
    """
    field_name: str
    exact_match: float = 0.0
    normalized_match: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0
    predicted_count: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    insufficient_data: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "exact_match": round(self.exact_match, 4),
            "normalized_match": round(self.normalized_match, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "support": self.support,
            "predicted_count": self.predicted_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "insufficient_data": self.insufficient_data,
            "notes": self.notes,
        }


@dataclass
class EvaluationResult:
    """
    Comprehensive benchmark evaluation report across all statutory declarations.

    Attributes:
        field_metrics: Map of field_name to FieldMetric.
        overall_exact_match: Macro-average exact match rate across fields with support.
        overall_normalized_match: Macro-average normalized match rate across fields with support.
        overall_precision: Macro-average precision across evaluated fields.
        overall_recall: Macro-average recall across evaluated fields.
        overall_f1: Macro-average F1 score across evaluated fields.
        total_samples: Total number of dataset records examined.
        evaluated_samples: Count of samples having at least one ground-truth declaration.
        is_incomplete: Flag indicating whether evaluation is partial due to missing ground truth.
        status_message: Human-readable diagnostic description of dataset and evaluation state.
    """
    field_metrics: dict[str, FieldMetric] = field(default_factory=dict)
    overall_exact_match: float = 0.0
    overall_normalized_match: float = 0.0
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    total_samples: int = 0
    evaluated_samples: int = 0
    is_incomplete: bool = True
    status_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_message": self.status_message,
            "is_incomplete": self.is_incomplete,
            "total_samples": self.total_samples,
            "evaluated_samples": self.evaluated_samples,
            "macro_averages": {
                "exact_match": round(self.overall_exact_match, 4),
                "normalized_match": round(self.overall_normalized_match, 4),
                "precision": round(self.overall_precision, 4),
                "recall": round(self.overall_recall, 4),
                "f1": round(self.overall_f1, 4),
            },
            "field_metrics": {k: v.to_dict() for k, v in self.field_metrics.items()},
        }
