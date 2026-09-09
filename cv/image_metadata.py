"""Extract trustworthy physical-scale metadata from uploaded images."""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def extract_dpi(image_bytes: bytes) -> float | None:
    """Return embedded horizontal DPI, or ``None`` when scale is unknown."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            dpi = image.info.get("dpi")
            if isinstance(dpi, tuple):
                dpi = dpi[0]
            if dpi is None:
                dpi = image.getexif().get(282)
            if dpi is not None:
                try:
                    numeric_dpi = float(dpi)
                except (TypeError, ValueError):
                    numeric_dpi = 0.0
                if numeric_dpi > 0:
                    return numeric_dpi
    except (OSError, ValueError, TypeError):
        return None
    return None