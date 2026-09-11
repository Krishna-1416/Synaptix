# Synaptix ML Subsystem - Phase 1 Foundation

## Overview

This module provides the **Phase 1 Machine Learning Foundation** for the Synaptix Automated Legal Metrology Inspection System (SIH26034).

Phase 1 establishes strongly typed data contracts, a dataset manifest loader and audit engine, a non-invasive adapter around the existing OCR regex extractor, a hybrid conflict-resolution design, and a rigorous evaluation engine.

> [!IMPORTANT]
> **Phase 1 Principles:**
> - **No Large Model Downloads**: No heavy weights or pre-trained models are downloaded or stored.
> - **Zero Code Disruption**: Existing modules (`frontend/`, `backend/`, `cv/`, `ocr/field_extractor.py`, `shared/`) are not modified.
> - **Zero Global Package Installations**: Operates on Python 3.14 standard library.
> - **No Fabricated Accuracy**: Missing ground truth is explicitly identified and reported as incomplete.

---

## Directory Layout

```
ml/
├── __init__.py                 # Public package exports
├── README.md                   # This documentation
├── schemas.py                  # Typed data structures (ExtractionEntity, Result, Evaluation)
├── dataset_loader.py           # Manifest loader and dataset auditing
├── entity_extractor.py         # Regex adapter, ML stub, and Hybrid arbitration
├── evaluation.py               # Field normalizer and metric calculation engine
├── datasets/
│   └── README.md               # Dataset requirements and annotation guidelines for Phase 2
├── models/
│   └── README.md               # Phase 2 model architectures and training roadmap
└── tests/
    ├── __init__.py
    └── test_dataset_loader.py  # Unit test suite for Phase 1 components
```

---

## Architecture & Schemas

### 1. Data Contracts (`schemas.py`)

- **`ExtractionInput`**: Envelops raw transcribed text, OCR token arrays (text, confidence, bounding boxes), and contextual metadata.
- **`ExtractionEntity`**: Represents an individual statutory declaration candidate:
  - `field_name`: Mandatory statutory declaration identifier (e.g. `mrp`, `net_quantity`).
  - `value`: Extracted string value or `None`.
  - `confidence`: Confidence score strictly between `0.0` and `1.0`.
  - `source`: Extraction provenance (`'regex' | 'ml' | 'hybrid'`).
  - `bbox`: Axis-aligned bounding box `[x_min, y_min, x_max, y_max]`.
- **`ExtractionResult`**: Aggregates extracted entities and standardized key-value pairs matching `shared/schemas/inspection_schema.json`.
- **`EvaluationResult` & `FieldMetric`**: Detailed precision, recall, F1, exact match, normalized match, and statistical support counters for each field.

---

## Dataset Audit & Findings (`dataset_loader.py`)

The loader ingests `sample_data/real_samples/samples_manifest.json` and cleanly delineates:
1. **Product Metadata**: Brand, barcode, panel category, image dimensions.
2. **Available Ground-Truth Declarations**: Verified statutory values from package declarations.
3. **Raw OCR Text**: 100% absent from current manifest.
4. **Bounding-Box Annotations**: 100% absent from current manifest.

### Audit Summary across Manifest Samples (10 Records):

| Field | Ground Truth Support | Missing Count | Status |
|---|:---:|:---:|---|
| `manufacturer` | 8 / 10 | 2 | Partial (Company names listed) |
| `generic_name` | 6 / 10 | 4 | Partial (Commodity titles) |
| `net_quantity` | 2 / 10 | 8 | Sparse (Only "200g" and "165g" explicit) |
| `mrp` | 0 / 10 | 10 | **Missing** |
| `manufacture_date` | 0 / 10 | 10 | **Missing** |
| `country_of_origin` | 0 / 10 | 10 | **Missing** |
| `unit_sale_price` | 0 / 10 | 10 | **Missing** |
| `consumer_care` | 0 / 10 | 10 | **Missing** (Only generic headings) |

**Conclusion**: The manifest is an asset inventory of product samples, not a labeled ML benchmark. Real ML training requires an annotated dataset.

---

## Hybrid Extraction Pipeline (`entity_extractor.py`)

The hybrid extractor orchestrates conflict resolution between deterministic regex extraction and machine learning predictions:

```
                  Raw OCR Tokens & Text
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    Regex Extractor                  ML Extractor
  (Fast, Deterministic)            (Context-Aware NER)
            │                               │
            ▼                               ▼
     Regex Entities                    ML Entities
            │                               │
            └───────────────┬───────────────┘
                            ▼
               Conflict Resolution Engine
      - Format-rigid fields (MRP, Date, Qty) -> Regex precedence
      - Complex text fields (Manufacturer, Care) -> Confidence arbitration
      - Agreement -> Merged entity with boosted confidence
                            │
                            ▼
                 Final Structured Fields
                   (source="hybrid")
```

In Phase 1, `extract_entities(text, tokens=None)` functions as an adapter around `ocr.field_extractor.LegalFieldExtractor`, enabling downstream code to use the ML interface while preserving current OCR extraction behavior.

---

## Evaluation Engine (`evaluation.py`)

Compares ground-truth declarations against predictions and computes field-level metrics:
- **Exact Match (EM)**: Verifies exact character equality.
- **Normalized Match (NM)**: Uses `FieldNormalizer` to canonicalize units ("200g" == "200 g"), prices ("Rs. 50" == "50.00"), and company suffixes ("Pvt Ltd" == "Private Limited").
- **Precision, Recall, F1**: Measures detection accuracy without penalizing unannotated samples.
- **Incomplete Flag**: If ground truth is missing for any mandatory field, `EvaluationResult.is_incomplete` is set to `True` with an explicit diagnostic explanation.

---

## Running Tests

All Phase 1 tests are built using Python's standard library `unittest` and require no third-party dependencies:

```powershell
python -m unittest discover -s ml/tests -p "test_*.py" -v
```
