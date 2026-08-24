import cv2
import numpy as np
import sys
sys.path.append("d:/OCR")
from detect_paper import align_document_image

img = cv2.imread("d:/OCR/ten_tv_v2/010f6b4ae375622b3b64.jpg")
aligned = align_document_image(img)
h, w = aligned.shape[:2]

gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
blurred = cv2.bilateralFilter(gray, 5, 75, 75)
edges = cv2.Canny(blurred, 30, 150)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

expected_y_centers = [(4.22 + i * 6.458) * h / 100.0 for i in range(15)]

candidates = []
for cnt in contours:
    rx, ry, rw, rh = cv2.boundingRect(cnt)
    aspect = rw / float(rh) if rh > 0 else 0
    if 400 <= rw <= 800 and 40 <= rh <= 180 and aspect >= 3.0:
        candidates.append((rx, ry, rw, rh))

row_candidates = {i: [] for i in range(15)}
for rx, ry, rw, rh in candidates:
    cy = ry + rh / 2.0
    best_dist = float('inf')
    best_row = -1
    for i, ey in enumerate(expected_y_centers):
        dist = abs(cy - ey)
        if dist < best_dist:
            best_dist = dist
            best_row = i
    if best_dist < 0.04 * h:
        row_candidates[best_row].append((rx, ry, rw, rh))

canvas = aligned.copy()

# Expansion offset parameters (adjust these to expand the box)
EXPAND_X = 2
EXPAND_Y = 2

for i in range(15):
    cands = row_candidates[i]
    single_normal = [c for c in cands if 45 <= c[3] <= 85]
    if len(single_normal) == 1:
        rx, ry, rw, rh = single_normal[0]
        
        # Original (drawn in Green)
        cv2.rectangle(canvas, (rx, ry), (rx+rw, ry+rh), (0, 255, 0), 1)
        
        # Expanded (drawn in Blue)
        erx = rx - EXPAND_X
        ery = ry - EXPAND_Y
        erw = rw + 2 * EXPAND_X
        erh = rh + 2 * EXPAND_Y
        cv2.rectangle(canvas, (erx, ery), (erx+erw, ery+erh), (255, 0, 0), 2)
        
print("Saved d:/OCR/scratch/test_expand.png")
cv2.imwrite("d:/OCR/scratch/test_expand.png", canvas)
