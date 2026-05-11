import cv2
import os


REGIONS = {
    "ho_va_ten": (180, 25, 700, 60),
    "lop":        (140, 90, 260, 60),
    "mon":        (540, 90, 410, 60),
    "mssv":       (130, 165, 470, 300),
    "ma_de":      (710, 165, 220, 300),
    "answer_1":   (80, 465, 290, 450),
    "answer_2":   (355, 465, 290, 450),
    "answer_3":   (645, 465, 290, 450),
}

def refine_box_contour(img, x, y, w, h):
    padding = 10
    roi_x = max(0, x - padding)
    roi_y = max(0, y - padding)
    roi_w = min(img.shape[1] - roi_x, w + 2 * padding)
    roi_h = min(img.shape[0] - roi_y, h + 2 * padding)
    
    roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
    if roi.size == 0:
        return x, y, w, h
        
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_rect = (x, y, w, h)
    max_area = 0
    
    for cnt in contours:
        rx, ry, rw, rh = cv2.boundingRect(cnt)
        area = rw * rh
        if area > (w * h * 0.3) and area > max_area:
            max_area = area
            best_rect = (roi_x + rx, roi_y + ry, rw, rh)
            
    return best_rect

def crop_regions_image(img):
    """Crop configured regions from an aligned answer sheet image."""
    if img is None:
        return None, {}

    h, w = img.shape[:2]
    result_img = img.copy()
    crops = {}

    for name, (rx, ry, rw, rh) in REGIONS.items():
        bx, by = int(rx * w / 1000), int(ry * h / 1000)
        bw, bh = int(rw * w / 1000), int(rh * h / 1000)
        
        nx, ny, nw, nh = refine_box_contour(img, bx, by, bw, bh)
        
        margin = 5
        cx, cy = max(0, nx - margin), max(0, ny - margin)
        cw, ch = min(img.shape[1] - cx, nw + 2 * margin), min(img.shape[0] - cy, nh + 2 * margin)
        
        crops[name] = img[cy:cy+ch, cx:cx+cw]
        
        cv2.rectangle(result_img, (bx, by), (bx + bw, by + bh), (255, 200, 0), 2)
        cv2.rectangle(result_img, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 4)
        cv2.putText(result_img, name, (nx, ny - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    return result_img, crops


def crop_regions(img_path, output_visualized_path, crops_dir):
    img = cv2.imread(img_path)
    result_img, crops = crop_regions_image(img)
    if result_img is None:
        return False

    os.makedirs(crops_dir, exist_ok=True)
    for name, crop in crops.items():
        cv2.imwrite(os.path.join(crops_dir, f"{name}.png"), crop)

    cv2.imwrite(output_visualized_path, result_img)
    return True
