# cv/ — Computer Vision Engineer

**Stack:** OpenCV, optional lightweight Hugging Face model (Florence-2 etc. — only if baseline isn't enough).

## Owns
- Preprocessing: grayscale, bilateral filtering, adaptive thresholding (feeds into `ocr/`)
- Deskewing and contour/label-region detection
- Bounding-box overlay generation (for the frontend's validation visualizer)
- Readability checks
- Calibrated font-height check:
  `Physical Height (mm) = (Pixel Height / Image DPI) × 25.4`
  — only compute this when image scale/DPI is actually known/calibrated;
  do not infer physical font size from raw pixel height alone.

## Suggested structure
```
cv/
├── preprocess.py        # grayscale, bilateral filter, adaptive threshold, deskew
├── bbox_overlay.py       # draws detected regions for frontend visualization
├── font_height.py         # calibrated physical measurement, DPI-aware
└── tests/
```

## Day 2 & Day 4 goal
Day 2: preprocessing output feeding cleanly into PaddleOCR.
Day 4: `visual_checks` object (readability, font_height, placement) populated
and merged into the shared inspection JSON.
