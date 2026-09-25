# OCR Accuracy Improvement Guide

**Project:** Synaptix — Automated Legal Metrology Inspection System  
**Component:** `ocr/` module  
**Engine:** RapidOCR (PP-OCRv4 ONNXRuntime)  
**Last Updated:** September 2026  

---

## 1. Overview

This document describes eight targeted improvements to the Synaptix OCR pipeline, ranked by accuracy impact and ordered by implementation priority. Each change includes the rationale, the exact code modification, the expected accuracy gain, and any memory or performance trade-offs.

The recommendations are grounded in:
- RapidOCR's official tuning guide and parameter documentation
- PaddleOCR's PP-OCRv4 model benchmarks
- Field-tested label-OCR preprocessing techniques
- Render free-tier constraints (512 MB RAM, 0.1 vCPU)

---

## 2. Baseline: What's Currently in the Code

| Component | Baseline Value | Implementation Target / File |
| :--- | :--- | :--- |
| **Recognition model** | `PP-OCRv4_mobile_rec` (default) | `ocr/paddle_ocr_engine.py` |
| **Detection model** | `PP-OCRv4_mobile_det` (default) | `ocr/paddle_ocr_engine.py` |
| **`det_limit_side_len`** | 960 | `ocr/paddle_ocr_engine.py` |
| **`det_db_thresh`** | 0.32 | `ocr/paddle_ocr_engine.py` |
| **`det_db_box_thresh`** | 0.32 | `ocr/paddle_ocr_engine.py` |
| **`det_db_unclip_ratio`** | 2.0 | `ocr/paddle_ocr_engine.py` |
| **`text_score`** | 0.45 | `ocr/paddle_ocr_engine.py` |
| **Image cap** | 1280 px | `ocr/preprocess_handoff.py` |
| **CLAHE** | Applied unconditionally | `ocr/preprocess_handoff.py` / `cv/adaptive_enhancement.py` |
| **Field repair** | Regex fallbacks | `ocr/field_extractor.py` |

- **Estimated accuracy on typical Indian product labels:** ~75–80%
- **Target accuracy after improvements:** ~88–92%

---

## 3. Improvement #1 — Switch to Server-Side Recognition Models

### 3.1 Rationale
PaddleOCR ships two families of models: mobile (fast, small, less accurate) and server (slower, larger, much more accurate). The default RapidOCR config uses the mobile variants.

| Model | Recognition Accuracy | Model Size | Inference (CPU) |
| :--- | :--- | :--- | :--- |
| `PP-OCRv4_mobile_rec` | 78.74% | 10.6 MB | ~40 ms |
| `PP-OCRv4_server_rec` | 80.61% | 71.2 MB | ~130 ms |
| `PP-OCRv4_server_rec_doc` | 81.53% | 74.7 MB | ~150 ms |

The `server_rec_doc` variant is trained on an extended document corpus and supports 15,000+ characters, including uncommon symbols and diacritics found on imported packaging. It also handles low-resolution text better than the mobile model.

### 3.2 Implementation
**File:** `ocr/paddle_ocr_engine.py`

```python
self.engine = RapidOCR(
    det_model_path="models/ch_PP-OCRv4_server_det_infer.onnx",
    rec_model_path="models/ch_PP-OCRv4_server_rec_doc_infer.onnx",
    det_limit_side_len=1280,
    det_db_thresh=0.20,
    det_db_box_thresh=0.40,
    det_db_unclip_ratio=2.2,
    text_score=0.35,
)
```

### 3.3 Expected Gain
+3 percentage points on recognition accuracy.

