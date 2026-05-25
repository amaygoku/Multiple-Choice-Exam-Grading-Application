import cv2
import os

def refine_box_contour(img, x, y, w, h):
    """
    Refines a bounding box by looking for contours within a small region of interest.
    """
    # Define ROI with padding to ensure we capture the whole box line
    padding = 10
    roi_x = max(0, x - padding)
    roi_y = max(0, y - padding)
    roi_w = min(img.shape[1] - roi_x, w + 2 * padding)
    roi_h = min(img.shape[0] - roi_y, h + 2 * padding)
    
    roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
    if roi.size == 0:
        return x, y, w, h
    
    # Preprocessing for contour detection
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Binary inverse thresholding works well for black lines on white paper
    # Using adaptive thresholding to be robust to light variations
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, 2)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_rect = (x, y, w, h)
    max_area = 0
    
    # Filter for the best candidate contour
    for cnt in contours:
        rx, ry, rw, rh = cv2.boundingRect(cnt)
        area = rw * rh
        # Candidate should have a reasonable size (at least 30% of target area)
        if area > (w * h * 0.3) and area > max_area:
            max_area = area
            best_rect = (roi_x + rx, roi_y + ry, rw, rh)
            
    return best_rect

def visualize(img_path, output_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not load {img_path}")
        return
    
    h, w = img.shape[:2]
    
    # Normalized coordinates (0-1000) for Answer_sheet_A4.pdf layout
    # Calculated from detection in answer_sheet_page1.png
    regions = {
        "ho_va_ten": (165, 22, 730, 65),
        "lop":        (125, 80, 285, 65),
        "mon":        (545, 80, 435, 65),
        "mssv":       (130, 170, 465, 320),
        "ma_de":      (720, 170, 190, 320),
        "answer_1":   (72, 500, 260, 475),
        "answer_2":   (377, 500, 260, 475),
        "answer_3":   (690, 500, 260, 475),
    }
    
    result_img = img.copy()
    
    # Create crops directory if it doesn't exist
    crops_dir = os.path.join(os.path.dirname(img_path), "crops")
    if not os.path.exists(crops_dir):
        os.makedirs(crops_dir)
        print(f"Created directory: {crops_dir}")
    
    for name, (rx, ry, rw, rh) in regions.items():
        # Step 1: Base coordinates from normalized values
        bx = int(rx * w / 1000)
        by = int(ry * h / 1000)
        bw = int(rw * w / 1000)
        bh = int(rh * h / 1000)
        
        # Step 2: Refine using contours
        nx, ny, nw, nh = refine_box_contour(img, bx, by, bw, bh)
        
        # Step 3: Crop the refined region and save
        margin = 2 if name in ("mssv", "ma_de") else 5
        cx = max(0, nx - margin)
        cy = max(0, ny - margin)
        cw = min(img.shape[1] - cx, nw + 2 * margin)
        ch = min(img.shape[0] - cy, nh + 2 * margin)
        
        crop = img[cy:cy+ch, cx:cx+cw]
        
        crop_filename = f"{name}.png"
        crop_path = os.path.join(crops_dir, crop_filename)
        cv2.imwrite(crop_path, crop)
        
        # Step 4: Draw refined rectangles for visualization
        # Search region in light blue (thicker for high res)
        cv2.rectangle(result_img, (bx, by), (bx + bw, by + bh), (255, 200, 0), 2)
        # Refined box in red
        cv2.rectangle(result_img, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 4)
        
        # Put label
        cv2.putText(result_img, name, (nx, ny - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        
    cv2.imwrite(output_path, result_img)
    print(f"Saved visualization with contour refinement to {output_path}")
    print(f"Individual crops saved to {crops_dir}")

if __name__ == "__main__":
    visualize(r'D:\OCR\resultImage.jpg', r'D:\OCR\refined_answer_sheet.png')
