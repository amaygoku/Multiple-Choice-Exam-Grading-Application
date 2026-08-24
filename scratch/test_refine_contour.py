import cv2
import numpy as np
import sys
sys.path.append("d:/OCR")
from detect_paper import align_document_image

def refine_box_contour(img, x, y, w, h, padding=15):
    roi_x = max(0, x - padding)
    roi_y = max(0, y - padding)
    roi_w = min(img.shape[1] - roi_x, w + 2 * padding)
    roi_h = min(img.shape[0] - roi_y, h + 2 * padding)
    
    roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
    if roi.size == 0:
        return x, y, w, h, (roi_x, roi_y, roi_w, roi_h), False
        
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_rect = (x, y, w, h)
    max_area = 0
    detected = False
    
    for cnt in contours:
        rx, ry, rw, rh = cv2.boundingRect(cnt)
        area = rw * rh
        if area > (w * h * 0.3) and area > max_area:
            max_area = area
            best_rect = (roi_x + rx, roi_y + ry, rw, rh)
            detected = True
            
    return best_rect[0], best_rect[1], best_rect[2], best_rect[3], (roi_x, roi_y, roi_w, roi_h), detected

img = cv2.imread("d:/OCR/ten_tv_v2/0a6ae3a4c79d46c31f8c.jpg")
aligned = align_document_image(img)
h, w = aligned.shape[:2]

X_CENTER_RATIO = 0.5320
WIDTH_RATIO = 0.7525
HEIGHT_RATIO = 0.0625
Y_START_RATIO = 0.04245
Y_STEP_RATIO = 0.06504

canvas = aligned.copy()
detected_count = 0

EXPAND_X = 2
EXPAND_Y = 2

for i in range(15):
    cy_ratio = Y_START_RATIO + i * Y_STEP_RATIO
    cx_ratio = X_CENTER_RATIO
    
    bx = int((cx_ratio - WIDTH_RATIO / 2.0) * w)
    by = int((cy_ratio - HEIGHT_RATIO / 2.0) * h)
    bw = int(WIDTH_RATIO * w)
    bh = int(HEIGHT_RATIO * h)
    
    bx = max(0, min(w - bw, bx))
    by = max(0, min(h - bh, by))
    
    rx, ry, rw, rh, roi, detected = refine_box_contour(aligned, bx, by, bw, bh, padding=15)
    
    roi_x, roi_y, roi_w, roi_h = roi
    # Draw base coordinate search region in light blue (like crop.py)
    cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), (255, 200, 0), 1)
    # Draw ROI search region boundary in thin red
    cv2.rectangle(canvas, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 0, 255), 1)
    
    if detected:
        # Snap to outer border
        rx = rx - EXPAND_X
        ry = ry - EXPAND_Y
        rw = rw + 2 * EXPAND_X
        rh = rh + 2 * EXPAND_Y
        color = (0, 255, 0)
        cv2.rectangle(canvas, (rx, ry), (rx+rw, ry+rh), color, 2)
        print(f"Row {i+1}: Detected at x={rx}, y={ry}, w={rw}, h={rh}")
        detected_count += 1
    else:
        color = (255, 128, 0)
        cv2.rectangle(canvas, (bx, by), (bx+bw, by+bh), color, 2)
        print(f"Row {i+1}: Fallback used")

print(f"Total detected: {detected_count}/15")
cv2.imwrite("d:/OCR/scratch/test_out_refine.png", canvas)
