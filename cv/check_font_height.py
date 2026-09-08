"""Demonstrate safe font-height measurement from detected regions."""

from cv.contours import detect_regions
from cv.font_height import measure_region_height


image_path = "sample_data/package.jpg"
regions = detect_regions(image_path)

if not regions:
    raise SystemExit("No text-like regions found.")

# No DPI is supplied for a phone/downloaded image, so physical_height_mm must
# remain None. This is the safe and expected result.
result = measure_region_height(regions[-1])
print("Detected pixel height:", result.pixel_height)
print("Physical height in mm:", result.physical_height_mm)
print("Status:", result.status)

# Example only: use this form only when 300 DPI is genuinely known/calibrated.
example = measure_region_height(regions[-1], dpi=300)
print("Example at known 300 DPI:", round(example.physical_height_mm, 3), "mm")
