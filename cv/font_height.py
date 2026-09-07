"""Calibrated physical font-height measurement.

This module never infers DPI. A millimetre value is returned only when a real
DPI or equivalent physical calibration was supplied by the calling workflow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .contours import BoundingBox


@dataclass(frozen=True)
class FontHeightResult:
    """Pixel height plus an optional calibrated physical measurement."""

    pixel_height: float
    dpi: float | None
    physical_height_mm: float | None
    status: str

    def as_dict(self) -> dict[str, float | str | None]:
        return asdict(self)


def calculate_font_height(pixel_height: float, dpi: float | None = None) -> FontHeightResult:
    """Convert known pixel height to mm only when a valid DPI is supplied.

    Formula: ``physical height (mm) = pixel height / DPI * 25.4``.
    The caller must obtain DPI from calibrated capture or trusted image
    metadata; raw photographs normally have no reliable physical scale.
    """
    if pixel_height <= 0:
        raise ValueError("pixel_height must be positive")
    if dpi is None:
        return FontHeightResult(float(pixel_height), None, None, "unknown_scale")
    if dpi <= 0:
        raise ValueError("dpi must be positive when supplied")
    return FontHeightResult(
        float(pixel_height),
        float(dpi),
        float(pixel_height) / float(dpi) * 25.4,
        "measured",
    )


def measure_region_height(region: BoundingBox, dpi: float | None = None) -> FontHeightResult:
    """Measure a detected text-line region; this does not assess compliance."""
    return calculate_font_height(region.height, dpi)
