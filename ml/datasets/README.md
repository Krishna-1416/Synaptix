# ML Datasets Specification & Annotation Guide

## Purpose

This directory serves as the target repository for training, validation, and evaluation datasets for the Synaptix ML subsystem.

In Phase 1, **no large datasets or synthetic corpora are stored here**. This document defines the exact schema, annotation format, and dataset requirements necessary before model training can begin in Phase 2.

---

## Analysis of Current Repository Samples

The current repository contains:
- `sample_data/real_samples/samples_manifest.json`: 10 sample image metadata records.

### Limitations for ML Training:
1. **No Token Annotations**: Token coordinates (`x_min, y_min, x_max, y_max`) are not mapped to statutory labels.
2. **Missing Rule 6 Ground Truth**: Zero samples contain ground truth for `mrp`, `manufacture_date`, `country_of_origin`, or `unit_sale_price`.
3. **Small Sample Size**: 10 records are insufficient for statistical fine-tuning or cross-validation.

---

## Phase 2 Dataset Requirements

To train a robust multimodal or sequence-tagging model for Legal Metrology, the dataset must meet the following criteria:

### 1. Annotation Structure (Token-Level BIO Tagging)

Each document sample must provide normalized tokens with coordinate bounding boxes and statutory entity tags:

```json
{
  "document_id": "doc_001",
  "image_path": "images/doc_001.jpg",
  "image_dimensions": [1920, 1080],
  "tokens": [
    {
      "text": "MRP",
      "bbox": [120, 450, 180, 475],
      "label": "O"
    },
    {
      "text": "Rs.",
      "bbox": [185, 450, 215, 475],
      "label": "B-MRP"
    },
    {
      "text": "50.00",
      "bbox": [220, 450, 280, 475],
      "label": "I-MRP"
    }
  ],
  "ground_truth_fields": {
    "mrp": "Rs. 50.00 (INCL. OF ALL TAXES)",
    "net_quantity": "200 g",
    "manufacture_date": "05/2024",
    "country_of_origin": "India",
    "manufacturer": "Britannia Industries Ltd, Kolkata 700017",
    "generic_name": "Cashew Cookies",
    "unit_sale_price": "Rs. 0.25 / g",
    "consumer_care": "feedback@britannia.co.in, 1800-425-4449"
  }
}
```

### 2. Recommended Dataset Sizing

| Split | Recommended Count | Target Diversity |
|---|:---:|---|
| **Training** | 400 - 800 samples | FMCG, packaged foods, cosmetics, electronics, apparel |
| **Validation** | 100 - 150 samples | Stratified by package geometry (pouch, carton, bottle, can) |
| **Test / Benchmark** | 100 samples | Real-world noisy scans, rotated images, glare, low DPI |

### 3. Data Collection & Synthesis Strategy

1. **Synthetic Data Engine**:
   - Generate synthetic packaging declaration panels using Python PIL / ReportLab.
   - Randomize fonts, font sizes, ink colors, background textures, and bounding boxes.
   - Programmatically inject verified Rule 6 ground truth for 100% annotation fidelity.
2. **Real Sample Annotation**:
   - Use open-source annotation tools like **Label Studio** or **DocBee** configured with the 8 statutory labels.
   - Export annotations to LayoutLM / FUNSD format.
