import cv2
import numpy as np
from pathlib import Path
import sys
sys.path.append("d:/OCR")
from detect_paper import align_document_image

img = cv2.imread("d:/OCR/ten_tv_v2/010f6b4ae375622b3b64.jpg")
if img is None:
    print("Could not read image!")
    exit(1)
aligned = align_document_image(img)
if aligned is None:
    print("Alignment failed!")
    exit(1)

# Methods:
gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
blurred = cv2.bilateralFilter(gray, 5, 75, 75)

# 1. Canny
edges = cv2.Canny(blurred, 30, 150)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

# 2. Global thresholding
_, thresh_global = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

# 3. Adaptive thresholding
thresh_adaptive = cv2.adaptiveThreshold(
    gray,
    255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY_INV,
    31,
    9
)

# Test row 0 coordinates:
h, w = aligned.shape[:2]
cy = 0.0422 * h
cx = 0.5330 * w
rw = int(0.7479 * w)
rh = int(0.0377 * h)
rx = int(cx - rw/2)
ry = int(cy - rh/2)

pad_x = int(0.04 * w)
pad_y = int(0.015 * h)

x1 = max(0, rx - pad_x)
y1 = max(0, ry - pad_y)
x2 = min(w, rx + rw + pad_x)
y2 = min(h, ry + rh + pad_y)

print(f"ROI coordinates: x1={x1}, y1={y1}, x2={x2}, y2={y2}")

canvas = aligned.copy()
cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 1)

for name, bin_img in [("Canny", closed), ("Global", thresh_global), ("Adaptive", thresh_adaptive)]:
    roi_bin = bin_img[y1:y2, x1:x2]
    contours, _ = cv2.findContours(roi_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        aspect = bw / float(bh) if bh > 0 else 0
        if 350 <= bw <= 800 and 25 <= bh <= 110 and aspect >= 3.0:
            print(f"{name}: x={x1+bx}, y={y1+by}, w={bw}, h={bh}")
            # Use different colors to distinguish
            color = (0, 255, 0) if name == "Canny" else ((255, 0, 0) if name == "Global" else (0, 255, 255))
            cv2.rectangle(canvas, (x1+bx, y1+by), (x1+bx+bw, y1+by+bh), color, 2)
            cv2.putText(canvas, name, (x1+bx+5, y1+by+15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

cv2.imwrite("d:/OCR/scratch/test_out.png", canvas)
print("Saved d:/OCR/scratch/test_out.png")
