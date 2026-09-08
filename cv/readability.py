from dataclasses import dataclass
import cv2

from cv.preprocessing import load_image, to_grayscale


@dataclass(frozen=True)
class ReadabilityResult:
    status: str
    sharpness_score: float
    contrast_score: float

    def as_dict(self):
        return {
            "status": self.status,
            "sharpness_score": self.sharpness_score,
            "contrast_score": self.contrast_score,
        }


def assess_readability(image, min_sharpness=45.0, min_contrast=22.0):
    source = load_image(image)
    gray = to_grayscale(source)

    # Higher score means sharper image
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Higher score means stronger contrast
    contrast = float(gray.std())

    if sharpness >= min_sharpness and contrast >= min_contrast:
        status = "good"
    elif sharpness < min_sharpness and contrast < min_contrast:
        status = "poor"
    else:
        status = "review"

    return ReadabilityResult(status, sharpness, contrast)