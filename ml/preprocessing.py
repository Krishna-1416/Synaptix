"""
ml/preprocessing.py
-------------------
Token-level feature extraction and BIO label encoding for the NER pipeline.

Converts raw OCR token lists (from ocr.interfaces.OCRToken or plain dicts)
into feature vectors and encoded label sequences suitable for the ML model.

No external ML dependencies beyond numpy and the standard library.
"""

from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ml.config import (
    BIO_LABELS,
    FeatureConfig,
    FIELD_TO_LABEL,
    MODELS_DIR,
    FEATURE_VOCAB_FILE,
    feature_cfg,
)

# ─── Label encoding ────────────────────────────────────────────────────────────

LABEL2ID: dict[str, int] = {label: idx for idx, label in enumerate(BIO_LABELS)}
ID2LABEL: dict[int, str] = {idx: label for label, idx in LABEL2ID.items()}
NUM_LABELS: int = len(BIO_LABELS)


def encode_label(label: str) -> int:
    """Convert a BIO label string to its integer id. Unknown → O."""
    return LABEL2ID.get(label, LABEL2ID["O"])


def decode_label(label_id: int) -> str:
    """Convert integer label id back to BIO label string."""
    return ID2LABEL.get(label_id, "O")


def label_ids_to_bio(label_ids: list[int]) -> list[str]:
    return [decode_label(i) for i in label_ids]


# ─── Token feature keywords (heuristic indicator features) ────────────────────

_MRP_KWS = frozenset(["mrp", "m.r.p", "max", "maximum", "retail", "price", "₹", "rs.", "rs", "inr"])
_QTY_KWS = frozenset(["net", "wt", "wt.", "weight", "qty", "quantity", "content", "g", "kg", "ml", "l", "ltr", "pcs"])
_DATE_KWS = frozenset(["mfd", "mfg", "pkd", "packed", "date", "on:", "manufacture", "packing"])
_MFG_KWS = frozenset(["manufactured", "mfd.", "packed", "mktd.", "marketed", "produced", "imported", "by:", "by"])
_ORIGIN_KWS = frozenset(["country", "origin", "made", "product", "manufactured", "in:"])
_CARE_KWS = frozenset(["consumer", "customer", "care", "helpline", "queries", "complaints", "feedback", "service", "toll", "free"])
_USP_KWS = frozenset(["unit", "sale", "price", "u.s.p", "usp", "/g", "/kg", "/ml", "/l", "/pcs"])

# Patterns for character-level features
_RE_HAS_DIGIT = re.compile(r"\d")
_RE_IS_ALL_CAPS = re.compile(r"^[A-Z\s\W]+$")
_RE_IS_PHONE = re.compile(r"\b\d{4,5}[\-\s]?\d{3,4}[\-\s]?\d{3,4}\b")
_RE_IS_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_RE_IS_PINCODE = re.compile(r"\b\d{6}\b")
_RE_IS_CURRENCY = re.compile(r"[₹]|(?:\b(?:rs|inr)\b\.?)", re.IGNORECASE)
_RE_IS_DATE = re.compile(r"\b\d{2}[\/\-\.]\d{2,4}\b")
_RE_IS_METRIC = re.compile(r"\b\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|l|ltr|pcs|units?|nos)\b", re.IGNORECASE)


def _tok_keyword_vector(text_lower: str) -> list[float]:
    """Returns 7-dim indicator vector: [is_mrp_kw, is_qty_kw, is_date_kw, is_mfg_kw, is_origin_kw, is_care_kw, is_usp_kw]"""
    return [
        1.0 if any(kw in text_lower for kw in _MRP_KWS) else 0.0,
        1.0 if any(kw in text_lower for kw in _QTY_KWS) else 0.0,
        1.0 if any(kw in text_lower for kw in _DATE_KWS) else 0.0,
        1.0 if any(kw in text_lower for kw in _MFG_KWS) else 0.0,
        1.0 if any(kw in text_lower for kw in _ORIGIN_KWS) else 0.0,
        1.0 if any(kw in text_lower for kw in _CARE_KWS) else 0.0,
        1.0 if any(kw in text_lower for kw in _USP_KWS) else 0.0,
    ]


def _tok_char_features(text: str, text_lower: str) -> list[float]:
    """Returns 8-dim character-level indicator vector."""
    return [
        1.0 if _RE_HAS_DIGIT.search(text) else 0.0,
        1.0 if _RE_IS_ALL_CAPS.match(text) else 0.0,
        1.0 if _RE_IS_PHONE.search(text) else 0.0,
        1.0 if _RE_IS_EMAIL.search(text) else 0.0,
        1.0 if _RE_IS_PINCODE.search(text) else 0.0,
        1.0 if _RE_IS_CURRENCY.search(text) else 0.0,
        1.0 if _RE_IS_DATE.search(text) else 0.0,
        1.0 if _RE_IS_METRIC.search(text) else 0.0,
    ]


