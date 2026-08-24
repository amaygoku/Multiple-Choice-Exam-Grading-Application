import cv2
import numpy as np
import sys
sys.path.append("d:/OCR")
from detect_paper import align_document_image

img = cv2.imread("d:/OCR/ten_tv_v2/010f6b4ae375622b3b64.jpg")
aligned = align_document_image(img)
h, w = aligned.shape[:2]

# Configurable coordinate parameters (calibrated to the actual grid)
X_CENTER_RATIO = 0.5320
WIDTH_RATIO = 0.7525
HEIGHT_RATIO = 0.0625
Y_START_RATIO = 0.04245
Y_STEP_RATIO = 0.06504

# Padding ratios
ROI_PAD_X_RATIO = 0.015
ROI_PAD_Y_RATIO = 0.030

canvas = aligned.copy()
detected_count = 0

# Offset adjustment to expand box to outer border
EXPAND_X = 2
EXPAND_Y = 2

for i in range(15):
    cy_ratio = Y_START_RATIO + i * Y_STEP_RATIO
    cx_ratio = X_CENTER_RATIO
    
    roi_w = int((WIDTH_RATIO + 2 * ROI_PAD_X_RATIO) * w)
    roi_h = int((HEIGHT_RATIO + 2 * ROI_PAD_Y_RATIO) * h)
    roi_x = int((cx_ratio - (WIDTH_RATIO / 2.0 + ROI_PAD_X_RATIO)) * w)
    roi_y = int((cy_ratio - (HEIGHT_RATIO / 2.0 + ROI_PAD_Y_RATIO)) * h)
    
    rx1 = max(0, roi_x)
    ry1 = max(0, roi_y)
    rx2 = min(w, roi_x + roi_w)
    ry2 = min(h, roi_y + roi_h)
    
    # Preprocess local ROI crop
    roi_img = aligned[ry1:ry2, rx1:rx2]
    roi_gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
    roi_blur = cv2.bilateralFilter(roi_gray, 5, 75, 75)
    roi_edges = cv2.Canny(roi_blur, 30, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    roi_closed = cv2.morphologyEx(roi_edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    contours, _ = cv2.findContours(roi_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_candidate = None
    best_diff = float('inf')
    
    target_w = WIDTH_RATIO * w
    target_h = HEIGHT_RATIO * h
    
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        aspect = bw / float(bh) if bh > 0 else 0
        
        # Check criteria (wide rectangle)
        if 350 <= bw <= 800 and 35 <= bh <= 110 and aspect >= 3.0:
            diff_w = abs(bw - target_w) / target_w
            diff_h = abs(bh - target_h) / target_h
            local_cy = by + bh / 2.0
            target_local_cy = (ry2 - ry1) / 2.0
            diff_y = abs(local_cy - target_local_cy) / (ry2 - ry1)
            
            total_diff = diff_w + diff_h + 2.0 * diff_y
            if total_diff < best_diff:
                best_diff = total_diff
                best_candidate = (rx1 + bx, ry1 + by, bw, bh)
                
    if best_candidate is not None:
        rx, ry, rw, rh = best_candidate
        
        # Apply offset expansion to snap to outer black border
        rx = rx - EXPAND_X
        ry = ry - EXPAND_Y
        rw = rw + 2 * EXPAND_X
        rh = rh + 2 * EXPAND_Y
        
        color = (0, 255, 0)
        cv2.rectangle(canvas, (rx, ry), (rx+rw, ry+rh), color, 2)
        cv2.rectangle(canvas, (rx1, ry1), (rx2, ry2), (0, 0, 255), 1)
        print(f"Row {i+1}: Detected at x={rx}, y={ry}, w={rw}, h={rh}")
        detected_count += 1
    else:
        # Fallback
        fallback_w = int(WIDTH_RATIO * w)
        fallback_h = int(HEIGHT_RATIO * h)
        fallback_x = int((X_CENTER_RATIO - WIDTH_RATIO / 2.0) * w)
        fallback_y = int((cy_ratio - HEIGHT_RATIO / 2.0) * h)
        fallback_x = max(0, min(w - fallback_w, fallback_x))
        fallback_y = max(0, min(h - fallback_h, fallback_y))
        
        cv2.rectangle(canvas, (fallback_x, fallback_y), (fallback_x+fallback_w, fallback_y+fallback_h), (255, 128, 0), 2)
        cv2.rectangle(canvas, (rx1, ry1), (rx2, ry2), (0, 0, 255), 1)
        print(f"Row {i+1}: Fallback used")

print(f"Total detected: {detected_count}/15")
cv2.imwrite("d:/OCR/scratch/test_out_canny_roi.png", canvas)
