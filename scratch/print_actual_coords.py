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

for i in range(15):
    cands = row_candidates[i]
    single_normal = [c for c in cands if 45 <= c[3] <= 85]
    if len(single_normal) == 1:
        rx, ry, rw, rh = single_normal[0]
        cy = ry + rh / 2.0
        print(f"Row {i+1}: y_center={cy:.2f} (ratio={cy/h:.5f}) | x_center={rx + rw/2.0:.2f} (ratio={(rx + rw/2.0)/w:.5f}) | w_ratio={rw/w:.5f}, h_ratio={rh/h:.5f}")
    else:
        print(f"Row {i+1}: Not resolved (found {len(single_normal)} candidates)")
