"""
Synaptix ML Subsystem - Phase 1 Foundation.

Provides typed schemas, dataset manifest loader, entity extraction adapter,
hybrid conflict-resolution interfaces, and evaluation metrics for Legal Metrology.
"""

from ml.schemas import (
    ExtractionInput,
    ExtractionEntity,
    ExtractionResult,
    FieldMetric,
    EvaluationResult,
)
from ml.dataset_loader import (
    DatasetRecord,
    DatasetAuditSummary,
    load_samples_manifest,
    audit_dataset,
)
from ml.entity_extractor import (
    BaseEntityExtractor,
    RegexEntityExtractorAdapter,
    MLEntityExtractor,
    HybridEntityExtractor,
    extract_entities,
)
from ml.evaluation import (
    FieldNormalizer,
    evaluate_predictions,
)

__all__ = [
    "ExtractionInput",
    "ExtractionEntity",
    "ExtractionResult",
    "FieldMetric",
    "EvaluationResult",
    "DatasetRecord",
    "DatasetAuditSummary",
    "load_samples_manifest",
    "audit_dataset",
    "BaseEntityExtractor",
    "RegexEntityExtractorAdapter",
    "MLEntityExtractor",
    "HybridEntityExtractor",
    "extract_entities",
    "FieldNormalizer",
    "evaluate_predictions",
]
  