def _normalize_bbox(bbox: list, img_w: float = 1000.0, img_h: float = 1000.0) -> list[float]:
    """Normalize bounding box to [0,1] range given estimated image dims."""
    if not bbox or len(bbox) != 4:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    x0, y0, x1, y1 = bbox
    cx = ((x0 + x1) / 2) / img_w
    cy = ((y0 + y1) / 2) / img_h
    w = (x1 - x0) / img_w
    h = (y1 - y0) / img_h
    return [
        max(0.0, min(1.0, cx)),
        max(0.0, min(1.0, cy)),
        max(0.0, min(1.0, w)),
        max(0.0, min(1.0, h)),
        max(0.0, min(1.0, x0 / img_w)),
        max(0.0, min(1.0, y0 / img_h)),
    ]


# ─── Vocabulary ────────────────────────────────────────────────────────────────

class TokenVocabulary:
    """
    Simple unigram character-n-gram vocabulary for token-level lookup features.
    Supports save/load from JSON for reproducible inference.
    """

    def __init__(self, max_size: int = 2000) -> None:
        self.max_size = max_size
        self._word2id: dict[str, int] = {"<PAD>": 0, "<UNK>": 1}
        self._next_id = 2
        self.frozen = False

    @property
    def size(self) -> int:
        return len(self._word2id)

    def add(self, token: str) -> int:
        token_norm = token.strip().lower()[:20]  # Cap length
        if token_norm not in self._word2id and not self.frozen:
            if self._next_id < self.max_size:
                self._word2id[token_norm] = self._next_id
                self._next_id += 1
        return self._word2id.get(token_norm, 1)  # 1 = <UNK>

    def lookup(self, token: str) -> int:
        token_norm = token.strip().lower()[:20]
        return self._word2id.get(token_norm, 1)

    def freeze(self) -> None:
        self.frozen = True

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"vocab": self._word2id, "next_id": self._next_id}, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> TokenVocabulary:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        vocab = cls()
        vocab._word2id = data["vocab"]
        vocab._next_id = data.get("next_id", len(vocab._word2id))
        vocab.frozen = True
        return vocab


# ─── Feature extraction ────────────────────────────────────────────────────────

def extract_token_features(
    token: dict[str, Any],
    vocab: Optional[TokenVocabulary],
    cfg: FeatureConfig = feature_cfg,
    img_w: float = 1000.0,
    img_h: float = 1000.0,
) -> list[float]:
    """
    Build feature vector for a single token dict (keys: text, confidence, bbox).

    Returns a 1-D list of floats:
      [vocab_lookup (1), char_features (8), keyword_features (7), bbox_features (6), confidence (1)]
      = 23 features per token

    If vocab is None, vocab_lookup is skipped (22 features).
    """
    text = str(token.get("text", ""))
    text_lower = text.lower()
    confidence = float(token.get("confidence", 1.0))
    bbox = token.get("bbox", [])

    features: list[float] = []

    # 1. Vocabulary lookup (embedded as float index — used as additional indicator)
    if vocab is not None:
        tok_id = vocab.lookup(text)
        features.append(float(tok_id) / max(1.0, float(vocab.size)))

    # 2. Character-level features (8-dim)
    if cfg.use_char_features:
        features.extend(_tok_char_features(text, text_lower))

    # 3. Keyword indicator features (7-dim)
    if cfg.use_keyword_features:
        features.extend(_tok_keyword_vector(text_lower))

    # 4. Bounding box spatial features (6-dim)
    if cfg.use_positional_features:
        features.extend(_normalize_bbox(bbox, img_w, img_h))

    # 5. Confidence score (1-dim)
    features.append(max(0.0, min(1.0, confidence)))

    return features


def featurize_document(
    tokens: list[dict[str, Any]],
    vocab: Optional[TokenVocabulary],
    cfg: FeatureConfig = feature_cfg,
) -> np.ndarray:
    """
    Featurize a document's token list into a 2-D numpy array of shape (T, F).
    T = number of tokens (capped at cfg.max_doc_tokens), F = feature dimension.
    """
    if not tokens:
        return np.zeros((1, _get_feature_dim(vocab, cfg)), dtype=np.float32)

    # Estimate image dimensions from bounding boxes
    bboxes = [t.get("bbox", [0, 0, 0, 0]) for t in tokens]
    img_w = float(max((b[2] for b in bboxes if len(b) == 4), default=1000))
    img_h = float(max((b[3] for b in bboxes if len(b) == 4), default=1000))
    img_w = max(img_w, 100.0)
    img_h = max(img_h, 100.0)

    tokens_capped = tokens[:cfg.max_doc_tokens]
    feat_list = [
        extract_token_features(tok, vocab, cfg, img_w=img_w, img_h=img_h)
        for tok in tokens_capped
    ]
    return np.array(feat_list, dtype=np.float32)


