"""Content-based deskewing for package-label images.

This module corrects small camera/document tilt. It does not identify text or
make a compliance decision.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .preprocessing import ImageInput, load_image, to_grayscale


@dataclass(frozen=True)
class DeskewConfig:
    """Parameters controlling conservative skew estimation."""

    min_foreground_pixels: int = 100
    min_orientation_ratio: float = 1.15
    min_absolute_angle_degrees: float = 0.3
    max_absolute_angle_degrees: float = 20.0
    interpolation: int = cv2.INTER_CUBIC
    border_mode: int = cv2.BORDER_REPLICATE

    def __post_init__(self) -> None:
        if self.min_foreground_pixels < 1:
            raise ValueError("min_foreground_pixels must be at least 1")
        if self.min_orientation_ratio <= 1.0:
            raise ValueError("min_orientation_ratio must be greater than 1")
        if not 0 <= self.min_absolute_angle_degrees < self.max_absolute_angle_degrees:
            raise ValueError("angle limits must satisfy 0 <= minimum < maximum")


def estimate_skew_angle(image: ImageInput, config: DeskewConfig | None = None) -> float | None:
    """Estimate label tilt in degrees, or return ``None`` when not reliable.

    The calculation uses principal-component analysis (PCA) on dark,
    non-background pixels. Unlike ``minAreaRect``, this avoids OpenCV-version
    differences in reported rectangle angles. Positive results are rotation
    angles that should be applied directly with OpenCV's
    ``getRotationMatrix2D``.
    """
    config = config or DeskewConfig()
    source = load_image(image)
    gray = to_grayscale(source)
    # Otsu adapts to light or dark package backgrounds without a fixed threshold.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    points = np.column_stack(np.where(binary > 0))[:, ::-1].astype(np.float32)
    if len(points) < config.min_foreground_pixels:
        return None

    centered = points - points.mean(axis=0)
    covariance = np.cov(centered, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    major_value, minor_value = float(eigenvalues[-1]), float(eigenvalues[0])
    if minor_value <= 0 or major_value / minor_value < config.min_orientation_ratio:
        return None

    direction = eigenvectors[:, -1]
    text_angle = float(np.degrees(np.arctan2(direction[1], direction[0])))
    # Direction can point either left or right. Normalize it to the nearest
    # horizontal orientation before converting it into a correction angle.
    if text_angle > 90.0:
        text_angle -= 180.0
    elif text_angle <= -90.0:
        text_angle += 180.0
    # In image coordinates (where y grows downward), OpenCV's positive
    # rotation convention matches this normalized PCA angle.
    correction = text_angle
    if not config.min_absolute_angle_degrees <= abs(correction) <= config.max_absolute_angle_degrees:
        return None
    return correction


def deskew_image(image: ImageInput, config: DeskewConfig | None = None) -> tuple[np.ndarray, float | None]:
    """Return ``(corrected_image, applied_angle)`` without changing input shape.

    When the estimate is unavailable or too extreme, this safely returns an
    unchanged copy and ``None``.  Callers can use that signal in debug logs.
    """
    config = config or DeskewConfig()
    source = load_image(image)
    angle = estimate_skew_angle(source, config)
    if angle is None:
        return source, None
    height, width = source.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
    rotated = cv2.warpAffine(
        source,
        matrix,
        (width, height),
        flags=config.interpolation,
        borderMode=config.border_mode,
    )
    return rotated, angle
