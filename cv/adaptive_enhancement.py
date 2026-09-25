"""
Adaptive image enhancement for package label OCR under real-world conditions:
- Specular glare / highlight suppression on glossy and foil packaging
- Contrast Limited Adaptive Histogram Equalization (CLAHE) in LAB space
- Unsharp masking for camera soft focus / handheld motion blur
- 4-way cardinal orientation (90°, 180°, 270°) detection & correction
"""

from __future__ import annotations

import logging
from typing import Tuple
import cv2
import numpy as np

logger = logging.getLogger("synaptix.cv.adaptive")


def apply_clahe_contrast(
    rgb_image: np.ndarray,
    clip_limit: float = 2.5,
    tile_grid_size: Tuple[int, int] = (8, 8),
) -> np.ndarray:
    """
    Applies CLAHE on the Lightness (L) channel in LAB color space.
    Equalizes local contrast across shadow gradients without blowing out highlights.
    """
    if rgb_image is None or rgb_image.size == 0:
        return rgb_image

    try:
        lab = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        l_enhanced = clahe.apply(l_channel)

        enhanced_lab = cv2.merge((l_enhanced, a_channel, b_channel))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
    except Exception as err:
        logger.warning(f"CLAHE contrast enhancement fallback: {err}")
        return rgb_image


def suppress_specular_glare(
    rgb_image: np.ndarray,
    luminance_threshold: int = 248,
) -> np.ndarray:
    """
    Detects specular glare hot-spots (common on plastic pouches & metallic foil)
    and attenuates intensity to reveal underlying text strokes.
    """
    if rgb_image is None or rgb_image.size == 0:
        return rgb_image

    try:
        gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
        # Create mask of specular highlights
        _, glare_mask = cv2.threshold(gray, luminance_threshold, 255, cv2.THRESH_BINARY)

        # Check if glare covers a moderate portion of the image (0.1% to 15%)
        glare_ratio = np.count_nonzero(glare_mask) / float(gray.size)
        if 0.001 < glare_ratio < 0.20:
            # Dilate mask slightly to cover halo
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            dilated_mask = cv2.dilate(glare_mask, kernel, iterations=1)

            # Inpaint glare regions using Navier-Stokes based method
            inpainted = cv2.inpaint(rgb_image, dilated_mask, inpaintRadius=3, flags=cv2.INPAINT_NS)
            # Blend 60% inpainted with 40% original to retain valid character edges
            return cv2.addWeighted(inpainted, 0.65, rgb_image, 0.35, 0)

        return rgb_image
    except Exception as err:
        logger.warning(f"Glare suppression fallback: {err}")
        return rgb_image


def apply_unsharp_mask(
    rgb_image: np.ndarray,
    sigma: float = 1.0,
    strength: float = 1.5,
) -> np.ndarray:
    """
    Sharpens soft-focus phone camera images via Gaussian unsharp masking.
    """
    if rgb_image is None or rgb_image.size == 0:
        return rgb_image

    try:
        blurred = cv2.GaussianBlur(rgb_image, (0, 0), sigma)
        # unsharp = original + strength * (original - blurred)
        sharpened = cv2.addWeighted(rgb_image, 1.0 + strength, blurred, -strength, 0)
        return np.clip(sharpened, 0, 255).astype(np.uint8)
    except Exception as err:
        logger.warning(f"Unsharp mask fallback: {err}")
        return rgb_image


def enhance_packaging_image(
    rgb_image: np.ndarray,
    apply_glare_suppression: bool = True,
    apply_clahe: bool = True,
    apply_sharpening: bool = True,
) -> np.ndarray:
    """
    High-level composite enhancer that normalizes illumination, suppresses glare,
    equalizes local contrast, and sharpens text strokes on packaged commodity labels.
    """
    if rgb_image is None or rgb_image.size == 0:
        return rgb_image

    enhanced = rgb_image
    if apply_glare_suppression:
        enhanced = suppress_specular_glare(enhanced)

    if apply_clahe:
        # Improvement #3: Conditional CLAHE (only apply if image has genuinely low contrast)
        gray_contrast = cv2.cvtColor(enhanced, cv2.COLOR_RGB2GRAY).std()
        if gray_contrast < 30.0:
            enhanced = apply_clahe_contrast(enhanced, clip_limit=2.0, tile_grid_size=(8, 8))

    if apply_sharpening:
        # Check if image is blurry (Laplacian variance < 250)
        gray = cv2.cvtColor(enhanced, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 350.0:
            enhanced = apply_unsharp_mask(enhanced, sigma=1.0, strength=1.3)

    return enhanced


def upscale_if_low_res(
    rgb_image: np.ndarray,
    min_dimension_threshold: int = 600,
    max_scale_factor: float = 2.5,
) -> Tuple[np.ndarray, float]:
    """
    If the image has low resolution (min dimension < 600px, where 1mm fonts
    would be only 3-5px high), scale it up with INTER_CUBIC so character strokes
    become discernible by the neural text detector.
    Returns (scaled_image, scale_factor).
    """
    if rgb_image is None or rgb_image.size == 0:
        return rgb_image, 1.0

    h, w = rgb_image.shape[:2]
    min_dim = min(h, w)
    if min_dim < min_dimension_threshold:
        factor = min(max_scale_factor, float(min_dimension_threshold) / float(max(min_dim, 1)))
        new_w = int(round(w * factor))
        new_h = int(round(h * factor))
        upscaled = cv2.resize(rgb_image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        return upscaled, factor

    return rgb_image, 1.0

