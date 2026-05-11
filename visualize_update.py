import cv2
import os
import numpy as np

def refine_and_clean_box(img, x, y, w, h):
    """
    1. Tìm vị trí khung chính xác (Refine)
    2. Xóa viền khung và lấy phần ruột (Clean)
    """
    # Bước 1: Tìm vị trí khung chính xác (Refine)
    pad_search = 15
    roi_x, roi_y = max(0, x - pad_search), max(0, y - pad_search)
    roi_w, roi_h = min(img.shape[1] - roi_x, w + 2 * pad_search), min(img.shape[0] - roi_y, h + 2 * pad_search)
    
    search_roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
    gray = cv2.cvtColor(search_roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    main_cnt = None
    max_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > (w * h * 0.3) and area > max_area:
            max_area = area
            main_cnt = cnt
            
    if main_cnt is None:
        # Nếu không tìm thấy contour, trả về vùng mặc định đã xóa viền sơ bộ
        return img[y+2:y+h-2, x+2:x+w-2], (x, y, w, h)

    # Lấy tọa độ thật của cái khung sau khi Refine
    rx, ry, rw, rh = cv2.boundingRect(main_cnt)
    nx, ny, nw, nh = roi_x + rx, roi_y + ry, rw, rh
    
    # Bước 2: Xử lý xóa khung dựa trên Contour đã tìm thấy
    # Lấy chính xác vùng ảnh chứa cái khung
    refined_roi = img[ny:ny+nh, nx:nx+nw].copy()
    h_ref, w_ref = refined_roi.shape[:2]
    
    # Tạo mask trắng để dán chữ vào
    clean_bg = np.ones_like(refined_roi) * 255
    
    # Tạo mặt nạ vùng ruột (co vào 3 pixel để bỏ viền) từ contour đã dịch chuyển về tọa độ ROI
    local_cnt = main_cnt - [rx, ry] # Dịch contour về gốc (0,0) của ROI
    mask = np.zeros((h_ref, w_ref), dtype=np.uint8)
    cv2.drawContours(mask, [local_cnt], -1, 255, thickness=-1)
    mask = cv2.erode(mask, np.ones((5,5), np.uint8), iterations=1)
    
    # Dán phần ruột vào nền trắng
    clean_bg[mask == 255] = refined_roi[mask == 255]
    
    return clean_bg, (nx, ny, nw, nh)

def visualize_update(img_path, output_path):
    img = cv2.imread(img_path)
    if img is None: return
    h, w = img.shape[:2]
    
    regions = {
        "ho_va_ten": (300, 25, 600, 60),
        "lop":        (250, 80, 246, 50),
        "mon":        (500, 80, 246, 50),
        "mssv":       (458, 53, 217, 243),
        "ma_de":      (750, 53, 98, 243),
        "answer_1":   (110, 290, 236, 400),
        "answer_2":   (410, 290, 225, 400),
        "answer_3":   (690, 290, 228, 400),
    }
    
    crops_dir = os.path.join(os.path.dirname(img_path), "crops")
    if not os.path.exists(crops_dir): os.makedirs(crops_dir)
    result_img = img.copy()

    for name, (rx, ry, rw, rh) in regions.items():
        # Tọa độ mặc định theo tỷ lệ
        bx, by = int(rx * w / 1000), int(ry * h / 1000)
        bw, bh = int(rw * w / 1000), int(rh * h / 1000)
        
        # THỰC HIỆN REFINE + CLEAN
        clean_crop, (nx, ny, nw, nh) = refine_and_clean_box(img, bx, by, bw, bh)
        
        # Thêm chút padding trắng xung quanh ảnh cuối cho VietOCR dễ đọc
        #final_crop = cv2.copyMakeBorder(clean_crop, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        
        # Lưu crop sạch
        cv2.imwrite(os.path.join(crops_dir, f"{name}_refined.png"), clean_crop)
        
        # Vẽ visualize để kiểm tra (Vòng đỏ là vị trí khung thực tế đã tìm được)
        cv2.rectangle(result_img, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 2)
        cv2.putText(result_img, name, (nx, ny - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imwrite(output_path, result_img)
    print(f"Hoàn thành! Đã Refine tọa độ dựa trên contour và làm sạch ảnh.")

if __name__ == "__main__":
    visualize_update(r'D:\OCR\resultImage.jpg', r'D:\OCR\refined_answer_sheet_v4.png')
