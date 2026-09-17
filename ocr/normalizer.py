"""
Token Normalization and Spatial Reading-Order Sorter for OCR tokens.

Performs:
1. Confidence threshold filtering (drops noise/artifacts)
2. Unicode text cleaning while preserving legal currency glyphs (₹, Rs.)
3. Spatial 2D grouping into reading order (top-to-bottom lines, left-to-right words)
4. Multi-token text line reconstruction for multi-token declarations
"""

import re
import unicodedata
from typing import NamedTuple, Optional
from pydantic import BaseModel, Field
from ocr.interfaces import OCRToken


class TextLine(BaseModel):
    """Represents a reconstructed horizontal text line composed of one or more OCR tokens."""
    text: str = Field(..., description="Concatenated text of the line")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence of tokens in the line")
    bbox: list[int] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box enclosing the entire line [x_min, y_min, x_max, y_max]",
    )
    tokens: list[OCRToken] = Field(default_factory=list, description="Original individual tokens")


class TokenNormalizer:
    """Cleans, filters, and spatially arranges OCR tokens into coherent text structures."""

    DEFAULT_MIN_CONFIDENCE: float = 0.40
    # Characters that are typically noise artifacts when isolated
    ISOLATED_NOISE_CHARS = set("~`^_|=+<>\\")

    @classmethod
    def clean_text(cls, raw_text: str) -> str:
        """
        Sanitize text while preserving Indian currency symbols (₹), colons, slashes,
        and legal metrology punctuation.
        """
        if not raw_text:
            return ""

        # Normalize unicode (keep standard characters and decomposed currency glyphs)
        normalized = unicodedata.normalize("NFKC", raw_text)
        
        # Replace non-breaking spaces and tabs with regular spaces
        cleaned = re.sub(r"[\s\u00a0\u2000-\u200b]+", " ", normalized).strip()

        # Remove stray noise characters if text consists only of punctuation
        if len(cleaned) == 1 and cleaned in cls.ISOLATED_NOISE_CHARS:
            return ""

        # Normalize common OCR glyph confusions (e.g. O/D as 0 in metric weights and prices)
        def _repl_unit(m: re.Match) -> str:
            return m.group(1) + ("0" * len(m.group(2))) + m.group(3)

        cleaned = re.sub(
            r"(\b\d+)([ODod]+)(\s*(?:g|kg|gm|ml|l|ltr|pcs|units?|nos|n\b))",
            _repl_unit,
            cleaned,
            flags=re.IGNORECASE,
        )

        def _repl_price(m: re.Match) -> str:
            return re.sub(r"[ODod]", "0", m.group(0))

        cleaned = re.sub(
            r"(?:Rs\.?|₹|MRP)\s*[\dODod]+(?:\.[\dODod]+)?",
            _repl_price,
            cleaned,
            flags=re.IGNORECASE,
        )

        # Fix collapsed unit numbers (e.g. 25STICKS -> 25 STICKS, 10TABLETS -> 10 TABLETS)
        cleaned = re.sub(
            r"\b(\d+)\s*(STICKS?|MATCHES?|TABLETS?|CAPSULES?|SHEETS?|WIPES?|POUCHES?|ROLLS?|BAGS?|TUBES?|BARS?|PACKS?|PCS|NOS|UNITS?)\b",
            r"\1 \2",
            cleaned,
            flags=re.IGNORECASE,
        )

        # Normalize dot-matrix phone / contact typos (e.g. Pi:1800... -> Ph: 1800...)
        cleaned = re.sub(r"\bP[in1]\s*:\s*(\d)", r"Ph: \1", cleaned, flags=re.IGNORECASE)

        # Normalize dot-matrix email without dot before TLD (e.g. qmat@itcin -> qmat@itc.in)
        cleaned = re.sub(r"@([A-Za-z0-9_-]+?)(in|com|org|net|co\.in)\b", r"@\1.\2", cleaned, flags=re.IGNORECASE)

        # Normalize currency prefix (e.g. R1/- or R 1/- -> Rs. 1/-)
        cleaned = re.sub(r"\bR\s*(\d+)\s*(?:/-)", r"Rs. \1/-", cleaned, flags=re.IGNORECASE)

        return cleaned

    @classmethod
    def filter_tokens(
        cls,
        tokens: list[OCRToken],
        min_confidence: Optional[float] = None,
    ) -> list[OCRToken]:
        """Filter tokens by confidence and remove empty/noise tokens."""
        threshold = min_confidence if min_confidence is not None else cls.DEFAULT_MIN_CONFIDENCE
        filtered: list[OCRToken] = []

        for token in tokens:
            cleaned = cls.clean_text(token.text)
            if not cleaned:
                continue
            if token.confidence < threshold:
                continue

            filtered.append(
                OCRToken(
                    text=cleaned,
                    confidence=token.confidence,
                    bbox=token.bbox,
                )
            )

        return filtered

    @staticmethod
    def is_vertical_token(token: OCRToken) -> bool:
        """Returns True if the token's bounding box indicates vertical sidebar text."""
        w = max(1, token.bbox[2] - token.bbox[0])
        h = max(1, token.bbox[3] - token.bbox[1])
        return h >= 1.8 * w and h >= 35

    @classmethod
    def reconstruct_lines(
        cls,
        tokens: list[OCRToken],
        vertical_overlap_ratio: float = 0.45,
    ) -> list[TextLine]:
        """
        Sort and group tokens into reading-order text lines based on spatial coordinates:
        1. Vertical sidebar tokens are isolated into their own independent lines.
        2. Horizontal tokens are grouped using strict bidirectional vertical overlap.
        3. Wide horizontal gaps (> 3x font height) between tokens prevent cross-column merging.
        4. Lines are sorted top-to-bottom, tokens within each line left-to-right.
        """
        if not tokens:
            return []

        # Separate vertical sidebar tokens from standard horizontal tokens
        horizontal_tokens: list[OCRToken] = []
        vertical_lines: list[TextLine] = []

        for token in tokens:
            if cls.is_vertical_token(token):
                vertical_lines.append(
                    TextLine(
                        text=token.text,
                        confidence=token.confidence,
                        bbox=token.bbox,
                        tokens=[token],
                    )
                )
            else:
                horizontal_tokens.append(token)

        # Sort horizontal tokens primarily by Y-coordinate, secondarily by X-coordinate
        sorted_tokens = sorted(horizontal_tokens, key=lambda t: (t.bbox[1], t.bbox[0]))

        line_groups: list[list[OCRToken]] = []

        for token in sorted_tokens:
            t_ymin, t_ymax = token.bbox[1], token.bbox[3]
            t_height = max(1, t_ymax - t_ymin)

            placed = False
            for group in line_groups:
                g_ymin = min(t.bbox[1] for t in group)
                g_ymax = max(t.bbox[3] for t in group)
                g_height = max(1, g_ymax - g_ymin)

                # Height compatibility check (prevent mixing tiny and giant fonts in one line)
                if max(t_height, g_height) / min(t_height, g_height) > 2.2:
                    continue

                # True vertical overlap intersection
                inter_y = max(0, min(t_ymax, g_ymax) - max(t_ymin, g_ymin))
                min_h = min(t_height, g_height)
                if (inter_y / min_h) >= vertical_overlap_ratio:
                    group.append(token)
                    placed = True
                    break

            if not placed:
                line_groups.append([token])

        # For each line group, sort tokens left-to-right by x_min
        text_lines: list[TextLine] = []
        for group in line_groups:
            group_sorted = sorted(group, key=lambda t: t.bbox[0])

            # Check if there is an excessive horizontal gap indicating separate columns
            current_subgroup: list[OCRToken] = []
            for t in group_sorted:
                if current_subgroup:
                    prev_t = current_subgroup[-1]
                    gap = t.bbox[0] - prev_t.bbox[2]
                    avg_h = ((prev_t.bbox[3] - prev_t.bbox[1]) + (t.bbox[3] - t.bbox[1])) / 2.0
                    # If horizontal gap is huge (> 4x font height), treat as distinct column stream
                    if gap > 4.0 * avg_h and gap > 120:
                        # Flush current subgroup
                        sub_text = " ".join(item.text for item in current_subgroup).strip()
                        text_lines.append(
                            TextLine(
                                text=sub_text,
                                confidence=round(sum(item.confidence for item in current_subgroup) / len(current_subgroup), 4),
                                bbox=[
                                    min(item.bbox[0] for item in current_subgroup),
                                    min(item.bbox[1] for item in current_subgroup),
                                    max(item.bbox[2] for item in current_subgroup),
                                    max(item.bbox[3] for item in current_subgroup),
                                ],
                                tokens=current_subgroup,
                            )
                        )
                        current_subgroup = [t]
                        continue
                current_subgroup.append(t)

            if current_subgroup:
                line_text = " ".join(t.text for t in current_subgroup).strip()
                x_min = min(t.bbox[0] for t in current_subgroup)
                y_min = min(t.bbox[1] for t in current_subgroup)
                x_max = max(t.bbox[2] for t in current_subgroup)
                y_max = max(t.bbox[3] for t in current_subgroup)
                mean_conf = round(sum(t.confidence for t in current_subgroup) / len(current_subgroup), 4)

                text_lines.append(
                    TextLine(
                        text=line_text,
                        confidence=mean_conf,
                        bbox=[x_min, y_min, x_max, y_max],
                        tokens=current_subgroup,
                    )
                )

        # Merge horizontal text lines and vertical sidebar lines
        all_lines = text_lines + vertical_lines

        # Sort all lines top-to-bottom by y_min
        all_lines.sort(key=lambda line: line.bbox[1])
        return all_lines

    @classmethod
    def normalize(
        cls,
        tokens: list[OCRToken],
        min_confidence: Optional[float] = None,
        vertical_overlap_ratio: float = 0.45,
    ) -> list[TextLine]:
        """
        Convenience pipeline: filters tokens by confidence and reconstructs spatial text lines.
        """
        filtered = cls.filter_tokens(tokens, min_confidence=min_confidence)
        return cls.reconstruct_lines(filtered, vertical_overlap_ratio=vertical_overlap_ratio)
