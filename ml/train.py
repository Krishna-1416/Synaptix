"""
Training pipeline for the Synaptix Legal Metrology BiLSTM-CRF NER model.

The current training data is the synthetic fixture dataset in:
    ml/datasets/fixtures.py

Each fixture token already contains its BIO label.

Expected model input:
    (batch, sequence_length, feature_dimension)

Document examples are stored internally as:
    features: (sequence_length, feature_dimension)
    targets:  (sequence_length,)
    mask:     (sequence_length,)

The training loop adds the batch dimension before calling the model.
"""

from __future__ import annotations

import json
import random
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ml.config import (
    BIO_LABELS,
    LABEL_TO_FIELD,
    feature_cfg,
    model_cfg,
    training_cfg,
    MODELS_DIR,
)
from ml.datasets.fixtures import SYNTHETIC_FIXTURES
from ml.model import BiLSTMCRFTagger
from ml.preprocessing import (
    TokenVocabulary,
    _get_feature_dim,
    featurize_document,
)


DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


def set_seed(seed: int) -> None:
    """Set random seeds for reproducible training."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _fixture_tokens(
    fixture: Any,
) -> list[dict[str, Any]]:
    """Extract token dictionaries from one fixture."""

    if isinstance(fixture, dict):

        tokens = fixture.get("tokens")

        if isinstance(tokens, list):

            return [
                token
                for token in tokens
                if isinstance(token, dict)
            ]

    return []


def _fixture_labels(
    tokens: list[dict[str, Any]],
) -> list[str]:
    """
    Read BIO labels directly from fixture tokens.

    The fixture dataset is already manually labelled, so there is
    no need to regenerate labels using heuristics.
    """

    labels: list[str] = []

    valid_labels = set(BIO_LABELS)

    for token in tokens:

        label = str(
            token.get(
                "label",
                "O",
            )
        ).strip()

        if label not in valid_labels:

            warnings.warn(
                f"Unknown BIO label '{label}'. "
                f"Replacing with O."
            )

            label = "O"

        labels.append(label)

    return labels


def validate_bio_sequences(
    labels: list[str],
) -> None:
    """
    Validate BIO label transitions.

    An I-X token must immediately follow B-X or I-X.
    """

    previous_entity: str | None = None

    for index, label in enumerate(labels):

        if label == "O":
            previous_entity = None
            continue

        if label.startswith("B-"):

            previous_entity = label[2:]
            continue

        if label.startswith("I-"):

            entity = label[2:]

            if previous_entity != entity:

                raise ValueError(
                    "Invalid BIO sequence at token "
                    f"{index}: '{label}' does not follow "
                    f"B-{entity}/I-{entity}."
                )

            previous_entity = entity
            continue

        raise ValueError(
            f"Invalid BIO label at token {index}: {label}"
        )


def load_training_data(
) -> list[
    tuple[
        list[dict[str, Any]],
        list[str],
    ]
]:
    """
    Load labelled training documents from synthetic fixtures.

    Returns:
        [
            (
                tokens,
                labels,
            ),
            ...
        ]
    """

    dataset: list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ] = []

    for fixture in SYNTHETIC_FIXTURES:

        tokens = _fixture_tokens(
            fixture
        )

        if not tokens:
            continue

        labels = _fixture_labels(
            tokens
        )

        if len(tokens) != len(labels):

            raise ValueError(
                "Token/label length mismatch: "
                f"{len(tokens)} tokens vs "
                f"{len(labels)} labels."
            )

        validate_bio_sequences(
            labels
        )

        dataset.append(
            (
                tokens,
                labels,
            )
        )

    return dataset


def build_vocabulary(
    dataset: list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ],
) -> TokenVocabulary:
    """Build token vocabulary from training documents."""

    vocab = TokenVocabulary(
        max_size=2000
    )

    for tokens, _ in dataset:

        for token in tokens:

            text = str(
                token.get(
                    "text",
                    "",
                )
            )

            vocab.add(
                text
            )

    vocab.freeze()

    return vocab


def split_dataset(
    dataset: list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ],
) -> tuple[
    list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ],
    list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ],
    list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ],
]:
    """Split dataset into train, validation and test sets."""

    data = list(dataset)

    random.shuffle(
        data
    )

    total = len(data)

    if total < 3:

        raise ValueError(
            "At least 3 documents are required "
            "for train/validation/test splitting."
        )

    train_count = max(
        1,
        int(
            total
            * training_cfg.train_split
        ),
    )

    val_count = max(
        1,
        int(
            total
            * training_cfg.val_split
        ),
    )

    if train_count + val_count >= total:

        train_count = total - 2
        val_count = 1

    test_count = (
        total
        - train_count
        - val_count
    )

    if test_count < 1:

        test_count = 1
        train_count -= 1

    train_data = data[
        :train_count
    ]

    val_data = data[
        train_count:
        train_count + val_count
    ]

    test_data = data[
        train_count + val_count:
    ]

    return (
        train_data,
        val_data,
        test_data,
    )


def prepare_examples(
    dataset: list[
        tuple[
            list[dict[str, Any]],
            list[str],
        ]
    ],
    vocab: TokenVocabulary,
) -> list[
    tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]
]:
    """
    Convert token dictionaries into tensors.

    Returns per-document tensors:

        features:
            (sequence_length, feature_dimension)

        targets:
            (sequence_length,)

        mask:
            (sequence_length,)
    """

    examples: list[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ] = []

    label_to_id = {
        label: index
        for index, label
        in enumerate(BIO_LABELS)
    }

    for tokens, labels in dataset:

        features_np = featurize_document(
            tokens=tokens,
            vocab=vocab,
            cfg=feature_cfg,
        )

        if len(tokens) > feature_cfg.max_doc_tokens:

            tokens = tokens[
                :feature_cfg.max_doc_tokens
            ]

            labels = labels[
                :feature_cfg.max_doc_tokens
            ]

        labels = labels[
            :len(features_np)
        ]

        feature_tensor = torch.tensor(
            features_np,
            dtype=torch.float32,
        )

        target_ids = [
            label_to_id.get(
                label,
                label_to_id["O"],
            )
            for label in labels
        ]

        target_tensor = torch.tensor(
            target_ids,
            dtype=torch.long,
        )

        mask_tensor = torch.ones(
            len(target_ids),
            dtype=torch.bool,
        )

        if feature_tensor.size(0) != target_tensor.size(0):

            raise ValueError(
                "Feature/target sequence length mismatch: "
                f"{feature_tensor.size(0)} features vs "
                f"{target_tensor.size(0)} targets."
            )

        examples.append(
            (
                feature_tensor,
                target_tensor,
                mask_tensor,
            )
        )

    return examples


def compute_loss(
    model: BiLSTMCRFTagger,
    examples: list[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ],
    optimizer: torch.optim.Optimizer | None = None,
) -> float:
    """
    Compute average loss for document-level examples.

    Stored document shape:

        features:
            (sequence_length, feature_dimension)

        targets:
            (sequence_length,)

        mask:
            (sequence_length,)

    The model requires:

        features:
            (batch, sequence_length, feature_dimension)

        targets:
            (batch, sequence_length)

        mask:
            (batch, sequence_length)

    Therefore every document receives a temporary batch dimension
    using unsqueeze(0).
    """

    if not examples:
        return 0.0

    training = optimizer is not None

    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0

    context = (
        torch.enable_grad()
        if training
        else torch.no_grad()
    )

    with context:

        for features, targets, mask in examples:

            features = features.to(
                DEVICE
            )

            targets = targets.to(
                DEVICE
            )

            mask = mask.to(
                DEVICE
            )

            # --------------------------------------------------
            # Add batch dimension.
            #
            # Before:
            #     features = (T, F)
            #
            # After:
            #     features = (1, T, F)
            # --------------------------------------------------

            features = features.unsqueeze(
                0
            )

            targets = targets.unsqueeze(
                0
            )

            mask = mask.unsqueeze(
                0
            )

            if training:

                optimizer.zero_grad()

            loss = model(
                features,
                tags=targets,
                mask=mask,
            )

            if not torch.isfinite(
                loss
            ):

                raise RuntimeError(
                    "Non-finite loss detected during training. "
                    "Check BIO labels, sequence lengths, "
                    "and CRF constraints."
                )

            if training:

                loss.backward()

                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    training_cfg.max_grad_norm,
                )

                optimizer.step()

            total_loss += float(
                loss.detach().cpu()
            )

    return (
        total_loss
        / len(examples)
    )


def save_artifacts(
    model: BiLSTMCRFTagger,
    vocab: TokenVocabulary,
) -> None:
    """Save trained model and preprocessing artifacts."""

    MODELS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_path = (
        MODELS_DIR
        / "ner_model.pt"
    )

    label_map_path = (
        MODELS_DIR
        / "label_map.json"
    )

    vocab_path = (
        MODELS_DIR
        / "feature_vocab.json"
    )

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "input_dim": model.input_dim,
        "hidden_dim": model.hidden_dim,
        "num_layers": model.num_layers,
        "dropout": model.dropout_value,
        "num_labels": model.num_labels,
        "bio_labels": BIO_LABELS,
    }

    torch.save(
        checkpoint,
        model_path,
    )

    with open(
        label_map_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "label_to_id": {
                    label: index
                    for index, label
                    in enumerate(BIO_LABELS)
                },
                "id_to_label": {
                    str(index): label
                    for index, label
                    in enumerate(BIO_LABELS)
                },
            },
            file,
            indent=2,
        )

    vocab.save(
        vocab_path
    )

    print()
    print(
        "Artifacts saved:"
    )

    print(
        f"  Model : {model_path}"
    )

    print(
        f"  Labels: {label_map_path}"
    )

    print(
        f"  Vocab : {vocab_path}"
    )


def evaluate_model(
    model: BiLSTMCRFTagger,
    examples: list[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ],
) -> float:
    """Calculate average evaluation loss."""

    return compute_loss(
        model=model,
        examples=examples,
        optimizer=None,
    )


def main() -> None:

    print(
        "=" * 60
    )

    print(
        "Synaptix BiLSTM-CRF Training"
    )

    print(
        "=" * 60
    )

    set_seed(
        training_cfg.random_seed
    )

    print(
        f"Device: {DEVICE}"
    )

    dataset = load_training_data()

    if not dataset:

        raise RuntimeError(
            "No training documents were found."
        )

    print(
        f"Documents: {len(dataset)}"
    )

    train_data, val_data, test_data = (
        split_dataset(dataset)
    )

    print(
        f"Train: {len(train_data)}"
    )

    print(
        f"Validation: {len(val_data)}"
    )

    print(
        f"Test: {len(test_data)}"
    )

    print()

    print(
        "WARNING: Current dataset is synthetic."
    )

    print(
        "Training metrics are development metrics only."
    )

    print()

    vocab = build_vocabulary(
        dataset
    )

    train_examples = prepare_examples(
        train_data,
        vocab,
    )

    val_examples = prepare_examples(
        val_data,
        vocab,
    )

    test_examples = prepare_examples(
        test_data,
        vocab,
    )

    feature_dim = _get_feature_dim(
        vocab=vocab,
        cfg=feature_cfg,
    )

    print(
        f"Feature dimension: {feature_dim}"
    )

    model = BiLSTMCRFTagger(
        input_dim=feature_dim,
        hidden_dim=model_cfg.hidden_dim,
        num_layers=model_cfg.num_layers,
        dropout=model_cfg.dropout,
        num_labels=len(BIO_LABELS),
    ).to(
        DEVICE
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=training_cfg.learning_rate,
        weight_decay=training_cfg.weight_decay,
    )

    best_val_loss = float(
        "inf"
    )

    best_state = None

    epochs_without_improvement = 0

    for epoch in range(
        1,
        training_cfg.epochs + 1,
    ):

        train_loss = compute_loss(
            model=model,
            examples=train_examples,
            optimizer=optimizer,
        )

        val_loss = evaluate_model(
            model=model,
            examples=val_examples,
        )

        print(
            f"Epoch {epoch:02d}/"
            f"{training_cfg.epochs} | "
            f"Train Loss: {train_loss:.6f} | "
            f"Val Loss: {val_loss:.6f}"
        )

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            best_state = {
                key: value.detach().cpu().clone()
                for key, value
                in model.state_dict().items()
            }

            epochs_without_improvement = 0

        else:

            epochs_without_improvement += 1

        if (
            epoch >= training_cfg.min_epochs
            and epochs_without_improvement
            >= training_cfg.early_stopping_patience
        ):

            print(
                "Early stopping triggered."
            )

            break

    if best_state is not None:

        model.load_state_dict(
            best_state
        )

        model.to(
            DEVICE
        )

    test_loss = evaluate_model(
        model=model,
        examples=test_examples,
    )

    print()

    print(
        "=" * 60
    )

    print(
        "Training Complete"
    )

    print(
        "=" * 60
    )

    print(
        f"Best Validation Loss: "
        f"{best_val_loss:.6f}"
    )

    print(
        f"Test Loss: "
        f"{test_loss:.6f}"
    )

    save_artifacts(
        model=model,
        vocab=vocab,
    )

    print()

    print(
        "Supported fields:"
    )

    for field_name in LABEL_TO_FIELD.values():

        print(
            f"  - {field_name}"
        )

    print()

    print(
        "Next step: connect the saved model "
        "to ml/predict.py and MLEntityExtractor."
    )


if __name__ == "__main__":
    main()