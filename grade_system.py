def _normalize_answer(value):
    return "".join(ch for ch in value.upper().replace(" ", "") if ch in {"A", "B", "C", "D"})


def grade_paper(student_answers, correct_answers_str):
    """
    Chấm bài trên chuỗi đáp án giáo viên.
    correct_answers_str: "A, B, C, D, A..."
    """
    if not correct_answers_str:
        return {"score": 0, "correct_count": 0, "total": 0, "details": []}

    correct_answers = [_normalize_answer(ans) for ans in correct_answers_str.split(",")]
    correct_answers = [ans for ans in correct_answers if ans]

    total_questions = len(correct_answers)
    if total_questions == 0:
        return {"score": 0, "correct_count": 0, "total": 0, "details": []}

    num_correct_score = 0.0
    detailed_results = []

    for i in range(total_questions):
        st_ans = _normalize_answer(student_answers[i] if i < len(student_answers) else "")
        cr_ans = correct_answers[i]

        st_set = set(st_ans)
        cr_set = set(cr_ans)

        q_score = 0.0
        ket_qua = "SAI"

        if len(st_set) == 0:
            ket_qua = "CHƯA TÔ"
        elif not st_set.issubset(cr_set):
            ket_qua = "SAI"
        elif st_set == cr_set:
            q_score = 1.0
            ket_qua = "ĐÚNG"
        else:
            q_score = len(st_set) / len(cr_set)
            ket_qua = "MỘT PHẦN"

        num_correct_score += q_score

        detailed_results.append(
            {
                "question": i + 1,
                "student_ans": st_ans if st_ans else "Trống",
                "correct_ans": cr_ans,
                "result": ket_qua,
                "is_correct": q_score > 0,
            }
        )

    score = (num_correct_score / total_questions) * 10.0

    return {
        "score": round(score, 2),
        "correct_count": round(num_correct_score, 2),
        "total": total_questions,
        "details": detailed_results,
    }
