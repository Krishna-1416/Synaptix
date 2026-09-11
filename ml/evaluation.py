"""
Benchmark evaluation engine and field-level metric calculator for Legal Metrology.

Compares ground-truth declarations against predictions and computes:
- Exact Match (EM)
- Normalized Match (NM)
- Precision (P)
- Recall (R)
- F1-Score (F1)

Fields Evaluated:
- manufacturer
- country_of_origin
- generic_name
- net_quantity
- manufacture_date
- mrp
- unit_sale_price
- consumer_care

Rule:
Never fabricate accuracy scores. If ground truth is missing or insufficient,
the engine explicitly flags the evaluation as incomplete and reports unannotated counts.
"""

from __future__ import annotations
import re
import unicodedata
from typing import Any, Optional, Sequence, Union

from ml.schemas import (
    EvaluationResult,
    FieldMetric,
    STANDARD_FIELD_NAMES,
)

MIN_STATISTICAL_SUPPORT = 5


class FieldNormalizer:
    """
    Standardized canonicalization rules for Legal Metrology statutory fields.
    Normalizes typographic variances, unit synonyms, and punctuation to enable fair comparison.
    """

    @classmethod
    def clean_general_text(cls, text: Optional[str]) -> str:
        """Generic normalization: unicode normalization, whitespace collapse, punctuation trim."""
        if text is None:
            return ""
        norm = unicodedata.normalize("NFKC", str(text))
        norm = norm.strip().lower()
        norm = re.sub(r"[\s\t\n\r]+", " ", norm)
        norm = re.sub(r"^[\s\:\-\.\,\;\|]+|[\s\:\-\.\,\;\|]+$", "", norm)
        return norm

    @classmethod
    def normalize_manufacturer(cls, text: Optional[str]) -> str:
        """Canonicalize corporate entity suffixes and addresses."""
        cleaned = cls.clean_general_text(text)
        if not cleaned:
            return ""
        # Standardize company suffixes
        cleaned = re.sub(r"\bpvt\.?\s*ltd\.?\b", "private limited", cleaned)
        cleaned = re.sub(r"\bltd\.?\b", "limited", cleaned)
        cleaned = re.sub(r"\bco\.?\b", "company", cleaned)
        cleaned = re.sub(r"\bcorp\.?\b", "corporation", cleaned)
        cleaned = re.sub(r"\bmfg\.?\s*(?:by)?\b", "", cleaned)
        cleaned = re.sub(r"\bmanufactured\s*(?:and\s*packed)?\s*by\b", "", cleaned)
        return cls.clean_general_text(cleaned)

    @classmethod
    def normalize_net_quantity(cls, text: Optional[str]) -> str:
        """Canonicalize metric weight, volume, or count declarations."""
        cleaned = cls.clean_general_text(text)
        if not cleaned:
            return ""

        # Remove "net weight", "net qty", etc.
        cleaned = re.sub(r"\bnet\s*(?:wt|weight|qty|quantity|content)?\b", "", cleaned)
        cleaned = re.sub(r"^[\:\-\s\=e]+", "", cleaned).strip()

        # Match number and unit
        m = re.search(r"(\d+(?:\.\d+)?)\s*([a-z]+)", cleaned)
        if m:
            val, unit = m.group(1), m.group(2)
            # Remove trailing zero decimals: 200.0 -> 200
            val_float = float(val)
            val_str = str(int(val_float)) if val_float.is_integer() else str(val_float)

            # Standardize unit
            if unit in ("g", "gm", "gram", "grams"):
                u = "g"
            elif unit in ("kg", "kilogram", "kilograms"):
                u = "kg"
            elif unit in ("ml", "millilitre", "millilitres"):
                u = "ml"
            elif unit in ("l", "ltr", "litre", "litres"):
                u = "l"
            elif unit in ("n", "unit", "units", "pc", "pcs", "piece", "pieces", "nos"):
                u = "units"
            else:
                u = unit
            return f"{val_str} {u}"

        return cleaned

    @classmethod
    def normalize_mrp(cls, text: Optional[str]) -> str:
        """Canonicalize currency values (removes symbols, taxes, /-)."""
        cleaned = cls.clean_general_text(text)
        if not cleaned:
            return ""

        # Remove taxes and qualifiers
        cleaned = re.sub(r"\(?incl(?:usive)?\s*of\s*(?:all\s*)?taxes\)?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:mrp|max(?:imum)?\s*retail\s*price)\b", "", cleaned, flags=re.IGNORECASE)
        # Remove currency labels and slashes without stripping decimal points
        cleaned = re.sub(r"[₹]|(?:\b(?:rs|inr)\b\.?)|\/\-", "", cleaned, flags=re.IGNORECASE).strip()

        # Extract numerical amount with optional commas and decimals
        m = re.search(r"(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?", cleaned)
        if m:
            amt_str = m.group(0).replace(",", "")
            amount = float(amt_str)
            return f"{amount:.2f}"
        return cleaned

    @classmethod
    def normalize_date(cls, text: Optional[str]) -> str:
        """Canonicalize manufacture / packing date to MM/YYYY."""
        cleaned = cls.clean_general_text(text)
        if not cleaned:
            return ""

        cleaned = re.sub(r"\b(?:mfd|mfg|pkd|packed|date\s*of\s*mfg|date\s*of\s*packing)\b", "", cleaned)
        cleaned = cls.clean_general_text(cleaned)

        # DD/MM/YYYY -> MM/YYYY
        m_full = re.search(r"\b\d{1,2}[\/\-\.](\d{2})[\/\-\.](\d{4})\b", cleaned)
        if m_full:
            return f"{m_full.group(1)}/{m_full.group(2)}"

        # MM/YYYY
        m_my = re.search(r"\b(\d{2})[\/\-\.](\d{4})\b", cleaned)
        if m_my:
            return f"{m_my.group(1)}/{m_my.group(2)}"

        # MM/YY -> MM/20YY
        m_short = re.search(r"\b(\d{2})[\/\-\.](\d{2})\b", cleaned)
        if m_short:
            return f"{m_short.group(1)}/20{m_short.group(2)}"

        return cleaned

    @classmethod
    def normalize_country(cls, text: Optional[str]) -> str:
        """Canonicalize country of origin."""
        cleaned = cls.clean_general_text(text)
        if not cleaned:
            return ""
        cleaned = re.sub(r"\b(?:country\s*of\s*origin|made\s*in|product\s*of|manufactured\s*in)\b", "", cleaned)
        return cls.clean_general_text(cleaned)

    @classmethod
    def normalize_field(cls, field_name: str, value: Optional[str]) -> str:
        """Route to appropriate field-specific normalizer."""
        if value is None:
            return ""
        if field_name == "manufacturer":
            return cls.normalize_manufacturer(value)
        elif field_name == "net_quantity":
            return cls.normalize_net_quantity(value)
        elif field_name == "mrp":
            return cls.normalize_mrp(value)
        elif field_name == "manufacture_date":
            return cls.normalize_date(value)
        elif field_name == "country_of_origin":
            return cls.normalize_country(value)
        else:
            return cls.clean_general_text(value)


