"""Single CV entry point and explicit handoffs to OCR and backend modules.

This module owns visual processing only. It does not recognize declarations,
call an OCR service, persist data, or make a legal PASS/FAIL decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

from .contours import BoundingBox, detect_regions, draw_regions
from .deskew import deskew_image
from .font_height import FontHeightResult, measure_region_height
from .placement import PlacementResult, build_placement
from .preprocessing import ImageInput, preprocess_image
from .readability import ReadabilityResult, assess_readability


@dataclass
class CVPipelineResult:
    """Outputs owned by the CV engineer and ready for agreed handoff adapters."""

    ocr_ready_image: np.ndarray
    corrected_image: np.ndarray
    deskew_angle_degrees: float | None
    regions: list[BoundingBox]
    readability: ReadabilityResult
    placement: PlacementResult
    font_height: FontHeightResult | None

    def backend_payload(self) -> dict[str, dict[str, str | float | None]]:
        """Return data compatible with the current shared inspection schema.

        The current schema declares ``placement`` as a string, so detailed box
        coordinates remain in ``detailed_visual_checks`` until Member 2 agrees
        to extend that shared contract.
        """
        return {
            "visual_checks": {
                "readability": self.readability.status,
                "font_height": (
                    self.font_height.physical_height_mm if self.font_height else None
                ),
                "placement": f"{len(self.regions)} regions detected",
            }
        }

    def detailed_visual_checks(self) -> dict[str, object]:
        """Return full metrics and coordinates for a proposed backend extension."""
        return {
            "deskew_angle_degrees": self.deskew_angle_degrees,
            "readability": asdict(self.readability),
            "placement": self.placement.as_dict(),
            "font_height": asdict(self.font_height) if self.font_height else None,
        }

    def region_overlay(self) -> np.ndarray:
        """Create a display/debug image without altering the OCR image."""
        return draw_regions(self.corrected_image, self.regions)


def run_cv_pipeline(
    image: ImageInput,
    *,
    dpi: float | None = None,
    font_region_index: int | None = None,
) -> CVPipelineResult:
    """Run all completed CV stages and return OCR and backend handoffs.

    A physical font height is calculated only when both a known DPI and an
    explicitly selected text region are supplied. This prevents arbitrary box
    heights from being mistaken for legal font measurements.
    """
    corrected, deskew_angle = deskew_image(image)
    ocr_ready = preprocess_image(corrected)
    regions = detect_regions(corrected)
    readability = assess_readability(corrected)
    placement = build_placement(corrected, regions)

    font_height: FontHeightResult | None = None
    if font_region_index is not None:
        if not 0 <= font_region_index < len(regions):
            raise ValueError("font_region_index must select a detected region")
        font_height = measure_region_height(regions[font_region_index], dpi)

    return CVPipelineResult(
        ocr_ready_image=ocr_ready,
        corrected_image=corrected,
        deskew_angle_degrees=deskew_angle,
        regions=regions,
        readability=readability,
        placement=placement,
        font_height=font_height,
    )


def save_ocr_handoff(image: np.ndarray, destination: str) -> None:
    """Save a lossless OCR-ready image when in-memory handoff is unavailable."""
    if not cv2.imwrite(destination, image):
        raise ValueError(f"Could not save OCR handoff image: {destination}")
