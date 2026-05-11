import cv2
import numpy as np

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def extract_id_and_code_image(image, num_cols):
    """
    Hàm đọc Mã sinh viên (MSSV) và Mã đề.
    - image_path: Đường dẫn tới ảnh crop của vùng chứa lưới số.
    - num_cols: Số cột (ví dụ MSSV là 6, Mã đề là 3).
    """
    if image is None:
        return ""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Dùng ngưỡng nhị phân (Binary Inverse) để lấy vùng tối (mực in + vết tô)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    # Tìm viền lớn nhất (khung hình chữ nhật bao quanh toàn bộ lưới)
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return ""
        
    c = max(cnts, key=cv2.contourArea)
    
    # Tự động bẻ phẳng vùng nhânh diện bằng Perspective Transform
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    
    if len(approx) == 4:
        pts = approx.reshape(4, 2)
    else:
        rect = cv2.minAreaRect(c)
        pts = cv2.boxPoints(rect)
        
    warped_thresh = four_point_transform(thresh, pts)
    
    # Cắt bỏ phần viền đen sau khi bẻ phẳng
    pad = 6
    if warped_thresh.shape[1] <= 2*pad or warped_thresh.shape[0] <= 2*pad:
        return ""
        
    crop_t = warped_thresh[pad:warped_thresh.shape[0]-pad, pad:warped_thresh.shape[1]-pad]
    
    # Kích thước mỗi ô trong lưới
    cw = crop_t.shape[1] / num_cols
    ch = crop_t.shape[0] / 9  # Vì các số từ 0 -> 9 (10 hàng)

    result_code = ""
    
    for i in range(num_cols):
        tots = []
        for j in range(9): # Từ 0 đến 9
            # Tính toán tọa độ của ô (j, i)
            cell = crop_t[int(j * ch):int((j + 1) * ch), int(i * cw):int((i + 1) * cw)]
            # Đếm lượng pixel đen (ảnh đảo ngược nên là màu trắng)
            tots.append(cv2.countNonZero(cell))
            
        m = min(tots)
        
        # Ngưỡng (Threshold): Một ô được coi là tô nếu mật độ pixel lớn hơn lượng baseline + 120
        # (Số in bình thường chiếm khoảng 180-300 pixel, ô tô tay chiếm lớn hơn rất nhiều)
        filled_digits = [str(digit) for digit, val in enumerate(tots) if val > m + 120]
        
        if len(filled_digits) == 0:
            result_code += "?"
        elif len(filled_digits) == 1:
            result_code += filled_digits[0]
        else:
            # Nếu tô nhiều ô trong cùng 1 cột, chỉ lấy ô đậm nhất, hoặc trả về lỗi
            best_digit = str(np.argmax(tots))
            result_code += best_digit

    return result_code


def extract_id_and_code(image_path, num_cols):
    image = cv2.imread(image_path)
    if image is None:
        print(f"Could not read {image_path}")
        return ""
    return extract_id_and_code_image(image, num_cols)

if __name__ == "__main__":
    # Ảnh trắng (chưa tô) nên sẽ trả về "???" và "??????"
    ma_de = extract_id_and_code('d:/OCR/crops/ma_de.png', 3)
    mssv = extract_id_and_code('d:/OCR/crops/mssv.png', 8)
    
    print("Ma de du doan:", ma_de)
    print("MSSV du doan:", mssv)
