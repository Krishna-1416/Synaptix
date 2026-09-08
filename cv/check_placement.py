"""Print visual placement data for one package image."""

from cv.contours import detect_regions
from cv.placement import build_placement


image_path = "sample_data/package.jpg"
regions = detect_regions(image_path)
placement = build_placement(image_path, regions)

print("Region count:", placement.region_count)
print("Image dimensions:", placement.image_width, "x", placement.image_height)
for index, region in enumerate(placement.regions, start=1):
    print(index, region)
