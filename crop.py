import cv2
import os


REGIONS_V1 = {
        "ho_va_ten": (155, 10, 750, 70),
        "lop":        (115, 72, 290, 64),
        "mon":        (545, 72, 430, 64),
        "mssv":       (120, 170, 475, 335),
        "ma_de":      (720, 170, 210, 335),
        "answer_1":   (57, 495, 310, 495),
        "answer_2":   (355, 495, 310, 495),
        "answer_3":   (653, 495, 310, 495),
}

# Khung code v2 để người dùng tự sửa tham số tọa độ (định dạng: rx, ry, rw, rh trong hệ 1000x1000)
REGIONS_V2 = {
        "ho_va_ten": (165, 22, 730, 65),
        "lop":        (125, 80, 285, 65),
        "mon":        (545, 80, 435, 65),
        "mssv":       (130, 170, 465, 320),
        "ma_de":      (720, 170, 190, 320),
        "answer_1":   (72, 500, 280, 490),
        "answer_2":   (377, 500, 280, 490),
        "answer_3":   (690, 500, 280, 490),
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

def crop_regions_image(img, layout_version="v2"):
    """Crop configured regions from an aligned answer sheet image based on layout_version."""
    if img is None:
        return None, {}

    h, w = img.shape[:2]
    result_img = img.copy()
    crops = {}

    regions = REGIONS_V2 if layout_version == "v2" else REGIONS_V1

    for name, (rx, ry, rw, rh) in regions.items():
        bx, by = int(rx * w / 1000), int(ry * h / 1000)
        bw, bh = int(rw * w / 1000), int(rh * h / 1000)
        
        nx, ny, nw, nh = refine_box_contour(img, bx, by, bw, bh)
        
        margin = 2 if name in ("mssv", "ma_de") else 5
        cx, cy = max(0, nx - margin), max(0, ny - margin)
        cw, ch = min(img.shape[1] - cx, nw + 2 * margin), min(img.shape[0] - cy, nh + 2 * margin)
        
        crops[name] = img[cy:cy+ch, cx:cx+cw]
        
        cv2.rectangle(result_img, (bx, by), (bx + bw, by + bh), (255, 200, 0), 2)
        cv2.rectangle(result_img, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 4)
        cv2.putText(result_img, name, (nx, ny - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    return result_img, crops


def crop_regions(img_path, output_visualized_path, crops_dir, layout_version="v2"):
    img = cv2.imread(img_path)
    result_img, crops = crop_regions_image(img, layout_version=layout_version)
    if result_img is None:
        return False

    os.makedirs(crops_dir, exist_ok=True)
    for name, crop in crops.items():
        cv2.imwrite(os.path.join(crops_dir, f"{name}.png"), crop)

    cv2.imwrite(output_visualized_path, result_img)
    return True

