"""Computer-vision utilities for the Synaptix package-label workflow.

This initial package deliberately contains preprocessing only.  OCR, legal
validation, and backend integration belong to other project modules.
"""

from .preprocessing import PreprocessingConfig, preprocess_image

__all__ = ["PreprocessingConfig", "preprocess_image"]
