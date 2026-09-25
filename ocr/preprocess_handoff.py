"""
Preprocess handoff module for ingesting images from Computer Vision (Member 4)
or direct file paths.

Provides zero-copy in-memory array validation, channel normalization,
and color space standardization for downstream OCR inference.
"""

from pathlib import Path
from typing import Union
import cv2
import numpy as np

# Disable OpenCV multi-threading to prevent thread stack memory overhead and contention on 0.1 vCPU
cv2.setNumThreads(0)


class ImageValidationError(ValueError):
    """Raised when an incoming image fails dimensionality, type, or integrity checks."""
    pass


class OCRConfig:
    """Configuration parameters for OCR preprocessing and handoff."""
    PAD_PIXELS: int = 20
    CONTRAST_THRESHOLD: float = 30.0
    ASPECT_RATIO_THRESHOLD: float = 3.0
    PADDING_HEIGHT_RATIO: float = 0.15


def compute_padding(w: int, h: int, base_pad: int = 20) -> int:
    """
    Add extra vertical padding for wide, short images (Improvement #4).
    RapidOCR text detection benefits from vertical expansion on elongated packaging.
    """
    aspect = w / max(h, 1)
    if aspect > 3.0:
        return max(base_pad, int(h * 0.15))
    return base_pad


class PreprocessHandoff:
    """Handles and standardizes image handoffs from Member 4 (CV) or disk."""

    MIN_DIMENSION: int = 32
    MAX_DIMENSION: int = 8192
    TARGET_MAX_DIMENSION: int = 1280
    PAD_PIXELS: int = 20

    @classmethod
    def load_and_validate(cls, source: Union[np.ndarray, str, Path, bytes, bytearray]) -> np.ndarray:
        """
        Ingest, validate, and standardize an image into an RGB uint8 array.

        Args:
            source: In-memory numpy array, raw image bytes, or file path.

        Returns:
            np.ndarray: 3-channel uint8 array with shape (H, W, 3) in RGB ordering.

        Raises:
            ImageValidationError: If image cannot be read or fails integrity constraints.
        """
        image_array: np.ndarray

        if isinstance(source, (bytes, bytearray)):
            if len(source) == 0:
                raise ImageValidationError("Received empty byte buffer (size == 0).")
            try:
                import io
                from PIL import Image, ImageOps
                with Image.open(io.BytesIO(source)) as pil_img:
                    pil_img = ImageOps.exif_transpose(pil_img)
                    if pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")
                    image_array = np.array(pil_img, dtype=np.uint8)
            except Exception:
                nparr = np.frombuffer(source, np.uint8)
                bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if bgr is None:
                    raise ImageValidationError("Invalid or corrupt image: OpenCV failed to decode image bytes into an image array.")
                image_array = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        elif isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists() or not path.is_file():
                raise ImageValidationError(f"Image file does not exist: {path}")
            
            try:
                from PIL import Image, ImageOps
                with Image.open(str(path)) as pil_img:
                    pil_img = ImageOps.exif_transpose(pil_img)
                    if pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")
                    image_array = np.array(pil_img, dtype=np.uint8)
            except Exception:
                # Fallback via OpenCV (loads BGR)
                bgr = cv2.imread(str(path))
                if bgr is None:
                    raise ImageValidationError(f"OpenCV failed to decode image: {path}")
                image_array = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        elif isinstance(source, np.ndarray):
            if source.size == 0:
                raise ImageValidationError("Received empty NumPy array (size == 0).")
            image_array = source
        else:
            raise ImageValidationError(f"Unsupported image input type: {type(source).__name__}")

        # Ensure correct dtype
        if image_array.dtype != np.uint8:
            if np.issubdtype(image_array.dtype, np.floating):
                # Scale float [0.0, 1.0] to [0, 255] if applicable
                if image_array.max() <= 1.0:
                    image_array = (image_array * 255.0).astype(np.uint8)
                else:
                    image_array = np.clip(image_array, 0, 255).astype(np.uint8)
            else:
                image_array = image_array.astype(np.uint8)

        # Normalize dimensions & channels
        if image_array.ndim == 2:
            # Grayscale (H, W) -> RGB (H, W, 3)
            image_array = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)
        elif image_array.ndim == 3:
            channels = image_array.shape[2]
            if channels == 4:
                # RGBA -> RGB
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2RGB)
            elif channels == 1:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)
            elif channels != 3:
                raise ImageValidationError(f"Unsupported channel count: {channels} (expected 1, 3, or 4).")
        else:
            raise ImageValidationError(f"Invalid image dimensions: {image_array.ndim}D array (expected 2D or 3D).")

        h, w = image_array.shape[:2]
        if h < cls.MIN_DIMENSION or w < cls.MIN_DIMENSION:
            raise ImageValidationError(
                f"Image resolution too small: {w}x{h} (minimum {cls.MIN_DIMENSION}x{cls.MIN_DIMENSION})"
            )
        if h > cls.MAX_DIMENSION or w > cls.MAX_DIMENSION:
            raise ImageValidationError(
                f"Image resolution exceeds threshold: {w}x{h} (maximum {cls.MAX_DIMENSION}x{cls.MAX_DIMENSION})"
            )

        # Scale down oversized images to conserve memory on 512MB containers (Render)
        if max(h, w) > cls.TARGET_MAX_DIMENSION:
            scale = cls.TARGET_MAX_DIMENSION / float(max(h, w))
            new_w = max(int(round(w * scale)), cls.MIN_DIMENSION)
            new_h = max(int(round(h * scale)), cls.MIN_DIMENSION)
            image_array = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)

        return image_array


def load_and_prepare(
    image_input: Union[np.ndarray, str, Path, bytes, bytearray],
    contrast_threshold: float = OCRConfig.CONTRAST_THRESHOLD,
    apply_padding: bool = True,
) -> np.ndarray:
    """
    Standardize, contrast-adjust (conditional CLAHE), and pad image for OCR inference.
    
    1. Ingests and standardizes image to RGB (H, W, 3).
    2. Improvement #3 — Conditional CLAHE: Computes grayscale standard deviation and
       applies CLAHE only when contrast is genuinely low (< 30).
    3. Improvement #4 — Dynamic Padding: Adds vertical border padding for wide, short
       packaging labels (aspect ratio > 3.0) to aid text detection.
    """
    img = PreprocessHandoff.load_and_validate(image_input)
    h, w = img.shape[:2]

    # Improvement #3: Compute image contrast
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    contrast = float(gray.std())

    # Only apply CLAHE if contrast is low
    if contrast < contrast_threshold:
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # Improvement #4: Dynamic padding for elongated labels
    if apply_padding:
        aspect = w / max(h, 1)
        if aspect > OCRConfig.ASPECT_RATIO_THRESHOLD:
            pad = compute_padding(w, h, OCRConfig.PAD_PIXELS)
            img = cv2.copyMakeBorder(
                img, pad, pad, pad, pad,
                cv2.BORDER_CONSTANT, value=(255, 255, 255)
            )

    return img

