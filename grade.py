import difflib
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from extract_code import extract_id_and_code
from ocr import OCR_AVAILABLE, ocr_read_name
from omr_pipeline import process_omr


MOCK_ANSWER_KEYS = {
    "012": [
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
        "D",
        "A",
        "B",
        "C",
    ],
}

STUDENT_DB = {
    "12333333": "Nguyễn Vũ Dũng",
    "654321": "TRAN THI B",
    "100200": "LE HOANG C",
}


def load_answer_key(ma_de):
    return MOCK_ANSWER_KEYS.get(ma_de)


def compare_names(ocr_name, db_name):
    s1 = " ".join(ocr_name.upper().split())
    s2 = " ".join(db_name.upper().split())
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def verify_student_info(extracted_mssv, extracted_name):
    if extracted_mssv not in STUDENT_DB:
        return False, extracted_mssv, "MSSV không tồn tại trong Database.", ""

    true_name = STUDENT_DB[extracted_mssv]
    similarity = compare_names(extracted_name, true_name)

    print(f"  [Verify] Tra cứu cơ sở dữ liệu: MSSV {extracted_mssv} mapped với '{true_name}'")
    print(
        f"  [Verify] Tên nhận diện từ ảnh phiếu: '{extracted_name}' "
        f"(Độ khớp: {similarity:.1%})"
    )

    if similarity >= 0.85:
        return True, extracted_mssv, "Khớp tuyệt đối.", true_name
    if similarity >= 0.60:
        return True, extracted_mssv, "Khớp tương đối (lỗi nhẹ do OCR).", true_name
    return (
        False,
        extracted_mssv,
        f"KHÔNG KHỚP TÊN! Tên OCR='{extracted_name}', Tên DB='{true_name}'",
        true_name,
    )


def run_grading_pipeline(crops_dir="d:/OCR/crops"):
    print("=" * 50)
    print("BẮT ĐẦU QUÁ TRÌNH CHẤM ĐIỂM VÀ ĐỐI CHIẾU")
    print("=" * 50)

    ma_de_path = os.path.join(crops_dir, "ma_de.png")
    mssv_path = os.path.join(crops_dir, "mssv.png")
    ho_ten_path = os.path.join(crops_dir, "ho_va_ten_refined.png")

    ma_de = extract_id_and_code(ma_de_path, 3)
    mssv = extract_id_and_code(mssv_path, 8)

    print("\n[1] TRÍCH XUẤT THÔNG TIN THÍ SINH:")
    print(f"  -> MSSV (OMR): {mssv}")
    print(f"  -> Mã đề (OMR): {ma_de}")

    print("\n[2] ĐỐI CHIẾU THÔNG TIN (CROSS-VERIFICATION):")
    ocr_name = ocr_read_name(ho_ten_path)

    is_valid_student, final_mssv, verify_note, true_name = verify_student_info(mssv, ocr_name)

    if not is_valid_student:
        print("\n[ALARM - CẦN GIẢNG VIÊN REVIEW]")
        print(f"Lý do: {verify_note}")
        print("Trạng thái: Vẫn tiếp tục chấm điểm tạm thời nhưng không tự động ghi nhận vào CSDL.")
        print("-" * 50)

    correct_answers = load_answer_key(ma_de)
    if not correct_answers:
        print(f"\n[ERROR] Không tìm thấy đáp án mẫu cho mã đề '{ma_de}'.")
        print("        Hệ thống sẽ dừng việc tính điểm!")
        return

    answer_files = ["answer_1.png", "answer_2.png", "answer_3.png"]
    student_answers = []

    print("\n[3] TRÍCH XUẤT VÀ CHẤM KẾT QUẢ BÀI LÀM...")
    start_idx = 1
    for file_name in answer_files:
        path = os.path.join(crops_dir, file_name)
        if os.path.exists(path):
            ans = process_omr(path, start_question_idx=start_idx)
            if ans:
                student_answers.extend(ans)
                start_idx += len(ans)

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
            ket_qua = "CHƯA TÔ"
        elif not st_set.issubset(cr_set):
            ket_qua = "SAI (TÔ sai/thừa)"
        elif st_set == cr_set:
            q_score = 1.0
            ket_qua = "ĐÚNG"
        else:
            q_score = len(st_set) / len(cr_set)
            ket_qua = f"ĐÚNG 1 PHẦN ({q_score * 100:.0f}%)"

        num_correct_score += q_score
        detailed_results.append(
            {
                "cauHoi": i + 1,
                "dapAnHocSinh": st_ans if st_ans else "(Chưa tô)",
                "dapAnDung": cr_ans,
                "ketQua": ket_qua,
            }
        )

    score = (num_correct_score / total_questions) * 10.0

    print("=" * 50)
    print("BÁO CÁO KẾT QUẢ (SCORE REPORT):")
    print(f" - MSSV:         {final_mssv}")
    if OCR_AVAILABLE:
        print(f" - Tên thí sinh: {true_name}")
    print(f" - Status:       {'HỢP LỆ' if is_valid_student else 'CẦN REVIEW LẠI MÃ SỐ'}")
    print(f" - Mã đề:        {ma_de}")
    print(f" - Số câu đúng:  {num_correct_score:.2f} / {total_questions}")
    print(f" - ĐIỂM SỐ:      {score:.2f} / 10.0")
    print("=" * 50)


if __name__ == "__main__":
    run_grading_pipeline()
