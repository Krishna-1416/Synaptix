"""
BiLSTM-CRF sequence tagger for Synaptix Legal Metrology NER.

Input:
    (batch, sequence_length, feature_dimension)

Output:
    BIO label predictions for the 8 Rule 6 declaration fields.

The CRF is implemented locally, so no additional CRF dependency is required.
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn

from ml.config import BIO_LABELS


class LinearChainCRF(nn.Module):
    """Linear-chain CRF with BIO transition constraints."""

    def __init__(self, num_labels: int) -> None:
        super().__init__()

        self.num_labels = num_labels

        self.start_transitions = nn.Parameter(
            torch.zeros(num_labels)
        )

        self.end_transitions = nn.Parameter(
            torch.zeros(num_labels)
        )

        self.transitions = nn.Parameter(
            torch.zeros(num_labels, num_labels)
        )

        self.register_buffer(
            "transition_mask",
            self._build_transition_mask(num_labels),
        )

        self.register_buffer(
            "start_mask",
            self._build_start_mask(num_labels),
        )

    @staticmethod
    def _build_transition_mask(num_labels: int) -> torch.Tensor:
        labels = BIO_LABELS[:num_labels]

        mask = torch.full(
            (num_labels, num_labels),
            float("-inf"),
        )

        for from_id, from_label in enumerate(labels):
            for to_id, to_label in enumerate(labels):

                if to_label == "O":
                    mask[from_id, to_id] = 0.0
                    continue

                if to_label.startswith("B-"):
                    mask[from_id, to_id] = 0.0
                    continue

                if to_label.startswith("I-"):
                    entity = to_label[2:]

                    if from_label == f"B-{entity}":
                        mask[from_id, to_id] = 0.0

                    elif from_label == f"I-{entity}":
                        mask[from_id, to_id] = 0.0

        return mask

    @staticmethod
    def _build_start_mask(num_labels: int) -> torch.Tensor:
        labels = BIO_LABELS[:num_labels]

        mask = torch.full(
            (num_labels,),
            float("-inf"),
        )

        for idx, label in enumerate(labels):
            if label == "O" or label.startswith("B-"):
                mask[idx] = 0.0

        return mask

    def _constrained_transitions(self) -> torch.Tensor:
        return self.transitions + self.transition_mask

    def _constrained_start(self) -> torch.Tensor:
        return self.start_transitions + self.start_mask

    def _compute_log_partition(
        self,
        emissions: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        batch_size, sequence_length, _ = emissions.shape

        del batch_size

        score = (
            self._constrained_start().unsqueeze(0)
            + emissions[:, 0]
        )

        transitions = self._constrained_transitions()

        for timestep in range(1, sequence_length):

            next_score = (
                score.unsqueeze(2)
                + transitions.unsqueeze(0)
                + emissions[:, timestep].unsqueeze(1)
            )

            next_score = torch.logsumexp(
                next_score,
                dim=1,
            )

            active = mask[:, timestep].unsqueeze(1)

            score = torch.where(
                active,
                next_score,
                score,
            )

        score = score + self.end_transitions.unsqueeze(0)

        return torch.logsumexp(
            score,
            dim=1,
        )

    def _compute_gold_score(
        self,
        emissions: torch.Tensor,
        tags: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:

        first_tags = tags[:, 0]

        start = self._constrained_start()

        score = start.gather(
            0,
            first_tags,
        )

        first_emission = emissions[:, 0].gather(
            1,
            first_tags.unsqueeze(1),
        ).squeeze(1)

        score = score + first_emission

        transitions = self._constrained_transitions()

        sequence_length = emissions.size(1)

        for timestep in range(1, sequence_length):

            previous_tags = tags[:, timestep - 1]
            current_tags = tags[:, timestep]

            transition_score = transitions[
                previous_tags,
                current_tags,
            ]

            emission_score = emissions[:, timestep].gather(
                1,
                current_tags.unsqueeze(1),
            ).squeeze(1)

            active = mask[:, timestep]

            score = score + (
                transition_score + emission_score
            ) * active

        lengths = mask.long().sum(dim=1)

        last_indices = lengths - 1

        last_tags = tags.gather(
            1,
            last_indices.unsqueeze(1),
        ).squeeze(1)

        score = score + self.end_transitions[last_tags]

        return score

    def neg_log_likelihood(
        self,
        emissions: torch.Tensor,
        tags: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:

        partition = self._compute_log_partition(
            emissions,
            mask,
        )

        gold_score = self._compute_gold_score(
            emissions,
            tags,
            mask,
        )

        return (partition - gold_score).mean()

    def decode(
        self,
        emissions: torch.Tensor,
        mask: torch.Tensor,
    ) -> list[list[int]]:

        batch_size, sequence_length, _ = emissions.shape

        transitions = self._constrained_transitions()

        score = (
            self._constrained_start().unsqueeze(0)
            + emissions[:, 0]
        )

        history: list[torch.Tensor] = []

        for timestep in range(1, sequence_length):

            next_score = (
                score.unsqueeze(2)
                + transitions.unsqueeze(0)
            )

            best_score, best_path = next_score.max(
                dim=1
            )

            best_score = (
                best_score
                + emissions[:, timestep]
            )

            active = mask[:, timestep].unsqueeze(1)

            score = torch.where(
                active,
                best_score,
                score,
            )

            history.append(best_path)

        score = score + self.end_transitions

        _, best_last_tag = score.max(
            dim=1
        )

        lengths = mask.long().sum(dim=1).tolist()

        decoded: list[list[int]] = []

        for batch_index in range(batch_size):

            length = int(lengths[batch_index])

            if length <= 0:
                decoded.append([])
                continue

            last_tag = int(
                best_last_tag[
                    batch_index
                ].item()
            )

            path = [last_tag]

            for timestep in range(
                length - 1,
                0,
                -1,
            ):

                previous_tag = history[
                    timestep - 1
                ][
                    batch_index,
                    path[-1],
                ]

                path.append(
                    int(previous_tag.item())
                )

            path.reverse()

            decoded.append(path)

        return decoded

    def forward(
        self,
        emissions: torch.Tensor,
        tags: Optional[torch.Tensor] = None,
        mask: Optional[torch.Tensor] = None,
    ):
        if mask is None:
            mask = torch.ones(
                emissions.shape[:2],
                dtype=torch.bool,
                device=emissions.device,
            )

        if tags is not None:
            return self.neg_log_likelihood(
                emissions,
                tags,
                mask,
            )

        return self.decode(
            emissions,
            mask,
        )


class BiLSTMCRFTagger(nn.Module):
    """BiLSTM encoder followed by a linear-chain CRF."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        num_labels: int = len(BIO_LABELS),
    ) -> None:
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout_value = dropout
        self.num_labels = num_labels

        lstm_dropout = (
            dropout
            if num_layers > 1
            else 0.0
        )

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=lstm_dropout,
        )

        self.dropout = nn.Dropout(dropout)

        self.emission_layer = nn.Linear(
            hidden_dim * 2,
            num_labels,
        )

        self.crf = LinearChainCRF(
            num_labels
        )

    def emissions(
        self,
        features: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:

        lengths = None

        if mask is not None:
            lengths = (
                mask.long()
                .sum(dim=1)
                .cpu()
            )

        if lengths is not None:

            packed = (
                nn.utils.rnn.pack_padded_sequence(
                    features,
                    lengths,
                    batch_first=True,
                    enforce_sorted=False,
                )
            )

            encoded, _ = self.lstm(
                packed
            )

            encoded, _ = (
                nn.utils.rnn.pad_packed_sequence(
                    encoded,
                    batch_first=True,
                    total_length=features.size(1),
                )
            )

        else:
            encoded, _ = self.lstm(
                features
            )

        encoded = self.dropout(
            encoded
        )

        return self.emission_layer(
            encoded
        )

    def loss(
        self,
        features: torch.Tensor,
        tags: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:

        if mask is None:
            mask = torch.ones(
                features.shape[:2],
                dtype=torch.bool,
                device=features.device,
            )

        emissions = self.emissions(
            features,
            mask,
        )

        return self.crf.neg_log_likelihood(
            emissions,
            tags,
            mask,
        )

    def decode(
        self,
        features: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> list[list[int]]:

        if mask is None:
            mask = torch.ones(
                features.shape[:2],
                dtype=torch.bool,
                device=features.device,
            )

        emissions = self.emissions(
            features,
            mask,
        )

        return self.crf.decode(
            emissions,
            mask,
        )

    def forward(
        self,
        features: torch.Tensor,
        tags: Optional[torch.Tensor] = None,
        mask: Optional[torch.Tensor] = None,
    ):

        if tags is not None:
            return self.loss(
                features,
                tags,
                mask,
            )

        return self.decode(
            features,
            mask,
        )