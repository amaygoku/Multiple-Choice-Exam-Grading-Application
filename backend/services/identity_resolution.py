from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import Student, Submission
from backend.services.student_matching import name_similarity


def build_identity_resolution(
    db: Session,
    class_id: int | None,
    exam_id: int | None,
    detected_mssv: str,
    ocr_name: str,
) -> dict:
    if class_id is None:
        return {
            "detected_mssv": detected_mssv,
            "ocr_name": ocr_name,
            "needs_user_selection": False,
            "reason": "",
            "candidates": [],
        }

    students = (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.full_name.asc(), Student.id.asc())
        .all()
    )
    candidates_by_id: dict[int, dict] = {}
    exact_mssv_student = None

    def ensure_candidate(student: Student) -> dict:
        candidate = candidates_by_id.get(student.id)
        if candidate is None:
            candidate = {
                "student_id": student.id,
                "full_name": student.full_name,
                "mssv": student.mssv,
                "reasons": [],
                "name_similarity": 0.0,
                "has_existing_submission": False,
                "existing_submission_id": None,
            }
            candidates_by_id[student.id] = candidate
        return candidate

    if detected_mssv:
        for student in students:
            if student.mssv != detected_mssv:
                continue
            candidate = ensure_candidate(student)
            if "mssv_match" not in candidate["reasons"]:
                candidate["reasons"].append("mssv_match")
            exact_mssv_student = student

    if ocr_name:
        similar_students: list[tuple[float, Student]] = []
        for student in students:
            score = name_similarity(student.full_name, ocr_name)
            if score < 0.55:
                continue
            similar_students.append((score, student))
        similar_students.sort(key=lambda item: item[0], reverse=True)
        for score, student in similar_students[:5]:
            candidate = ensure_candidate(student)
            candidate["name_similarity"] = max(candidate["name_similarity"], round(score, 4))
            if "name_similarity" not in candidate["reasons"]:
                candidate["reasons"].append("name_similarity")

    if exam_id is not None and candidates_by_id:
        for candidate in candidates_by_id.values():
            existing = (
                db.query(Submission)
                .filter(
                    Submission.class_id == class_id,
                    Submission.exam_id == exam_id,
                    Submission.student_id == candidate["student_id"],
                )
                .order_by(Submission.updated_at.desc(), Submission.id.desc())
                .first()
            )
            if existing is not None:
                candidate["has_existing_submission"] = True
                candidate["existing_submission_id"] = existing.id
                if "existing_submission" not in candidate["reasons"]:
                    candidate["reasons"].append("existing_submission")

    candidates = sorted(
        candidates_by_id.values(),
        key=lambda item: (
            0 if "mssv_match" in item["reasons"] else 1,
            0 if item["has_existing_submission"] else 1,
            -item["name_similarity"],
            item["full_name"].lower(),
        ),
    )

    has_duplicate = any(item["has_existing_submission"] for item in candidates)
    needs_user_selection = False
    reason = ""
    if has_duplicate and candidates:
        needs_user_selection = True
        reason = "duplicate_submission"
    elif detected_mssv and exact_mssv_student is None and candidates:
        needs_user_selection = True
        reason = "mssv_not_found"

    return {
        "detected_mssv": detected_mssv,
        "ocr_name": ocr_name,
        "needs_user_selection": needs_user_selection,
        "reason": reason,
        "candidates": candidates,
    }
