"""
ML Subsystem Configuration for Synaptix (Phase 2).

All tunable hyperparameters, path settings, and training configurations
live here. Import this module instead of hardcoding values.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ─── Paths ────────────────────────────────────────────────────────────────────

ML_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ML_DIR.parent
MODELS_DIR = ML_DIR / "models"
DATASETS_DIR = ML_DIR / "datasets"

# Canonical model artifact filename
MODEL_FILE = MODELS_DIR / "ner_model.pt"
LABEL_MAP_FILE = MODELS_DIR / "label_map.json"
FEATURE_VOCAB_FILE = MODELS_DIR / "feature_vocab.json"

# ─── BIO Label Set ────────────────────────────────────────────────────────────

# 8 statutory Rule 6 fields → 17 BIO tags + O
ENTITY_FIELDS = (
    "MANUFACTURER",
    "COUNTRY",
    "GENERIC_NAME",
    "NET_QUANTITY",
    "MANUFACTURE_DATE",
    "MRP",
    "UNIT_SALE_PRICE",
    "CONSUMER_CARE",
)

# Maps canonical field names (as used in schemas.py) to label prefixes
FIELD_TO_LABEL: dict[str, str] = {
    "manufacturer": "MANUFACTURER",
    "country_of_origin": "COUNTRY",
    "generic_name": "GENERIC_NAME",
    "net_quantity": "NET_QUANTITY",
    "manufacture_date": "MANUFACTURE_DATE",
    "mrp": "MRP",
    "unit_sale_price": "UNIT_SALE_PRICE",
    "consumer_care": "CONSUMER_CARE",
}

LABEL_TO_FIELD: dict[str, str] = {v: k for k, v in FIELD_TO_LABEL.items()}

# Build sorted BIO label list: O + B-X + I-X for each entity field
BIO_LABELS: list[str] = ["O"] + [
    tag
    for ent in ENTITY_FIELDS
    for tag in (f"B-{ent}", f"I-{ent}")
]

# ─── Feature Engineering ──────────────────────────────────────────────────────

@dataclass
class FeatureConfig:
    """Token feature extraction settings."""
    max_token_length: int = 50          # Max chars per token to consider
    use_positional_features: bool = True # Include normalized (x, y, w, h) bbox features
    use_char_features: bool = True       # Include character-level indicators
    use_keyword_features: bool = True    # Include Legal Metrology keyword matching
    use_context_window: int = 2          # ±N tokens of context around each token
    max_doc_tokens: int = 512            # Truncate documents at this many tokens


# ─── Model Architecture ───────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """BiLSTM-CRF sequence tagger hyperparameters."""
    input_dim: int = 128                # Will be set dynamically from feature size
    hidden_dim: int = 256               # BiLSTM hidden units (per direction)
    num_layers: int = 2                 # BiLSTM stacking depth
    dropout: float = 0.3               # Dropout probability
    num_labels: int = len(BIO_LABELS)  # Set from BIO_LABELS length
    use_crf: bool = True               # Use CRF decode layer


# ─── Training ─────────────────────────────────────────────────────────────────

@dataclass
class TrainingConfig:
    """Training loop hyperparameters."""
    epochs: int = 30
    batch_size: int = 8
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    max_grad_norm: float = 5.0
    train_split: float = 0.70
    val_split: float = 0.15
    test_split: float = 0.15
    random_seed: int = 42
    early_stopping_patience: int = 6
    min_epochs: int = 5


# ─── Inference ────────────────────────────────────────────────────────────────

@dataclass
class InferenceConfig:
    """Inference / prediction settings."""
    model_path: Path = MODEL_FILE
    label_map_path: Path = LABEL_MAP_FILE
    feature_vocab_path: Path = FEATURE_VOCAB_FILE
    # Minimum token-level probability before an entity is accepted
    min_entity_confidence: float = 0.50
    # Regex always overrides ML for these fields (strict numeric/date format)
    regex_precedence_fields: tuple[str, ...] = (
        "mrp", "net_quantity", "manufacture_date", "unit_sale_price"
    )


# ─── Default instances ────────────────────────────────────────────────────────

feature_cfg = FeatureConfig()
model_cfg = ModelConfig()
training_cfg = TrainingConfig()
inference_cfg = InferenceConfig()
