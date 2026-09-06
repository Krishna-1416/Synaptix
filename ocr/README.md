# ocr/ — OCR Engineer

**Stack:** PaddleOCR (primary), Tesseract/EasyOCR (fallback only), OpenCV (preprocessing handoff from `cv/`).

## Owns
- Text detection + recognition pipeline on package images
- Text normalization (cleanup, script handling, confidence filtering)
- Mapping raw OCR text → the `fields` object in the shared schema
  (manufacturer, country_of_origin, net_quantity, manufacture_date, mrp, consumer_care)

## Rule
The app must work with PaddleOCR alone. Tesseract/EasyOCR is an optional
fallback path — never a hard dependency for the main demo.

## Output contract
```json
{"image_id":"IMG001","texts":[{"text":"MRP ₹120","confidence":0.97,"bbox":[100,220,250,265]}]}
```
This raw output feeds into `fields` extraction (regex/NLP) which the
Legal & Rules Engineer's `engine.py` consumes.

## Suggested structure
```
ocr/
├── preprocess_handoff.py   # receives OpenCV-cleaned image from cv/
├── paddle_ocr_engine.py
├── fallback_ocr_engine.py
├── field_extractor.py       # raw texts -> normalized fields dict
└── tests/
    └── sample_outputs/
```

## Day 2 goal
Run PaddleOCR on 10 sample FMCG package images (put them in
`sample_data/`) and confirm text + bbox + confidence extraction works
before wiring into the backend.
