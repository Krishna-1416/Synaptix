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

    @classmethod
    def reconstruct_lines(
        cls,
        tokens: list[OCRToken],
        vertical_overlap_ratio: float = 0.5,
    ) -> list[TextLine]:
        """
        Sort and group tokens into horizontal text lines based on spatial coordinates.
        Sorts lines top-to-bottom, and tokens within each line left-to-right.
        """
        if not tokens:
            return []

        # Sort tokens primarily by Y-coordinate (top-to-bottom), secondarily by X-coordinate
        sorted_tokens = sorted(tokens, key=lambda t: (t.bbox[1], t.bbox[0]))

        line_groups: list[list[OCRToken]] = []

        for token in sorted_tokens:
            t_ymin, t_ymax = token.bbox[1], token.bbox[3]
            t_height = max(1, t_ymax - t_ymin)
            t_cy = (t_ymin + t_ymax) / 2.0

            placed = False
            for group in line_groups:
                # Calculate bounding vertical span of the group
                g_ymin = min(t.bbox[1] for t in group)
                g_ymax = max(t.bbox[3] for t in group)
                g_height = max(1, g_ymax - g_ymin)
                g_cy = (g_ymin + g_ymax) / 2.0

                # Tolerant vertical distance check
                max_h = max(t_height, g_height)
                if abs(t_cy - g_cy) < max_h * vertical_overlap_ratio:
                    group.append(token)
                    placed = True
                    break

            if not placed:
                line_groups.append([token])

        # For each line group, sort tokens left-to-right by x_min
        text_lines: list[TextLine] = []
        for group in line_groups:
            group_sorted = sorted(group, key=lambda t: t.bbox[0])
            line_text = " ".join(t.text for t in group_sorted).strip()
            
            x_min = min(t.bbox[0] for t in group_sorted)
            y_min = min(t.bbox[1] for t in group_sorted)
            x_max = max(t.bbox[2] for t in group_sorted)
            y_max = max(t.bbox[3] for t in group_sorted)
            mean_conf = round(sum(t.confidence for t in group_sorted) / len(group_sorted), 4)

            text_lines.append(
                TextLine(
                    text=line_text,
                    confidence=mean_conf,
                    bbox=[x_min, y_min, x_max, y_max],
                    tokens=group_sorted,
                )
            )

        # Sort lines top-to-bottom by y_min
        text_lines.sort(key=lambda line: line.bbox[1])
        return text_lines
