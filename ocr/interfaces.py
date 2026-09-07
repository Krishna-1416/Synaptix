"""
Interfaces and abstract protocols for the OCR Engineer module (Member 3).
Adheres to the Dependency Inversion Principle (DIP) to decouple callers
from specific OCR engine implementations (PaddleOCR, EasyOCR, etc.).
"""

from typing import Protocol, runtime_checkable
import numpy as np
from pydantic import BaseModel, Field


class OCRToken(BaseModel):
    """Represents a single recognized text bounding token."""
    text: str = Field(..., description="Recognized text string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    bbox: list[int] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Axis-aligned bounding box coordinates: [x_min, y_min, x_max, y_max]",
    )


@runtime_checkable
class OCREngineProtocol(Protocol):
    """Protocol defining the interface for OCR engines."""

    def detect_and_recognize(self, image: np.ndarray) -> list[OCRToken]:
        """
        Execute text detection and recognition on an in-memory image array.

        Args:
            image: 3-channel RGB image as a uint8 NumPy array (H, W, 3).

        Returns:
            list[OCRToken]: List of detected tokens with text, confidence, and bounding box.
        """
        ...
