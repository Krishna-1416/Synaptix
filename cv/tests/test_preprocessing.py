import cv2
import numpy as np
import pytest

from cv.preprocessing import PreprocessingConfig, preprocess_image


def synthetic_label() -> np.ndarray:
    image = np.full((160, 420, 3), 235, dtype=np.uint8)
    cv2.putText(image, "MRP Rs. 120", (25, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (30, 30, 30), 2)
    cv2.putText(image, "NET QTY 500 g", (25, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2)
    return image


def test_preprocess_returns_binary_single_channel_image() -> None:
    result = preprocess_image(synthetic_label())
    assert result.shape == (160, 420)
    assert result.dtype == np.uint8
    assert set(np.unique(result)).issubset({0, 255})


def test_preprocess_accepts_grayscale_image() -> None:
    result = preprocess_image(np.full((40, 50), 128, dtype=np.uint8))
    assert result.shape == (40, 50)


@pytest.mark.parametrize("bad_image", [None, np.array([]), np.zeros((4, 4, 2), dtype=np.uint8)])
def test_preprocess_rejects_invalid_images(bad_image: object) -> None:
    with pytest.raises(ValueError):
        preprocess_image(bad_image)  # type: ignore[arg-type]


def test_config_rejects_even_adaptive_window() -> None:
    with pytest.raises(ValueError, match="odd"):
        PreprocessingConfig(adaptive_block_size=10)
