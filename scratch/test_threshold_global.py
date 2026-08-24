import cv2
import numpy as np
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

h, w = aligned.shape[:2]
gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
_, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

# Find contours globally
contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

expected_y_centers = [(4.22 + i * 6.458) * h / 100.0 for i in range(15)]

# Filter candidates
candidates = []
for cnt in contours:
    rx, ry, rw, rh = cv2.boundingRect(cnt)
    aspect = rw / float(rh) if rh > 0 else 0
    # Wide rectangles
    if 350 <= rw <= 800 and 35 <= rh <= 110 and aspect >= 3.0:
        candidates.append((rx, ry, rw, rh))

# Match candidates to the closest row
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
    if best_row != -1 and best_dist < 0.04 * h:
        row_candidates[best_row].append((rx, ry, rw, rh))

# Resolve rows
canvas = aligned.copy()
detected_count = 0
for i in range(15):
    cands = row_candidates[i]
    if len(cands) >= 1:
        # Pick the one closest to the center line
        ey = expected_y_centers[i]
        cands.sort(key=lambda c: abs((c[1] + c[3]/2.0) - ey))
        rx, ry, rw, rh = cands[0]
        color = (0, 255, 0)
        cv2.rectangle(canvas, (rx, ry), (rx+rw, ry+rh), color, 2)
        cv2.putText(canvas, f"{i+1} (Det)", (rx + 8, ry + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        detected_count += 1
        print(f"Row {i+1}: Detected at x={rx}, y={ry}, w={rw}, h={rh}")
    else:
        # Interpolate
        print(f"Row {i+1}: Not detected, needs fallback")

print(f"Total detected: {detected_count}/15")
cv2.imwrite("d:/OCR/scratch/test_out_global.png", canvas)
print("Saved d:/OCR/scratch/test_out_global.png")
