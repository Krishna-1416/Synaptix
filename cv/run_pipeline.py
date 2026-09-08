"""Run the final CV pipeline on one image and write handoff artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import cv2

from cv.pipeline import run_cv_pipeline, save_ocr_handoff


image_path = Path("sample_data/package.jpg")
output_dir = image_path.parent
result = run_cv_pipeline(str(image_path))

save_ocr_handoff(result.ocr_ready_image, str(output_dir / "ocr_ready.png"))
cv2.imwrite(str(output_dir / "regions_overlay.jpg"), result.region_overlay())
(output_dir / "backend_visual_checks.json").write_text(
    json.dumps(result.backend_payload(), indent=2), encoding="utf-8"
)
(output_dir / "cv_visual_details.json").write_text(
    json.dumps(result.detailed_visual_checks(), indent=2), encoding="utf-8"
)

print("OCR handoff: sample_data/ocr_ready.png")
print("Backend payload: sample_data/backend_visual_checks.json")
print("Detailed CV data: sample_data/cv_visual_details.json")
print("Readability:", result.readability.status)
print("Detected regions:", len(result.regions))
