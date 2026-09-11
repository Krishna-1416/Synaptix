# ML Models & Architecture Roadmap

## Purpose

This directory will store model checkpoints, configuration artifacts, and exported ONNX runtimes for the Synaptix ML subsystem.

In Phase 1, **no model weights, binary checkpoints, or large pre-trained weights are committed**.

---

## Phase 1 Status

- The existing system uses deterministic regex extraction (`ocr/field_extractor.py`) wrapped by the `RegexEntityExtractorAdapter`.
- The `MLEntityExtractor` class in `ml/entity_extractor.py` provides the exact interface contract for Phase 2.
- The `HybridEntityExtractor` class defines the conflict-resolution and arbitration policy between regex rules and ML model predictions.

---

## Phase 2 Candidate Model Architectures

### 1. Multimodal Document Understanding: LayoutLMv3 / LayoutXLM
- **Input**: Token image crops, 2D bounding boxes `[x0, y0, x1, y1]`, and OCR recognized text.
- **Strength**: Understands spatial relationships on complex package panels (e.g., text under "Manufactured By:" or within statutory borders).
- **Multi-lingual**: LayoutXLM supports English, Hindi, and Indian regional languages common on domestic packaging.

### 2. OCR-Free Vision-to-Text: Donut (Document Understanding Transformer)
- **Input**: Raw package image directly without intermediate OCR.
- **Strength**: Immune to OCR tokenization errors.
- **Tradeoff**: Higher compute requirements and slower latency.

### 3. Lightweight Token Classifier: DistilRoBERTa-NER
- **Input**: Normalized text lines produced by `ocr/normalizer.py`.
- **Strength**: High speed (< 20ms per inspection), low memory (< 300MB), runnable on CPU without GPU acceleration.
- **Role**: Ideal fallback when full multimodal models cannot run on low-tier hardware.

---

## Model Deployment & Optimization Strategy

Before committing models to production:
1. **ONNX Export & Quantization**:
   - Convert PyTorch models to ONNX FP16 / INT8.
   - Run inference using `onnxruntime` to achieve sub-50ms latency.
2. **Confidence Calibration**:
   - Calibrate output probabilities so that scores between 0.0 and 1.0 reliably represent probability of correctness.
3. **Weight Storage**:
   - Model weights (> 50MB) must NOT be committed to git directly.
   - Use Git LFS, Hugging Face Hub, or an S3/GCS model registry bucket with automated caching.