### 3.4 Trade-offs
- **Memory:** +60 MB for the larger model. On Render free tier (512 MB), this must be paired with INT8 quantisation (see Improvement #7).
- **Latency:** ~3× slower inference per image. On 0.1 vCPU, expect 4–8 seconds per scan instead of 2–3 seconds.
- **Model download:** The server models are ~75 MB each. Ensure they're pre-downloaded into the Docker image, not fetched at runtime.

---

## 4. Improvement #2 — Aggressive Detection Parameter Tuning

### 4.1 Rationale
RapidOCR's own tuning guide lists specific parameter adjustments for common failure modes. The two most relevant to product labels are:
- *"漏检小字：调大 det_limit_side_len 到 1280，或调低 det_db_thresh"*  
  (Missing small text: increase `det_limit_side_len` to 1280, or lower `det_db_thresh`)
- *"对于长度较长，高度较小的图像，可尝试对该图像高度做上下补充"*  
  (For wide, short images, add vertical padding)

Product labels are typically wide and short, and mandatory declarations like MRP and net quantity are often printed in small font at the bottom of the label.

### 4.2 Recommended Parameter Values

| Parameter | Baseline | Recommended | Effect |
| :--- | :--- | :--- | :--- |
| `det_limit_side_len` | 960 | 1280 | Preserves detail for dense small text |
| `det_db_thresh` | 0.32 | 0.20 | Captures fainter text regions |
| `det_db_box_thresh` | 0.32 | 0.40 | Reduces false positives from background |
| `det_db_unclip_ratio` | 2.0 | 2.2 | Expands boxes to capture cut-off chars |
| `text_score` | 0.45 | 0.35 | Retains lower-confidence recognitions |

> [!WARNING]
> Warning from the tuning guide: Raising `det_db_box_thresh` too high will drop light-coloured text (e.g., white text on a yellow label). Keep it at 0.40, not the default 0.5–0.6.

### 4.3 Implementation
**File:** `ocr/paddle_ocr_engine.py`

```python
self.engine = RapidOCR(
    det_limit_side_len=1280,
    det_db_thresh=0.20,
    det_db_box_thresh=0.40,
    det_db_unclip_ratio=2.2,
    text_score=0.35,
    # keep existing model paths and other params
)
```

### 4.4 Expected Gain
+2 to +4 percentage points on detection recall, especially for small text.

### 4.5 Trade-offs
- **Memory:** Minimal — `det_limit_side_len=1280` increases the detection input tensor size, but the ONNX arena is already disabled.
- **False positives:** Lowering `det_db_thresh` to 0.20 may pick up more background noise. The `field_extractor.py` regex patterns filter most of this.
- **Latency:** ~15% slower detection.

---

## 5. Improvement #3 — Conditional CLAHE (Not Always-On)

### 5.1 Rationale
Unconditional CLAHE application can hurt accuracy on already-good images by over-amplifying noise. Independent research on OCR preprocessing found that aggressive contrast enhancement reduced accuracy in well-lit cases.

The fix is to apply CLAHE only when the image is genuinely low-contrast, measured by the standard deviation of pixel intensities.

### 5.2 Implementation
**File:** `ocr/preprocess_handoff.py` / `cv/adaptive_enhancement.py`

```python
import cv2
import numpy as np

def load_and_prepare(image_input) -> np.ndarray:
    # ... existing decode and resize logic ...
    
    # Compute image contrast
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    contrast = gray.std()
    
    # Only apply CLAHE if contrast is low
    if contrast < 30:
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
    return img
```

### 5.3 Expected Gain
+1 percentage point on mixed-quality image sets. Larger gains on datasets where many images are already well-lit.

### 5.4 Tuning the Threshold
The threshold `contrast < 30` is a starting point. Measure the standard deviation across your test set of 20–30 labels and pick a value that separates "good" from "poor" images. Values between 25 and 35 are typical.

---

## 6. Improvement #4 — Dynamic Padding for Elongated Labels

### 6.1 Rationale
Product labels are often wide and short — a candy wrapper, a biscuit pack, a milk carton panel. RapidOCR's detection model performs worse on such images because the text lines are compressed vertically.

The tuning guide explicitly recommends adding vertical padding for wide, short images.

### 6.2 Implementation
**File:** `ocr/preprocess_handoff.py`

```python
def compute_padding(w: int, h: int, base_pad: int = 20) -> int:
    # Add extra vertical padding for wide, short images
    aspect = w / max(h, 1)
    if aspect > 3.0:
        return max(base_pad, int(h * 0.15))
    return base_pad

# In load_and_prepare / handoff:
pad = compute_padding(w, h, base_pad=20)
img = cv2.copyMakeBorder(
    img, pad, pad, pad, pad,
    cv2.BORDER_CONSTANT, value=(255, 255, 255)
)
```

### 6.3 Expected Gain
+1 percentage point on wide labels (snack packs, wrappers, bottles).

### 6.4 Trade-offs
- **Memory:** Padding a 1280×300 image to 1280×420 increases the buffer by 40%. Still well within limits.
- **Latency:** Negligible.

---

## 7. Improvement #5 — Targeted Fallback OCR on Cropped Regions

### 7.1 Rationale
When a critical field (MRP, net quantity, manufacture date) is missing after the main OCR pass and regex repair, the field is often present but located in a specific region the engine missed. Re-running OCR on a cropped sub-region at higher effective resolution often recovers it.

This is not multi-pass fusion — it is a single, targeted retry on a much smaller image, so it costs far less memory and CPU.

### 7.2 Implementation
**File:** `ocr/pipeline.py`

```python
def run_ocr_pipeline(image_input) -> OCRResult:
    # ... existing pipeline ...
    fields = extractor.extract(raw_text)
    fields = repair_fields(fields, raw_text)

    # Targeted retry for critical missing fields
    critical_fields = ["mrp", "net_quantity", "manufacture_date"]
    missing = [f for f in critical_fields if not getattr(fields, f, None)]
    if missing:
        retry_fields = retry_on_regions(image, engine, missing)
        for k, v in retry_fields.items():
            if v:
                setattr(fields, k, v)

    # ... telemetry, gc.collect(), return ...
```

**Helper function:**
```python
def retry_on_regions(image, engine, missing_fields):
    # Re-OCR cropped regions for specific missing fields
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
        # Upscale crop for better OCR
        crop = cv2.resize(crop, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        tokens = engine.run(crop)
        text = " ".join(t.text for t in tokens)
        # Re-run field extractor on crop text
        extractor = LegalFieldExtractor()
        partial = extractor.extract(text)
        if partial.get(field):
            recovered[field] = partial[field]
    return recovered
```

### 7.3 Expected Gain
+2 percentage points on critical-field recovery rate, especially on labels where the primary pass merged or missed a region.

### 7.4 Trade-offs
- **Memory:** The cropped region is at most 50% of original area, upscaled 1.5×, so peak memory during retry is roughly equal to the main pass.
- **Latency:** Adds 2–4 seconds when retry is triggered. Only triggers when critical fields are missing.

---

## 8. Improvement #6 — Domain-Specific Character Corrections

### 8.1 Rationale
Product labels use predictable formats for numeric fields. Common OCR confusions on packaging include:
- `O` ↔ `0` (letter O vs digit zero)
- `l` / `I` ↔ `1` (letter l/I vs digit one)
- `S` ↔ `5` (letter S vs digit five)
- `B` ↔ `8` (letter B vs digit eight)
- `Z` ↔ `2` (letter Z vs digit two)

These confusions are harmless in manufacturer names but critical in MRP, net quantity, and dates.

### 8.2 Implementation
**File:** `ocr/field_extractor.py`

```python
NUMERIC_CORRECTIONS = {
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "S": "5",
    "B": "8",
    "Z": "2",
}

def correct_numeric(text: str) -> str:
    # Apply OCR corrections to numeric field candidates only
    for wrong, right in NUMERIC_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text

# Apply only to specific fields, after regex extraction
def repair_fields(fields: dict, raw_text: str) -> dict:
    for field in ["mrp", "net_quantity", "manufacture_date"]:
        if fields.get(field):
            value = fields[field]
            if isinstance(value, str):
                fields[field] = correct_numeric(value)
    return fields
```

### 8.3 Expected Gain
+1 to +2 percentage points on numeric field accuracy.

### 8.4 Trade-offs
- **Risk:** Over-correction. Restricting correction strictly to numeric fields after extraction ensures manufacturer names and countries remain unaffected.

---

## 9. Improvement #7 — INT8 Quantisation

### 9.1 Rationale
Quantising the ONNX models to INT8 reduces model size and memory footprint by 50–75% with typically less than 1% accuracy loss. This is the key enabler for running server models on Render's free tier (512 MB RAM).

### 9.2 Implementation
**Standalone script — `ocr/quantize_models.py`:**

```python
from onnxruntime.quantization import quantize_dynamic, QuantType
import os

MODELS = [
    "ch_PP-OCRv4_server_det_infer.onnx",
    "ch_PP-OCRv4_server_rec_doc_infer.onnx",
]

os.makedirs("models/quantized", exist_ok=True)

for model in MODELS:
    src = f"models/{model}"
    dst = f"models/quantized/{model.replace('.onnx', '_int8.onnx')}"
    quantize_dynamic(
        model_input=src,
        model_output=dst,
        weight_type=QuantType.QInt8,
    )
    print(f"Quantized: {src} -> {dst}")
```

Engine model loading configuration:
```python
self.engine = RapidOCR(
    det_model_path="models/quantized/ch_PP-OCRv4_server_det_infer_int8.onnx",
    rec_model_path="models/quantized/ch_PP-OCRv4_server_rec_doc_infer_int8.onnx",
    # ... params
)
```

### 9.3 Expected Gain
-1 percentage point accuracy (small loss), but -50% memory and -40% latency, enabling server models within 512 MB.

---

## 10. Improvement #8 — Enable min_height Padding

### 10.1 Rationale
RapidOCR's `min_height` parameter (default 30) automatically adds vertical padding when the input image is too short for reliable text-line detection. For product labels — which are often short and wide — raising this to 30–40 improves detection of tightly-packed text lines.

### 10.2 Implementation
**File:** `ocr/paddle_ocr_engine.py`

```python
self.engine = RapidOCR(
    min_height=32,  # default 30
    # ... other params
)
```

### 10.3 Expected Gain
+1 percentage point on compact labels with minimal memory and latency impact.

---

## 11. Priority Matrix

| # | Change | Effort | Accuracy Gain | Memory Impact | Priority |
|---|---|---|---|---|---|
| 1 | Server-side rec model | Low | +3% | +60 MB | P1 (or P2 if free tier) |
| 2 | Aggressive det params | Low | +2–4% | None | P0 (Completed) |
| 3 | Conditional CLAHE | Low | +1% | None | P2 |
| 4 | Dynamic padding | Low | +1% | Negligible | P2 |
| 5 | Targeted fallback OCR | Medium | +2% | Moderate | P1 |
| 6 | Domain corrections | Low | +1–2% | None | P1 |
| 7 | INT8 quantisation | Medium | -1% | -50% | P1 (if server model) |
| 8 | `min_height` padding | Low | +1% | None | P3 |

---

## 12. Recommended Implementation Order

### If deploying to Render free tier (512 MB RAM):
1. **Improvement #2** — Aggressive parameter tuning (*Zero cost, +2–4%* - **Done**)
2. **Improvement #6** — Domain corrections (*Zero cost, +1–2%*)
3. **Improvement #3** — Conditional CLAHE (*Zero cost, +1%*)
4. **Improvement #4** — Dynamic padding (*Zero cost, +1%*)
5. **Improvement #7** — INT8 quantisation (*Enables server models*)
6. **Improvement #1** — Server models (*Post-quantisation*)
7. **Improvement #5** — Targeted fallback OCR
8. **Improvement #8** — `min_height` padding

*Total expected gain: ~88–90% accuracy*

### If on paid plan or running locally:
1. **Improvement #1** — Server models (*Biggest single gain, +3%*)
2. **Improvement #2** — Parameter tuning (*+2–4%* - **Done**)
3. **Improvement #5** — Targeted fallback (*+2%*)
4. **Improvement #6** — Domain corrections (*+1–2%*)
5. **Improvement #3** — Conditional CLAHE (*+1%*)
6. **Improvement #4** — Dynamic padding (*+1%*)
7. **Improvement #8** — `min_height` padding (*+1%*)

*Total expected gain: ~90–92% accuracy*

---

## 13. Verification & Benchmarking

### 13.1 Test Set Setup
Create `ocr/tests/samples/` with 20–30 packaging label images covering:
- Clear, high-resolution labels (baseline)
- Small-print labels (MRP < 2 mm)
- Low-light or shadowed labels
- Curved labels (bottles, cans)
- Multi-language labels
- Labels with metallic/reflective surfaces

### 13.2 Ground Truth Specification
`ocr/tests/ground_truth.json`:
```json
{
  "sample_01.jpg": {
    "mrp": "\u20b9250.00",
    "net_quantity": "500 g",
    "manufacture_date": "03/2026",
    "country_of_origin": "India",
    "manufacturer": "ABC Foods Pvt Ltd"
  },
  "sample_02.jpg": {
    "mrp": "\u20b940.00",
    "net_quantity": "52 g",
    "manufacture_date": "08/2026",
    "country_of_origin": "India",
    "manufacturer": "XYZ Snacks Ltd"
  }
}
```

### 13.3 Benchmark Harness
**File:** `ocr/tests/benchmark.py`

```python
import json
from pathlib import Path
from ocr.pipeline import run_ocr_pipeline

def _matches(actual, expected):
    # Fuzzy match - normalise whitespace and case
    a = str(actual).strip().lower().replace(" ", "")
    e = str(expected).strip().lower().replace(" ", "")
    return a == e or e in a

def benchmark():
    gt = json.loads(Path("ocr/tests/ground_truth.json").read_text(encoding="utf-8"))
    samples_dir = Path("ocr/tests/samples")
    per_field_correct = {f: 0 for f in next(iter(gt.values()))}
    total = len(gt)

    for filename, expected in gt.items():
        image_path = samples_dir / filename
        result = run_ocr_pipeline(str(image_path))
        for field, expected_value in expected.items():
            actual = getattr(result.fields, field, None)
            if actual and _matches(actual, expected_value):
                per_field_correct[field] += 1

    print(f"Total samples: {total}")
    for field, correct in per_field_correct.items():
        pct = 100 * correct / total
        print(f"  {field:20s}: {correct}/{total} ({pct:.1f}%)")

if __name__ == "__main__":
    benchmark()
```

---

## 14. References
- RapidOCR Official Documentation — Parameter Tuning
- RapidOCR Tuning Guide (Chinese)
- PaddleOCR PP-OCRv4 Model Benchmarks
- ONNX Runtime — Quantisation
- OpenCV — Adaptive Thresholding