def _get_feature_dim(vocab: Optional[TokenVocabulary], cfg: FeatureConfig) -> int:
    """Calculate feature vector dimensionality from config."""
    dim = 0
    if vocab is not None:
        dim += 1           # vocab lookup
    if cfg.use_char_features:
        dim += 8
    if cfg.use_keyword_features:
        dim += 7
    if cfg.use_positional_features:
        dim += 6
    dim += 1               # confidence
    return dim


# ─── Dataset preparation ──────────────────────────────────────────────────────

def prepare_dataset_from_fixtures(
    fixtures: list[dict[str, Any]],
    vocab: Optional[TokenVocabulary] = None,
    build_vocab: bool = True,
    cfg: FeatureConfig = feature_cfg,
) -> tuple[list[np.ndarray], list[list[int]], TokenVocabulary]:
    """
    Converts a list of fixture documents into featurized arrays and encoded label sequences.

    Returns:
        X: list of shape-(T, F) numpy arrays (one per document)
        y: list of integer label id lists (one per document)
        vocab: Built or updated TokenVocabulary
    """
    if vocab is None:
        vocab = TokenVocabulary()

    if build_vocab:
        for fixture in fixtures:
            for tok in fixture.get("tokens", []):
                vocab.add(tok.get("text", ""))
        vocab.freeze()

    X: list[np.ndarray] = []
    y: list[list[int]] = []

    for fixture in fixtures:
        tokens = fixture.get("tokens", [])
        if not tokens:
            continue

        token_dicts = [{"text": t["text"], "confidence": 1.0, "bbox": t.get("bbox", [])} for t in tokens]
        feat_arr = featurize_document(token_dicts, vocab, cfg)

        label_ids = [encode_label(tok.get("label", "O")) for tok in tokens[:cfg.max_doc_tokens]]
        # Pad labels to match token count if needed
        while len(label_ids) < feat_arr.shape[0]:
            label_ids.append(LABEL2ID["O"])

        X.append(feat_arr)
        y.append(label_ids)

    return X, y, vocab


def tokens_from_text(text: str) -> list[dict[str, Any]]:
    """
    Convert raw multiline text into synthetic token dicts with synthetic bbox coordinates.
    Used for inference when only raw OCR text (no bboxes) is available.
    """
    tokens = []
    for line_idx, line in enumerate(text.splitlines()):
        words = line.strip().split()
        x_offset = 10
        y_top = line_idx * 25
        for word in words:
            width = len(word) * 9
            tokens.append({
                "text": word,
                "confidence": 1.0,
                "bbox": [x_offset, y_top, x_offset + width, y_top + 20],
            })
            x_offset += width + 6
    return tokens


def bio_spans_to_fields(
    tokens: list[dict[str, Any]],
    bio_labels: list[str],
    min_confidence: float = 0.0,
    token_confidences: Optional[list[float]] = None,
) -> dict[str, Any]:
    """
    Convert BIO label sequence into field extraction results by merging contiguous entity spans.

    Returns:
        dict mapping field_name → {"value": str, "confidence": float, "bbox": list|None}
    """
    from ml.config import LABEL_TO_FIELD

    if token_confidences is None:
        token_confidences = [1.0] * len(bio_labels)

    results: dict[str, dict] = {}
    i = 0
    n = min(len(tokens), len(bio_labels))

    while i < n:
        label = bio_labels[i]
        if label.startswith("B-"):
            entity_type = label[2:]
            field_name = LABEL_TO_FIELD.get(entity_type)
            if field_name is None:
                i += 1
                continue

            # Collect the full span
            span_texts = [tokens[i]["text"]]
            span_confs = [token_confidences[i]]
            span_bboxes = [tokens[i].get("bbox")]

            j = i + 1
            while j < n and bio_labels[j] == f"I-{entity_type}":
                span_texts.append(tokens[j]["text"])
                span_confs.append(token_confidences[j])
                span_bboxes.append(tokens[j].get("bbox"))
                j += 1

            entity_value = " ".join(span_texts)
            entity_conf = sum(span_confs) / len(span_confs)

            if entity_conf >= min_confidence:
                # Merge bboxes into one enclosing box
                valid_bboxes = [b for b in span_bboxes if b and len(b) == 4]
                merged_bbox = None
                if valid_bboxes:
                    merged_bbox = [
                        min(b[0] for b in valid_bboxes),
                        min(b[1] for b in valid_bboxes),
                        max(b[2] for b in valid_bboxes),
                        max(b[3] for b in valid_bboxes),
                    ]

                # Keep the highest-confidence prediction per field
                if field_name not in results or entity_conf > results[field_name]["confidence"]:
                    results[field_name] = {
                        "value": entity_value,
                        "confidence": round(entity_conf, 4),
                        "bbox": merged_bbox,
                    }
            i = j
        else:
            i += 1

    return results
