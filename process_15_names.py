import cv2
import numpy as np
import os
from pathlib import Path
from detect_paper import align_document_image

def refine_box_contour(img, x, y, w, h, padding=15):
    """
    Refines a bounding box by looking for contours within a small region of interest.
    Uses the exact same algorithm as crop.py.
    """
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
        # Candidate should have a reasonable size (at least 30% of target area)
        if area > (w * h * 0.3) and area > max_area:
            max_area = area
            best_rect = (roi_x + rx, roi_y + ry, rw, rh)
            detected = True
            
    return best_rect[0], best_rect[1], best_rect[2], best_rect[3], (roi_x, roi_y, roi_w, roi_h), detected

def get_15_boxes(aligned_img):
    """
    Detects the 15 name bounding boxes on the aligned page using the local contour refinement method.
    Returns a list of 15 tuples: ((rx, ry, rw, rh), detected_directly, (roi_x, roi_y, roi_w, roi_h))
    """
    h, w = aligned_img.shape[:2]
    
    # --- CONFIGURABLE COORDINATE PARAMETERS (Ratios relative to image size) ---
    X_CENTER_RATIO = 0.5320   # Horizontal center position of the name fields
    WIDTH_RATIO = 0.7525      # Expected inner width of the name boxes
    HEIGHT_RATIO = 0.0325     # Expected inner height of the name boxes
    
    Y_START_RATIO = 0.03845   # Center position of the first row (i = 0)
    Y_STEP_RATIO = 0.06504    # Vertical distance between consecutive rows
    
    # Padding to create the search ROI (same as refine_box_contour padding)
    PADDING_PX = 15
    
    # Offset parameters to expand the detected inner box to the outer border of the cell lines
    EXPAND_X = 2
    EXPAND_Y = 2
    # --------------------------------------------------------------------------
    
    final_boxes = []
    
    for i in range(15):
        # Calculate theoretical center and base box coordinates for this row
        cy_ratio = Y_START_RATIO + i * Y_STEP_RATIO
        
        bx = int((X_CENTER_RATIO - WIDTH_RATIO / 2.0) * w)
        by = int((cy_ratio - HEIGHT_RATIO / 2.0) * h)
        bw = int(WIDTH_RATIO * w)
        bh = int(HEIGHT_RATIO * h)
        
        # Ensure base box is within image boundaries
        bx = max(0, min(w - bw, bx))
        by = max(0, min(h - bh, by))
        
        # Refine using the exact refine_box_contour logic from crop.py
        rx, ry, rw, rh, roi, detected = refine_box_contour(aligned_img, bx, by, bw, bh, padding=PADDING_PX)
        
        # Expand slightly to snap perfectly to the outer border of the printed cell lines (just like crop.py's margin)
        if detected:
            rx = rx - EXPAND_X
            ry = ry - EXPAND_Y
            rw = rw + 2 * EXPAND_X
            rh = rh + 2 * EXPAND_Y
        else:
            # Expand theoretical fallback box as well for consistency
            rx = bx - EXPAND_X
            ry = by - EXPAND_Y
            rw = bw + 2 * EXPAND_X
            rh = bh + 2 * EXPAND_Y
            
        final_boxes.append(((rx, ry, rw, rh), detected, roi))
        
    return final_boxes

def process_single_crop(aligned_img, box):
    """
    Crops the name field, removes boundary line margins, and enhances contrast.
    """
    rx, ry, rw, rh = box
    h, w = aligned_img.shape[:2]
    
    # Clip coordinates to image boundary
    rx1 = max(0, rx)
    ry1 = max(0, ry)
    rx2 = min(w, rx + rw)
    ry2 = min(h, ry + rh)
    
    roi = aligned_img[ry1:ry2, rx1:rx2]
    roi_h, roi_w = roi.shape[:2]
    
    # Crop a small margin to exclude the box borders
    margin = 5
    if roi_w > 2 * margin and roi_h > 2 * margin:
        final_crop = roi[margin:roi_h-margin, margin:roi_w-margin]
    else:
        final_crop = roi
        
    # Contrast enhancement (convert to LAB, normalize L channel, increase contrast)
    lab = cv2.cvtColor(final_crop, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.normalize(l, None, 0, 255, cv2.NORM_MINMAX)
    l = cv2.addWeighted(l, 1.2, l, 0, -30)
    final_lab = cv2.merge((l, a, b))
    enhanced = cv2.cvtColor(final_lab, cv2.COLOR_LAB2BGR)
    
    return enhanced

def main():
    input_dir = Path("d:/OCR/ten_tv_v3")
    output_dir = Path("d:/OCR/ten_tv_v3_processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    image_paths = sorted(list(input_dir.glob("*.jpg")) + list(input_dir.glob("*.png")))
    print(f"Found {len(image_paths)} images to process.")
    
    for idx, path in enumerate(image_paths, start=1):
        print(f"[{idx}/{len(image_paths)}] Processing {path.name}...")
        img = cv2.imread(str(path))
        if img is None:
            print("  Error: Could not read image!")
            continue
            
        aligned = align_document_image(img)
        if aligned is None:
            print("  Error: Paper alignment failed!")
            continue
            
        # Create a directory for this sheet's crops
        sheet_stem = path.stem
        sheet_dir = output_dir / sheet_stem
        sheet_dir.mkdir(parents=True, exist_ok=True)
        
        boxes = get_15_boxes(aligned)
        
        canvas = aligned.copy()
        
        for box_idx, (box, detected, roi) in enumerate(boxes, start=1):
            rx, ry, rw, rh = box
            roi_x, roi_y, roi_w, roi_h = roi
            
            # 1. Process and save the cropped name field
            cropped_name = process_single_crop(aligned, box)
            crop_path = sheet_dir / f"crop_{box_idx:02d}.png"
            cv2.imwrite(str(crop_path), cropped_name)
            
            # 2. Draw bounding boxes and text on the visualization canvas
            # Red for the search ROI boundary (thin line, thickness 1)
            cv2.rectangle(canvas, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 0, 255), 1)
            
            # Green for direct contour detection, Blue/Orange for interpolated box (thickness 2)
            color = (0, 255, 0) if detected else (255, 128, 0)
            status_text = "Det" if detected else "Interp"
            
            cv2.rectangle(canvas, (rx, ry), (rx+rw, ry+rh), color, 2)
            cv2.putText(canvas, f"{box_idx} ({status_text})", (rx + 8, ry + 22), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                        
        # Save visualization
        viz_path = output_dir / f"{sheet_stem}_visualized.png"
        cv2.imwrite(str(viz_path), canvas)
        
        detected_count = sum(1 for _, det, _ in boxes if det)
        print(f"  Successfully processed {path.name}. Detected: {detected_count}/15. Saved to {sheet_dir}/ and {viz_path.name}")
        
    print("\nAll sheets processed successfully!")

if __name__ == "__main__":
    main()