def calculate_field_metric(
    field_name: str,
    ground_truth_values: Sequence[Optional[str]],
    predicted_values: Sequence[Optional[str]],
) -> FieldMetric:
    """
    Computes Exact Match, Normalized Match, Precision, Recall, and F1 for a single statutory field.

    Handles unannotated samples safely:
    - If ground truth is None, the sample is excluded from support and not penalized as FN.
    - If prediction is made for an unannotated sample, it is logged but not treated as a false positive.
    """
    if len(ground_truth_values) != len(predicted_values):
        raise ValueError(
            f"Length mismatch: {len(ground_truth_values)} ground truths vs {len(predicted_values)} predictions"
        )

    support = 0
    predicted_count = 0
    exact_matches = 0
    normalized_matches = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for gt, pred in zip(ground_truth_values, predicted_values):
        gt_clean = gt.strip() if gt is not None else None
        pred_clean = pred.strip() if pred is not None else None

        if gt_clean is not None:
            # We have verified ground truth for this sample
            support += 1

            if pred_clean is not None:
                predicted_count += 1

                # Exact match check
                if pred_clean.lower() == gt_clean.lower():
                    exact_matches += 1

                # Normalized match check
                norm_gt = FieldNormalizer.normalize_field(field_name, gt_clean)
                norm_pred = FieldNormalizer.normalize_field(field_name, pred_clean)

                if norm_gt and norm_pred and (norm_gt == norm_pred or norm_gt in norm_pred or norm_pred in norm_gt):
                    normalized_matches += 1
                    true_positives += 1
                else:
                    false_positives += 1
            else:
                # Ground truth was present, but prediction was missing
                false_negatives += 1
        else:
            # Ground truth is unannotated
            if pred_clean is not None:
                predicted_count += 1

    # Calculate metrics
    em = (exact_matches / support) if support > 0 else 0.0
    nm = (normalized_matches / support) if support > 0 else 0.0
    precision = (true_positives / (true_positives + false_positives)) if (true_positives + false_positives) > 0 else 0.0
    recall = (true_positives / (true_positives + false_negatives)) if (true_positives + false_negatives) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    insufficient = support < MIN_STATISTICAL_SUPPORT
    if support == 0:
        notes = "No ground-truth annotations available in dataset. Evaluation score cannot be computed."
    elif insufficient:
        notes = f"Sparse ground truth ({support} sample(s)). Statistical evaluation requires at least {MIN_STATISTICAL_SUPPORT}."
    else:
        notes = "Adequate ground-truth support."

    return FieldMetric(
        field_name=field_name,
        exact_match=round(em, 4),
        normalized_match=round(nm, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        support=support,
        predicted_count=predicted_count,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        insufficient_data=insufficient,
        notes=notes,
    )


def evaluate_predictions(
    ground_truths: Sequence[Union[dict[str, Optional[str]], Any]],
    predictions: Sequence[Union[dict[str, Optional[str]], Any]],
) -> EvaluationResult:
    """
    Evaluates a collection of predicted fields against ground-truth declarations.

    Args:
        ground_truths: List of ground-truth dictionaries or DatasetRecord objects.
        predictions: List of prediction dictionaries or ExtractionResult objects.

    Returns:
        EvaluationResult: Detailed benchmark metrics with explicit incompleteness warnings.
    """
    total_samples = len(ground_truths)
    if total_samples != len(predictions):
        raise ValueError(
            f"Sample count mismatch: {total_samples} ground truths vs {len(predictions)} predictions"
        )

    # Convert inputs to standardized dict format if needed
    gt_dicts: list[dict[str, Optional[str]]] = []
    for item in ground_truths:
        if hasattr(item, "ground_truth") and hasattr(item.ground_truth, "to_dict"):
            gt_dicts.append(item.ground_truth.to_dict())
        elif hasattr(item, "to_dict"):
            gt_dicts.append(item.to_dict())
        elif isinstance(item, dict):
            gt_dicts.append(item)
        else:
            raise TypeError(f"Unsupported ground-truth format: {type(item).__name__}")

    pred_dicts: list[dict[str, Optional[str]]] = []
    for item in predictions:
        if hasattr(item, "fields"):
            pred_dicts.append(item.fields)
        elif hasattr(item, "to_dict"):
            pred_dicts.append(item.to_dict().get("fields", {}))
        elif isinstance(item, dict):
            pred_dicts.append(item.get("fields", item))
        else:
            raise TypeError(f"Unsupported prediction format: {type(item).__name__}")

    # Compute metrics for each statutory field
    field_metrics: dict[str, FieldMetric] = {}
    fields_with_support = 0
    total_em = 0.0
    total_nm = 0.0
    total_prec = 0.0
    total_rec = 0.0
    total_f1 = 0.0

    samples_with_any_gt = 0
    for gt in gt_dicts:
        if any(gt.get(fn) is not None for fn in STANDARD_FIELD_NAMES):
            samples_with_any_gt += 1

    for fn in STANDARD_FIELD_NAMES:
        gt_vals = [gt.get(fn) for gt in gt_dicts]
        pred_vals = [pred.get(fn) for pred in pred_dicts]
        metric = calculate_field_metric(fn, gt_vals, pred_vals)
        field_metrics[fn] = metric

        if metric.support > 0:
            fields_with_support += 1
            total_em += metric.exact_match
            total_nm += metric.normalized_match
            total_prec += metric.precision
            total_rec += metric.recall
            total_f1 += metric.f1

    # Macro averages across supported fields
    macro_em = (total_em / fields_with_support) if fields_with_support > 0 else 0.0
    macro_nm = (total_nm / fields_with_support) if fields_with_support > 0 else 0.0
    macro_prec = (total_prec / fields_with_support) if fields_with_support > 0 else 0.0
    macro_rec = (total_rec / fields_with_support) if fields_with_support > 0 else 0.0
    macro_f1 = (total_f1 / fields_with_support) if fields_with_support > 0 else 0.0

    # Determine completeness
    is_incomplete = (
        fields_with_support < len(STANDARD_FIELD_NAMES)
        or any(m.insufficient_data for m in field_metrics.values())
        or total_samples < 20
    )

    if is_incomplete:
        unsupported = [fn for fn, m in field_metrics.items() if m.support == 0]
        status_msg = (
            f"INCOMPLETE EVALUATION: Insufficient ground-truth annotations. "
            f"Only {fields_with_support}/{len(STANDARD_FIELD_NAMES)} fields have any ground truth. "
            f"Zero ground truth for: {unsupported}. "
            "Never use these scores as real ML benchmark performance without an annotated dataset."
        )
    else:
        status_msg = "Complete evaluation across all statutory Legal Metrology fields."

    return EvaluationResult(
        field_metrics=field_metrics,
        overall_exact_match=round(macro_em, 4),
        overall_normalized_match=round(macro_nm, 4),
        overall_precision=round(macro_prec, 4),
        overall_recall=round(macro_rec, 4),
        overall_f1=round(macro_f1, 4),
        total_samples=total_samples,
        evaluated_samples=samples_with_any_gt,
        is_incomplete=is_incomplete,
        status_message=status_msg,
    )
