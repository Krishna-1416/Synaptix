"""Visual placement data derived from detected regions.

This module exposes coordinates for the backend/frontend. It does not decide
whether label placement satisfies a legal rule.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .contours import BoundingBox
from .preprocessing import ImageInput, load_image


@dataclass(frozen=True)
class PlacementResult:
    """Pixel and normalized positions of visual regions in one image."""

    image_width: int
    image_height: int
    region_count: int
    regions: list[dict[str, float | int]]

    def as_dict(self) -> dict[str, object]:
        """Return JSON-ready placement information for an agreed adapter."""
        return asdict(self)


def build_placement(image: ImageInput, regions: list[BoundingBox]) -> PlacementResult:
    """Return coordinates and 0-to-1 normalized coordinates for each region."""
    source = load_image(image)
    height, width = source.shape[:2]
    entries: list[dict[str, float | int]] = []
    for region in regions:
        if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
            raise ValueError("bounding-box values must be positive and within image coordinates")
        if region.x + region.width > width or region.y + region.height > height:
            raise ValueError("bounding box extends outside the image")
        entries.append(
            {
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
                "x_normalized": round(region.x / width, 6),
                "y_normalized": round(region.y / height, 6),
                "width_normalized": round(region.width / width, 6),
                "height_normalized": round(region.height / height, 6),
            }
        )
    return PlacementResult(width, height, len(entries), entries)
