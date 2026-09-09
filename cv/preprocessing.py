"""Deterministic image preprocessing for package-label OCR handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import cv2
import numpy as np


ImageInput = Union[np.ndarray, str, bytes, bytearray]


@dataclass(frozen=True)
class PreprocessingConfig:
    """Tunable, validated OpenCV parameters for the preprocessing pipeline."""

    bilateral_diameter: int = 9
    bilateral_sigma_color: float = 75.0
    bilateral_sigma_space: float = 75.0
    adaptive_method: int = cv2.ADAPTIVE_THRESH_GAUSSIAN_C
    threshold_type: int = cv2.THRESH_BINARY
    adaptive_block_size: int = 31
    adaptive_constant: float = 8.0

    def __post_init__(self) -> None:
        if self.bilateral_diameter <= 0:
            raise ValueError("bilateral_diameter must be positive")
        if self.bilateral_sigma_color <= 0 or self.bilateral_sigma_space <= 0:
            raise ValueError("bilateral sigma values must be positive")
        if self.adaptive_block_size < 3 or self.adaptive_block_size % 2 == 0:
            raise ValueError("adaptive_block_size must be an odd integer of at least 3")
        if self.adaptive_method not in (
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        ):
            raise ValueError("adaptive_method is not supported")
        if self.threshold_type not in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
            raise ValueError("threshold_type must be THRESH_BINARY or THRESH_BINARY_INV")


def load_image(image: ImageInput) -> np.ndarray:
    """Load an image path, raw image bytes, or validate an already-decoded NumPy image.

    Returns a copy so callers retain ownership of their original array.
    Raises ValueError for unreadable, empty, or unsupported images.
    """
    if isinstance(image, (bytes, bytearray)):
        if len(image) == 0:
            raise ValueError("image bytes are empty")
        nparr = np.frombuffer(image, np.uint8)
        loaded = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
        if loaded is None:
            raise ValueError("Could not decode image from bytes")
        image = loaded
    elif isinstance(image, str):
        loaded = cv2.imread(image, cv2.IMREAD_UNCHANGED)
        if loaded is None:
            raise ValueError(f"Could not read image: {image}")
        image = loaded

    if not isinstance(image, np.ndarray):
        raise ValueError("image must be a NumPy array, readable path, or valid bytes")
    if image.size == 0 or image.ndim not in (2, 3):
        raise ValueError("image must be a non-empty grayscale, BGR, or BGRA image")
    if image.ndim == 3 and image.shape[2] not in (3, 4):
        raise ValueError("colour image must have 3 (BGR) or 4 (BGRA) channels")
    if image.dtype != np.uint8:
        raise ValueError("image must use uint8 pixels")
    return image.copy()


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert BGR/BGRA input to a single-channel grayscale image."""
    if image.ndim == 2:
        return image
    conversion = cv2.COLOR_BGRA2GRAY if image.shape[2] == 4 else cv2.COLOR_BGR2GRAY
    return cv2.cvtColor(image, conversion)


def preprocess_image(
    image: ImageInput, config: PreprocessingConfig | None = None
) -> np.ndarray:
    """Return a binary, single-channel label image suitable for downstream OCR.

    Pipeline: validate/load -> grayscale -> bilateral denoise -> adaptive
    threshold. This function does not rotate, locate text, recognize text, or
    make compliance decisions.
    """
    config = config or PreprocessingConfig()
    source = load_image(image)
    gray = to_grayscale(source)
    filtered = cv2.bilateralFilter(
        gray,
        d=config.bilateral_diameter,
        sigmaColor=config.bilateral_sigma_color,
        sigmaSpace=config.bilateral_sigma_space,
    )
    return cv2.adaptiveThreshold(
        filtered,
        maxValue=255,
        adaptiveMethod=config.adaptive_method,
        thresholdType=config.threshold_type,
        blockSize=config.adaptive_block_size,
        C=config.adaptive_constant,
    )
