import json
import os
import cv2
import sys
import difflib
import numpy as np
from PIL import Image
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from extract_code import extract_id_and_code
from omr_pipeline import process_omr

# ------------------ CẤU HÌNH OCR TÊN ---------------
try:
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg
    
    # Cấu hình theo bạn đã có trong notebook
    # Chúng tôi dùng cấu hình mặc định (vgg_transformer) hoặc cấu hình bạn đã test
    config = Cfg.load_config_from_name('vgg_seq2seq')
    
    # Bạn có thể trỏ vào trọng số model bạn dùng:
    # config['weights'] = './weights.pth' 
    config['weights'] = './seq2seqocr.pth'
    config['cnn']['pretrained']=False
    config['predictor']['beamsearch'] = True
    config['device'] = 'cpu'
    
    detector = Predictor(config)
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("[WARNING] Không load được thư viện vietocr. Vui lòng chạy trong môi trường có cài đặt vietocr nếu muốn trích xuất tên.")
except Exception as e:
    OCR_AVAILABLE = False
    print(f"[WARNING] Gặp lỗi khi load model vietocr: {e}")
def crop_to_text(img, padding=5):
    # 1. Chuyển về ảnh xám (Thay thế .convert('L'))
    if len(img.shape) == 3: # Nếu là ảnh màu
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # 2. Tạo ảnh nhị phân (Threshold)
    # Tìm các pixel tối (mực) trên nền sáng
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 3. Tìm tọa độ của các pixel mực
    coords = cv2.findNonZero(binary)
    
    if coords is None:
        return img
        
    # Tìm khung bao quanh (x, y, w, h)
    x, y, w, h = cv2.boundingRect(coords)
    
    # 4. Thêm padding và tính toán vị trí cắt
    y_min = max(0, y - padding)
    y_max = min(img.shape[0], y + h + padding)
    x_min = max(0, x - padding)
    x_max = min(img.shape[1], x + w + padding)
    
    # 5. Cắt ảnh bằng NumPy Slicing (Thay thế .crop)
    return img[y_min:y_max, x_min:x_max]

def adaptive_resize_pad(img_np, target_h=50, target_w=512):
    h, w = img_np.shape[:2]
    
    # 1. Tính toán width dựa trên target_h
    new_w = int(w * (target_h / h))
    
    # 2. Nếu width quá lớn so với model (ví dụ > 512), 
    # lúc này mới bắt buộc phải bóp width lại
    if new_w > target_w:
        resized = cv2.resize(img_np, (target_w, target_h), interpolation=cv2.INTER_AREA)
        new_w = target_w
    else:
        # Nếu width nhỏ, resize giữ đúng tỷ lệ để nét chữ to rõ
        resized = cv2.resize(img_np, (new_w, target_h), interpolation=cv2.INTER_AREA)

    # 3. Padding lề phải bằng màu trắng (255) để đạt đúng 512px
    pad_right = target_w - new_w
    final_img = cv2.copyMakeBorder(resized, 0, 0, 0, pad_right, 
                                   cv2.BORDER_CONSTANT, value=255)
    
    return final_img

