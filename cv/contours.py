"""Contour-based detection of likely text or label regions.

The functions in this module locate visual regions only. They do not recognize
text and do not decide whether a package is legally compliant.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

from .preprocessing import ImageInput, load_image, to_grayscale


@dataclass(frozen=True)
class RegionDetectionConfig:
    """Conservative filters for grouped text/label contours."""

    kernel_width: int = 17
    kernel_height: int = 3
    min_width: int = 50
    min_height: int = 10
    min_area: int = 180
    max_area_ratio: float = 0.45
    min_aspect_ratio: float = 0.30
    max_height_ratio: float = 0.75
    min_width_for_tall_region: int = 90

    def __post_init__(self) -> None:
        if self.kernel_width < 1 or self.kernel_height < 1:
            raise ValueError("morphology kernel dimensions must be positive")
        if self.min_width < 1 or self.min_height < 1 or self.min_area < 1:
            raise ValueError("minimum contour dimensions and area must be positive")
        if not 0 < self.max_area_ratio <= 1:
            raise ValueError("max_area_ratio must be greater than 0 and at most 1")
        if self.min_aspect_ratio <= 0:
            raise ValueError("min_aspect_ratio must be positive")
        if not 0 < self.max_height_ratio <= 1:
            raise ValueError("max_height_ratio must be greater than 0 and at most 1")
        if self.min_width_for_tall_region < self.min_width:
            raise ValueError("min_width_for_tall_region must be at least min_width")


@dataclass(frozen=True)
class BoundingBox:
    """A pixel-aligned rectangle using image coordinates from its top-left."""

    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height

    def as_dict(self) -> dict[str, int]:
        """Return a JSON-ready representation for a future agreed interface."""
        return asdict(self)


def detect_regions(
    image: ImageInput, config: RegionDetectionConfig | None = None
) -> list[BoundingBox]:
    """Find likely text/label regions and return stable, sorted bounding boxes.

    Dark foreground is thresholded and then horizontally closed to join letters
    in a line. Results are sorted top-to-bottom and then left-to-right. The
    filters intentionally reject tiny specks and near-full-image contours.
    """
    config = config or RegionDetectionConfig()
    source = load_image(image)
    gray = to_grayscale(source)
    _, foreground = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (config.kernel_width, config.kernel_height))
    grouped = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel)
    # RETR_LIST keeps inner contours too. Package labels frequently have an
    # outer printed frame, so RETR_EXTERNAL would hide all enclosed text.
    contours, _ = cv2.findContours(grouped, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    image_area = gray.shape[0] * gray.shape[1]
    regions: list[BoundingBox] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        aspect_ratio = width / height
        if width < config.min_width or height < config.min_height:
            continue
        if area < config.min_area or area / image_area > config.max_area_ratio:
            continue
        # Reject thin, tall package borders while retaining wider blocks of
        # ingredient/manufacturer text, which are often not horizontal lines.
        if aspect_ratio < config.min_aspect_ratio or height / gray.shape[0] > config.max_height_ratio:
            continue
        if height / gray.shape[0] > 0.25 and width < config.min_width_for_tall_region:
            continue
        regions.append(BoundingBox(x=x, y=y, width=width, height=height))
    return sorted(regions, key=lambda region: (region.y, region.x))


def draw_regions(
    image: ImageInput,
    regions: list[BoundingBox],
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Return a BGR debug image with the supplied bounding boxes drawn on it."""
    if thickness < 1:
        raise ValueError("thickness must be positive")
    source = load_image(image)
    canvas = cv2.cvtColor(source, cv2.COLOR_GRAY2BGR) if source.ndim == 2 else source
    for region in regions:
        cv2.rectangle(
            canvas,
            (region.x, region.y),
            (region.x + region.width, region.y + region.height),
            color,
            thickness,
        )
    return canvas


def regions_as_dicts(regions: list[BoundingBox]) -> list[dict[str, Any]]:
    """Provide primitive values for a future backend schema adapter."""
    return [region.as_dict() for region in regions]
