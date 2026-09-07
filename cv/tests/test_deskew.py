import cv2
import numpy as np

from cv.deskew import DeskewConfig, deskew_image, estimate_skew_angle


def horizontal_label() -> np.ndarray:
    image = np.full((300, 600), 255, dtype=np.uint8)
    cv2.putText(image, "NET QTY 500 g", (80, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3)
    cv2.line(image, (80, 180), (500, 180), 0, 3)
    return image


def rotate(image: np.ndarray, angle: float) -> np.ndarray:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(image, matrix, (width, height), borderValue=255)


def test_deskew_reduces_a_small_deliberate_tilt() -> None:
    tilted = rotate(horizontal_label(), 8.0)
    before = estimate_skew_angle(tilted)
    corrected, applied = deskew_image(tilted)
    after = estimate_skew_angle(corrected)
    assert applied is not None
    assert before is not None
    assert after is None or abs(after) < abs(before)
    assert corrected.shape == tilted.shape


def test_deskew_leaves_blank_image_unchanged() -> None:
    blank = np.full((100, 180), 255, dtype=np.uint8)
    result, angle = deskew_image(blank)
    assert angle is None
    assert np.array_equal(result, blank)


def test_deskew_rejects_extreme_orientation() -> None:
    sideways = rotate(horizontal_label(), 45.0)
    _, angle = deskew_image(sideways, DeskewConfig(max_absolute_angle_degrees=20.0))
    assert angle is None
