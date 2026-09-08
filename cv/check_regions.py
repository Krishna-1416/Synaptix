import cv2

from cv.contours import detect_regions, draw_regions

image = cv2.imread("sample_data/package.jpg")

regions = detect_regions(image)
overlay = draw_regions(image, regions)

cv2.imwrite("sample_data/regions_overlay.jpg", overlay)

print("Detected regions:", len(regions))

for i, region in enumerate(regions, start=1):
    print(i, region.as_dict())