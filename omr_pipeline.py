import cv2
import numpy as np

def order_points(pts):
    # Sắp xếp 4 điểm theo thứ tự: trên-trái, trên-phải, dưới-phải, dưới-trái
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    # Lấy ma trận biến đổi phối cảnh và warp ảnh để ảnh phẳng và vuông vức
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

def process_omr_image(image, start_question_idx=1, num_choices=4, debug=False):
    if image is None:
        return [], None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Dùng ngưỡng nhị phân (Binary Inverse) để lấy vùng tối (mực in + vết tô)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

    # Tìm viền lớn nhất (khung hình chữ nhật bao quanh toàn bộ lưới đáp án)
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return [], None
        
    c = max(cnts, key=cv2.contourArea)
    
    # Tìm 4 góc của khung đáp án để bẻ phẳng bằng (Perspective Transform)
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    
    if len(approx) == 4:
        pts = approx.reshape(4, 2)
    else:
        rect = cv2.minAreaRect(c)
        pts = cv2.boxPoints(rect)
        
    output = four_point_transform(image, pts)
    warped_gray = four_point_transform(gray, pts)
    warped_thresh = cv2.threshold(warped_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    # Cắt bỏ phần viền đen sau khi bẻ phẳng
    pad = 2
    pad2 = 5
    if warped_thresh.shape[1] <= 2*pad2 or warped_thresh.shape[0] <= 2*pad:
        return [], output
        
    crop_t = warped_thresh[pad:warped_thresh.shape[0]-pad, pad2:warped_thresh.shape[1]-pad2]
    
    num_rows = 15 # Mỗi block luôn có 15 dòng
    ch = crop_t.shape[0] / num_rows

    ch = crop_t.shape[0] / num_rows

    # Lưới Toán học có bù trừ tỷ lệ (Weighted Mathematical Grid)
    # Vì sao trước đây Toán học thuần túy trượt tâm? Vì Cột "Số thứ tự" rộng hơn cột "A B C D"!
    # Vậy ta chỉ định trước: Cột số chiếm khoảng 23% chiều rộng khối, 77% còn lại chia đều cho 4 đáp án.
    q_col_ratio = 0.15
    start_x = int(crop_t.shape[1] * q_col_ratio)
    cw = (crop_t.shape[1] - start_x) / num_choices

    answers = []
    choices = ['A', 'B', 'C', 'D', 'E', 'F'][:num_choices]
    
    all_tots = []
    
    for i in range(num_rows):
        tots = []
        for j in range(num_choices):
            
            pad_cell_y = 6
            y1 = int(i * ch) + pad_cell_y
            y2 = int((i + 1) * ch) - pad_cell_y
            
            # Tính toán X theo Toán học thuần túy 100% (Miễn nhiễm ánh sáng)
            pad_cell_x = 4
            x1 = start_x + int(j * cw) + pad_cell_x
            x2 = start_x + int((j + 1) * cw) - pad_cell_x
            
            if y2 <= y1 or x2 <= x1:
                tots.append(0)
                continue
                
            cell = crop_t[y1:y2, x1:x2]
            tots.append(cv2.countNonZero(cell))
            
            # Vẽ hình chữ nhật lên ảnh gốc bao quanh ô tính điểm
            cv2.rectangle(output, 
                          (pad2 + x1, pad + y1), 
                          (pad2 + x2, pad + y2), 
                          (0, 255, 0), 2)
        all_tots.append(tots)
        
    # Tính Baseline cho TỪNG CỘT (loại bỏ nhiễu của việc in các số 1, 2, 3, 4 có lượng mực khác nhau)
    # Lấy giá trị trung vị (median) trong cột làm chuẩn (chống nhiễu nét in đậm nhạt rất tốt)
    col_baselines = []
    for j in range(num_choices):
        col_vals = sorted([all_tots[i][j] for i in range(num_rows)])
        # Lấy giá trị trung vị (chịu được việc học sinh tô cùng 1 cột lên tới 7 câu trên 15 câu)
        col_baselines.append(col_vals[len(col_vals)//2])
        
    for i in range(num_rows):
        tots = all_tots[i]
        
        # Ngưỡng: Dùng tỷ lệ động thay vì cộng số pixel cố định để hỗ trợ mọi độ phân giải (điện thoại vs webcam)
        # Một ô được coi là tô nếu mật độ pixel > 1.4 lần baseline và chênh lệch tối thiểu 80 pixel
        bubbled_indices = [j for j, val in enumerate(tots) if val > col_baselines[j] * 1.4 and val > col_baselines[j] + 80]        
        if len(bubbled_indices) == 0:
            choice_str = "" # Không tô
        else:
            choice_str = "".join([choices[b] for b in bubbled_indices])
            
        answers.append(choice_str)
        
        # In text lên ảnh kết quả
        for b in bubbled_indices:
            jx = start_x + int((b + 0.5) * cw)
            cv2.putText(output, choices[b], 
                        (pad2 + jx - 5, pad + int(i * ch) + int(ch/2) + 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                            
        if debug:
            print(f"  + Cau {start_question_idx + i}: Dap an {choice_str if choice_str else 'Chua to'} (Tots: {tots})")

    return answers, output


def process_omr(image_path, start_question_idx=1, num_choices=4):
    print(f"\n[{image_path}]")
    image = cv2.imread(image_path)
    answers, output = process_omr_image(image, start_question_idx, num_choices, debug=True)
    if output is not None:
        cv2.imwrite(image_path.replace(".png", "_result.png"), output)
        print(f"-> Da luu anh ket qua: {image_path.replace('.png', '_result.png')}")

    return answers

if __name__ == "__main__":
    start_idx = 1
    for f in ["answer_1.png", "answer_2.png", "answer_3.png"]:
        ans = process_omr(f"d:/OCR/crops/{f}", start_question_idx=start_idx)
        if ans:
            start_idx += len(ans)