def kmeans_binarize(img):
    if img is None:
        return None
    
    # 1. Kiểm tra nếu ảnh là ảnh màu thì chuyển sang xám
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    
    # Chuyển dữ liệu về float32 cho K-means
    pixel_values = gray.reshape((-1, 1))
    pixel_values = np.float32(pixel_values)
    
    # Chạy K-means (K=2)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    k = 2
    _, labels, centers = cv2.kmeans(pixel_values, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # Xác định cụm nào là nền (sáng hơn)
    centers = np.uint8(centers)
    if centers[0] > centers[1]:
        bg_label, fg_label = 0, 1
    else:
        bg_label, fg_label = 1, 0
        
    # Tạo ảnh kết quả: Nền=255, Chữ=0
    res = np.zeros_like(labels, dtype=np.uint8)
    res[labels == bg_label] = 255
    res[labels == fg_label] = 0
    
    return res.reshape(gray.shape)

def ocr_read_name(image_path):
    if not OCR_AVAILABLE or not os.path.exists(image_path):
        return "KHONG XAC DINH"
    try:
        img = cv2.imread(image_path)
        if img is None:
            return "KHONG XAC DINH"
            
        # Luồng xử lý nguyên bản: kmeans -> adaptive_resize_pad
        cleaned_img_np = kmeans_binarize(img)
        if cleaned_img_np is not None:
            cleaned_img_np = adaptive_resize_pad(cleaned_img_np)
            cleaned_img_pil = Image.fromarray(cleaned_img_np).convert('RGB')
            result = detector.predict(cleaned_img_pil)
            return result
        return "KHONG XAC DINH"
    except Exception as e:
        print(f"[ERROR] Lỗi khi nhận diện tên: {e}")
        return "KHONG XAC DINH"

# ------------------ MOCK DATABASE VÀ MOCK ĐÁP ÁN ---------------
MOCK_ANSWER_KEYS = {
    "012": ["A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D",
            "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C"],
}

STUDENT_DB = {
    "12333333": "Nguyễn Vũ Dũng",
    "654321": "TRAN THI B",
    "100200": "LE HOANG C"
}

def load_answer_key(ma_de):
    return MOCK_ANSWER_KEYS.get(ma_de)

# ------------------ LOGIC ĐỐI CHIẾU CHÉO (CROSS-VERIFICATION) ---------------
def compare_names(ocr_name, db_name):
    # CHuẩn hóa chuỗi (chuyển về in hoa, bỏ khoảng trắng thừa)
    s1 = " ".join(ocr_name.upper().split())
    s2 = " ".join(db_name.upper().split())
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def verify_student_info(extracted_mssv, extracted_name):
    if extracted_mssv not in STUDENT_DB:
        return False, extracted_mssv, "MSSV không tồn tại trong Database."

    true_name = STUDENT_DB[extracted_mssv]
    similarity = compare_names(extracted_name, true_name)

    print(f"  [Verify] Tra cứu cơ sở dữ liệu: MSSV {extracted_mssv} mapped với '{true_name}'")
    print(f"  [Verify] Tên nhận diện từ ảnh phiểu: '{extracted_name}' (Độ khớp: {similarity:.1%})")

    if similarity >= 0.85:
        return True, extracted_mssv, "Khớp tuyệt đối.", true_name
    elif similarity >= 0.60:
        return True, extracted_mssv, "Khớp tương đối (Lỗi nhẹ do OCR). Đã tự ghép nối thành công.", true_name
    else:
        return False, extracted_mssv, f"KHÔNG KHỚP TÊN! Vui lòng nhờ GV kiểm tra tay. Tên OCR='{extracted_name}', Tên DB='{true_name}'", true_name

# ------------------ PIPELINE CHẤM ĐIỂM CHÍNH ---------------
def run_grading_pipeline(crops_dir="d:/OCR/crops"):
    print("="*50)
    print("BẮT ĐẦU QUÁ TRÌNH CHẤM ĐIỂM VÀ ĐỐI CHIẾU")
    print("="*50)

    # 1. Trích xuất thông tin định danh
    ma_de_path = os.path.join(crops_dir, "ma_de.png")
    mssv_path = os.path.join(crops_dir, "mssv.png")
    ho_ten_path = os.path.join(crops_dir, "ho_va_ten_refined.png") # Dùng ảnh đã crop mịn nếu có

    ma_de = extract_id_and_code(ma_de_path, 3)
    mssv = extract_id_and_code(mssv_path, 8)
    
    print("\n[1] TRÍCH XUẤT THÔNG TIN THÍ SINH:")
    print(f"  -> MSSV (OMR): {mssv}")
    print(f"  -> Mã đề (OMR): {ma_de}")
    
    # Nhận diện tên bằng VietOCR
    print(f"\n[2] ĐỐI CHIẾU THÔNG TIN (CROSS-VERIFICATION):")
    ocr_name = ocr_read_name(ho_ten_path)
    
    # 2. Thực hiện đối chiếu chéo (MSSV & OCR Name)
    is_valid_student, final_mssv, verify_note, true_name = verify_student_info(mssv, ocr_name)

    if not is_valid_student:
        print(f"\n[ALARM - CẦN GIẢNG VIÊN REVIEW]")
        print(f"Lý do: {verify_note}")
        print("Trạng thái: Vẫn tiếp tục chấm điểm tạm thời nhưng không tự động ghi nhận vào CSDL.")
        print("-"*50)
    
    # 3. Lấy đáp án mẫu cho mã đề
    correct_answers = load_answer_key(ma_de)
    if not correct_answers:
        print(f"\n[ERROR] Không tìm thấy đáp án mẫu cho mã đề '{ma_de}'.")
        print("        Hệ thống sẽ dừng việc tính điểm!")
        return

    # 4. Trích xuất đáp án từ các vùng trả lời
    answer_files = ["answer_1.png", "answer_2.png", "answer_3.png"]
    student_answers = []

    print("\n[3] TRÍCH XUẤT VÀ CHẤM KẾT QUẢ BÀI LÀM...")
    start_idx = 1
    for f in answer_files:
        path = os.path.join(crops_dir, f)
        if os.path.exists(path):
            ans = process_omr(path, start_question_idx=start_idx)
            if ans:
                student_answers.extend(ans)
                start_idx += len(ans)

    # 5. Duyệt và tính điểm
    total_questions = len(correct_answers)
    num_correct_score = 0.0
    detailed_results = []

    for i in range(total_questions):
        st_ans = student_answers[i] if i < len(student_answers) else ""
        cr_ans = correct_answers[i]

        st_set = set(st_ans)
        cr_set = set(cr_ans)
        
        q_score = 0.0
        ket_qua = "SAI"
        
        if len(st_set) == 0:
            q_score = 0.0
            ket_qua = "CHƯA TÔ"
        elif not st_set.issubset(cr_set):
            # Chọn thừa (tô nhầm) hoặc sai hoàn toàn -> mất điểm
            q_score = 0.0
            ket_qua = "SAI (Tô sai/thừa)"
        elif st_set == cr_set:
            # Chọn đủ tất cả đáp án đúng -> full điểm câu đó
            q_score = 1.0
            ket_qua = "ĐÚNG"
        else:
            # Chọn đúng 1 vài đáp án nhưng thiếu -> điểm thành phần
            q_score = len(st_set) / len(cr_set)
            ket_qua = f"ĐÚNG 1 PHẦN ({q_score*100:.0f}%)"

        num_correct_score += q_score

        detailed_results.append({
            "cauHoi": i + 1,
            "dapAnHocSinh": st_ans if st_ans else "(Chưa tô)",
            "dapAnDung": cr_ans,
            "ketQua": ket_qua
        })

    # Tính điểm hệ 10
    score = (num_correct_score / total_questions) * 10.0

    print("="*50)
    print(f"BÁO CÁO KẾT QUẢ (SCORE REPORT):")
    print(f" - MSSV:         {mssv}")
    if OCR_AVAILABLE:
        print(f" - Tên thí sinh: {true_name}")
    print(f" - Status:       {'HỢP LỆ' if is_valid_student else 'CẦN REVIEW LẠI MÃ SỐ'}")
    print(f" - Mã đề:        {ma_de}")
    print(f" - Số câu đúng:  {num_correct_score:.2f} / {total_questions}")
    print(f" - ĐIỂM SỐ:      {score:.2f} / 10.0")
    print("="*50)

if __name__ == "__main__":
    run_grading_pipeline()
