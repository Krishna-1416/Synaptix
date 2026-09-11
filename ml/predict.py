"""
Inference pipeline for the Synaptix Legal Metrology BiLSTM-CRF NER model.

Pipeline:

    OCR tokens
        |
        v
    Feature extraction
        |
        v
    BiLSTM
        |
        v
    CRF decoding
        |
        v
    BIO labels
        |
        v
    Entity spans
        |
        v
    8 Rule 6 declaration fields

Supported fields:

    manufacturer
    country_of_origin
    generic_name
    net_quantity
    manufacture_date
    mrp
    unit_sale_price
    consumer_care
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

import torch

from ml.config import (
    BIO_LABELS,
    FEATURE_VOCAB_FILE,
    LABEL_MAP_FILE,
    MODEL_FILE,
)
from ml.model import BiLSTMCRFTagger
from ml.preprocessing import (
    TokenVocabulary,
    bio_spans_to_fields,
    featurize_document,
    tokens_from_text,
)

logger = logging.getLogger(
    "synaptix.ml.predict"
)


class MLPredictor:
    """
    Loads the trained BiLSTM-CRF model and performs inference.
    """

    def __init__(
        self,
        model_path: str | Path = MODEL_FILE,
        label_map_path: str | Path = LABEL_MAP_FILE,
        feature_vocab_path: str | Path = FEATURE_VOCAB_FILE,
        device: Optional[str] = None,
    ) -> None:

        self.model_path = Path(
            model_path
        )

        self.label_map_path = Path(
            label_map_path
        )

        self.feature_vocab_path = Path(
            feature_vocab_path
        )

        if device is None:

            self.device = torch.device(
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )

        else:

            self.device = torch.device(
                device
            )

        self.model: Optional[
            BiLSTMCRFTagger
        ] = None

        self.vocab: Optional[
            TokenVocabulary
        ] = None

        self.label_map: dict[int, str] = {}

        self.loaded = False

    @property
    def is_ready(self) -> bool:
        """Return True when model and vocabulary are loaded."""

        return (
            self.loaded
            and self.model is not None
            and self.vocab is not None
        )

    def load(self) -> None:
        """Load model checkpoint, labels and feature vocabulary."""

        if not self.model_path.exists():

            raise FileNotFoundError(
                f"Model file not found: "
                f"{self.model_path}"
            )

        if not self.label_map_path.exists():

            raise FileNotFoundError(
                f"Label map not found: "
                f"{self.label_map_path}"
            )

        if not self.feature_vocab_path.exists():

            raise FileNotFoundError(
                f"Feature vocabulary not found: "
                f"{self.feature_vocab_path}"
            )

        logger.info(
            "Loading model from %s",
            self.model_path,
        )

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=False,
        )

        if not isinstance(
            checkpoint,
            dict,
        ):

            raise ValueError(
                "Invalid model checkpoint format."
            )

        input_dim = int(
            checkpoint.get(
                "input_dim",
                0,
            )
        )

        hidden_dim = int(
            checkpoint.get(
                "hidden_dim",
                128,
            )
        )

        num_layers = int(
            checkpoint.get(
                "num_layers",
                2,
            )
        )

        dropout = float(
            checkpoint.get(
                "dropout",
                0.3,
            )
        )

        num_labels = int(
            checkpoint.get(
                "num_labels",
                len(BIO_LABELS),
            )
        )

        if input_dim <= 0:

            raise ValueError(
                "Invalid input_dim in model checkpoint."
            )

        if num_labels != len(BIO_LABELS):

            raise ValueError(
                "Model label count does not match "
                "current BIO_LABELS configuration: "
                f"{num_labels} != {len(BIO_LABELS)}"
            )

        self.model = BiLSTMCRFTagger(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout,
            num_labels=num_labels,
        )

        state_dict = checkpoint.get(
            "model_state_dict"
        )

        if state_dict is None:

            raise ValueError(
                "Model checkpoint does not contain "
                "'model_state_dict'."
            )

        self.model.load_state_dict(
            state_dict
        )

        self.model.to(
            self.device
        )

        self.model.eval()

        self._load_label_map()

        self.vocab = (
            TokenVocabulary.load(
                self.feature_vocab_path
            )
        )

        self.loaded = True

        logger.info(
            "ML model loaded successfully."
        )

    def _load_label_map(self) -> None:
        """Load and validate the ID-to-label mapping."""

        with open(
            self.label_map_path,
            "r",
            encoding="utf-8",
        ) as file:

            payload = json.load(
                file
            )

        id_to_label = payload.get(
            "id_to_label"
        )

        if not isinstance(
            id_to_label,
            dict,
        ):

            raise ValueError(
                "label_map.json does not contain "
                "a valid id_to_label mapping."
            )

        self.label_map = {}

        for key, value in id_to_label.items():

            self.label_map[
                int(key)
            ] = str(value)

        for index, expected_label in enumerate(
            BIO_LABELS
        ):

            actual_label = self.label_map.get(
                index
            )

            if actual_label != expected_label:

                raise ValueError(
                    "Label map mismatch at index "
                    f"{index}: expected "
                    f"'{expected_label}', got "
                    f"'{actual_label}'."
                )

    def predict_tokens(
        self,
        tokens: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Run model inference on OCR tokens.

        Expected token format:

            {
                "text": "MRP",
                "confidence": 0.98,
                "bbox": [x1, y1, x2, y2]
            }
        """

        start_time = time.perf_counter()

        if not self.is_ready:
            self.load()

        if self.model is None:

            raise RuntimeError(
                "ML model is not loaded."
            )

        if self.vocab is None:

            raise RuntimeError(
                "Feature vocabulary is not loaded."
            )

        if not tokens:

            return {
                "fields": self._empty_fields(),
                "entities": [],
                "tokens": [],
                "execution_time_ms": 0.0,
                "model": "BiLSTM-CRF",
                "status": "no_tokens",
            }

        clean_tokens = self._sanitize_tokens(
            tokens
        )

        if not clean_tokens:

            return {
                "fields": self._empty_fields(),
                "entities": [],
                "tokens": [],
                "execution_time_ms": 0.0,
                "model": "BiLSTM-CRF",
                "status": "no_valid_tokens",
            }

        features_np = featurize_document(
            tokens=clean_tokens,
            vocab=self.vocab,
        )

        if features_np.size == 0:

            return {
                "fields": self._empty_fields(),
                "entities": [],
                "tokens": [],
                "execution_time_ms": 0.0,
                "model": "BiLSTM-CRF",
                "status": "empty_features",
            }

        sequence_length = len(
            features_np
        )

        feature_tensor = torch.tensor(
            features_np,
            dtype=torch.float32,
            device=self.device,
        ).unsqueeze(0)

        mask = torch.ones(
            (1, sequence_length),
            dtype=torch.bool,
            device=self.device,
        )

        with torch.no_grad():

            emissions = self.model.emissions(
                feature_tensor,
                mask,
            )

            decoded = self.model.crf.decode(
                emissions,
                mask,
            )

        if not decoded:

            predicted_ids: list[int] = []

        else:

            predicted_ids = decoded[0]

        token_count = min(
            len(clean_tokens),
            len(predicted_ids),
        )

        prediction_tokens: list[
            dict[str, Any]
        ] = []

        bio_labels: list[str] = []

        for index in range(
            token_count
        ):

            token = clean_tokens[
                index
            ]

            label_id = int(
                predicted_ids[index]
            )

            label = self.label_map.get(
                label_id,
                "O",
            )

            confidence = self._token_confidence(
                emissions[0, index],
                label_id,
            )

            prediction_token = {
                "text": str(
                    token.get(
                        "text",
                        "",
                    )
                ),
                "confidence": round(
                    confidence,
                    6,
                ),
                "bbox": token.get(
                    "bbox"
                ),
                "label": label,
                "label_id": label_id,
                "ocr_confidence": float(
                    token.get(
                        "confidence",
                        1.0,
                    )
                ),
            }

            prediction_tokens.append(
                prediction_token
            )

            bio_labels.append(
                label
            )

        span_tokens = clean_tokens[
            :token_count
        ]

        fields = bio_spans_to_fields(
            span_tokens,
            bio_labels,
        )

        fields = self._ensure_all_fields(
            fields
        )

        entities = self._build_entities(
            fields
        )

        elapsed_ms = (
            time.perf_counter()
            - start_time
        ) * 1000.0

        return {
            "fields": fields,
            "entities": entities,
            "tokens": prediction_tokens,
            "execution_time_ms": round(
                elapsed_ms,
                3,
            ),
            "model": "BiLSTM-CRF",
            "status": "success",
            "token_count": len(
                clean_tokens
            ),
        }

    def predict_text(
        self,
        text: str,
    ) -> dict[str, Any]:
        """
        Run inference on plain text.

        This converts raw text into synthetic OCR tokens.

        For real Synaptix OCR integration, use predict_tokens()
        so real OCR confidence and bounding boxes are preserved.
        """

        if not text or not text.strip():

            return {
                "fields": self._empty_fields(),
                "entities": [],
                "tokens": [],
                "execution_time_ms": 0.0,
                "model": "BiLSTM-CRF",
                "status": "empty_text",
            }

        tokens = tokens_from_text(
            text
        )

        return self.predict_tokens(
            tokens
        )

    def _sanitize_tokens(
        self,
        tokens: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Clean OCR tokens before feature extraction."""

        cleaned: list[
            dict[str, Any]
        ] = []

        max_tokens = 512

        for token in tokens:

            if not isinstance(
                token,
                dict,
            ):
                continue

            text = str(
                token.get(
                    "text",
                    "",
                )
            ).strip()

            if not text:
                continue

            confidence = token.get(
                "confidence",
                1.0,
            )

            try:

                confidence = float(
                    confidence
                )

            except (
                TypeError,
                ValueError,
            ):

                confidence = 1.0

            confidence = max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            )

            bbox = token.get(
                "bbox"
            )

            if (
                isinstance(
                    bbox,
                    (list, tuple),
                )
                and len(bbox) == 4
            ):

                try:

                    bbox = [
                        float(value)
                        for value in bbox
                    ]

                except (
                    TypeError,
                    ValueError,
                ):

                    bbox = [
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    ]

            else:

                bbox = [
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ]

            cleaned.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox,
                }
            )

            if len(cleaned) >= max_tokens:
                break

        return cleaned

    @staticmethod
    def _token_confidence(
        emission: torch.Tensor,
        label_id: int,
    ) -> float:
        """
        Convert emission logits into the probability
        of the predicted label.
        """

        probabilities = torch.softmax(
            emission,
            dim=0,
        )

        if (
            label_id < 0
            or label_id >= probabilities.numel()
        ):

            return 0.0

        return float(
            probabilities[
                label_id
            ].item()
        )

    @staticmethod
    def _empty_fields() -> dict[str, None]:
        """Return all Rule 6 fields with empty values."""

        return {
            "manufacturer": None,
            "country_of_origin": None,
            "generic_name": None,
            "net_quantity": None,
            "manufacture_date": None,
            "mrp": None,
            "unit_sale_price": None,
            "consumer_care": None,
        }

    @classmethod
    def _ensure_all_fields(
        cls,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Ensure all eight Rule 6 fields exist."""

        result = cls._empty_fields()

        if not isinstance(
            fields,
            dict,
        ):

            return result

        for key, value in fields.items():

            if key in result:

                result[key] = value

        return result

    @staticmethod
    def _build_entities(
        fields: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Convert bio_spans_to_fields() output into
        a normalized entity list.
        """

        entities: list[
            dict[str, Any]
        ] = []

        for field_name, payload in fields.items():

            if payload is None:
                continue

            if isinstance(
                payload,
                dict,
            ):

                value = payload.get(
                    "value"
                )

                confidence = payload.get(
                    "confidence",
                    0.0,
                )

                bbox = payload.get(
                    "bbox"
                )

            else:

                value = payload
                confidence = 0.0
                bbox = None

            if value is None:
                continue

            try:

                confidence = float(
                    confidence
                )

            except (
                TypeError,
                ValueError,
            ):

                confidence = 0.0

            entities.append(
                {
                    "field_name": field_name,
                    "value": str(value),
                    "confidence": round(
                        confidence,
                        6,
                    ),
                    "source": "ml",
                    "bbox": bbox,
                }
            )

        return entities


_default_predictor: Optional[
    MLPredictor
] = None


def get_predictor() -> MLPredictor:
    """
    Return a shared lazy-loaded predictor.
    """

    global _default_predictor

    if _default_predictor is None:

        _default_predictor = MLPredictor()

    if not _default_predictor.is_ready:

        _default_predictor.load()

    return _default_predictor


def predict_tokens(
    tokens: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convenience function for OCR token inference."""

    return get_predictor().predict_tokens(
        tokens
    )


def predict_text(
    text: str,
) -> dict[str, Any]:
    """Convenience function for raw text inference."""

    return get_predictor().predict_text(
        text
    )


def _print_result(
    result: dict[str, Any],
) -> None:
    """Pretty-print inference results."""

    print()
    print(
        "=" * 60
    )

    print(
        "Synaptix BiLSTM-CRF Prediction"
    )

    print(
        "=" * 60
    )

    print(
        f"Status: {result.get('status')}"
    )

    print(
        f"Model: {result.get('model')}"
    )

    print(
        f"Tokens: {result.get('token_count', 0)}"
    )

    print(
        f"Execution: "
        f"{result.get('execution_time_ms', 0):.3f} ms"
    )

    print()
    print(
        "Extracted Fields:"
    )

    fields = result.get(
        "fields",
        {},
    )

    for field_name, value in fields.items():

        if value is None:

            print(
                f"  {field_name:<20} : NOT DETECTED"
            )

        else:

            print(
                f"  {field_name:<20} : {value}"
            )

    print()
    print(
        "BIO Predictions:"
    )

    for token in result.get(
        "tokens",
        [],
    ):

        print(
            f"  {token['text']:<30} "
            f"{token['label']:<30} "
            f"{token['confidence']:.3f}"
        )

    print()
    print(
        "=" * 60
    )


def main() -> None:
    """Command-line inference test."""

    parser = argparse.ArgumentParser(
        description=(
            "Synaptix BiLSTM-CRF inference"
        )
    )

    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Text to analyse.",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=str(
            MODEL_FILE
        ),
        help="Path to ner_model.pt.",
    )

    parser.add_argument(
        "--labels",
        type=str,
        default=str(
            LABEL_MAP_FILE
        ),
        help="Path to label_map.json.",
    )

    parser.add_argument(
        "--vocab",
        type=str,
        default=str(
            FEATURE_VOCAB_FILE
        ),
        help="Path to feature_vocab.json.",
    )

    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Torch device, e.g. cpu or cuda.",
    )

    args = parser.parse_args()

    predictor = MLPredictor(
        model_path=args.model,
        label_map_path=args.labels,
        feature_vocab_path=args.vocab,
        device=args.device,
    )

    predictor.load()

    if args.text:

        result = predictor.predict_text(
            args.text
        )

    else:

        demo_text = """
        SUNRISE FOODS PVT LTD
        CASHEW COOKIES
        NET QTY: 200 g
        MRP: Rs. 40.00
        MANUFACTURED: 05/2024
        COUNTRY OF ORIGIN: India
        UNIT SALE PRICE: Rs. 0.20/g
        CONSUMER CARE: 1800-123-4567
        """

        print(
            "No --text argument supplied."
        )

        print(
            "Running built-in demonstration..."
        )

        result = predictor.predict_text(
            demo_text
        )

    _print_result(
        result
    )


if __name__ == "__main__":
    main()