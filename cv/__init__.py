"""Computer-vision utilities for the Synaptix package-label workflow.

This initial package deliberately contains preprocessing only.  OCR, legal
validation, and backend integration belong to other project modules.
"""

from .preprocessing import PreprocessingConfig, preprocess_image, load_image
from .deskew import DeskewConfig, deskew_image, estimate_skew_angle
from .contours import BoundingBox, RegionDetectionConfig, detect_regions, draw_regions
from .font_height import FontHeightResult, calculate_font_height, measure_region_height
from .readability import ReadabilityResult, assess_readability
from .placement import PlacementResult, build_placement
from .pipeline import CVPipelineResult, run_cv_pipeline, save_ocr_handoff

__all__ = [
    "PreprocessingConfig",
    "preprocess_image",
    "load_image",
    "DeskewConfig",
    "deskew_image",
    "estimate_skew_angle",
    "BoundingBox",
    "RegionDetectionConfig",
    "detect_regions",
    "draw_regions",
    "FontHeightResult",
    "calculate_font_height",
    "measure_region_height",
    "ReadabilityResult",
    "assess_readability",
    "PlacementResult",
    "build_placement",
    "CVPipelineResult",
    "run_cv_pipeline",
    "save_ocr_handoff",
]
