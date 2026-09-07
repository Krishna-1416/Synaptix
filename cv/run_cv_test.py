"""Run preprocessing and deskewing on one real package-label image."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from cv.deskew import deskew_image
from cv.preprocessing import preprocess_image


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the Synaptix CV pipeline on one image.")
    parser.add_argument(
        "image",
        nargs="?",
        default="sample_data/package.jpg",
        help="Input image path, relative to the repository root by default.",
    )
    args = parser.parse_args()
    image_path = Path(args.image)
    if not image_path.is_file():
        raise SystemExit(f"Image not found: {image_path}. Put package.jpg in sample_data/ or pass its path.")

    corrected, angle = deskew_image(str(image_path))
    preprocessed = preprocess_image(corrected)

    output_dir = image_path.parent
    corrected_path = output_dir / "corrected.jpg"
    preprocessed_path = output_dir / "preprocessed.jpg"
    if not cv2.imwrite(str(corrected_path), corrected):
        raise SystemExit(f"Could not write {corrected_path}")
    if not cv2.imwrite(str(preprocessed_path), preprocessed):
        raise SystemExit(f"Could not write {preprocessed_path}")

    print(f"Deskew angle applied: {angle}")
    print(f"Corrected image: {corrected_path}")
    print(f"OCR-ready image: {preprocessed_path}")


if __name__ == "__main__":
    main()
