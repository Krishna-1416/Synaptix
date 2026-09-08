from cv.readability import assess_readability

result = assess_readability("sample_data/package.jpg")

print("Readability:", result.status)
print("Sharpness:", round(result.sharpness_score, 2))
print("Contrast:", round(result.contrast_score, 2))
print("Backend data:", result.as_dict())