from __future__ import annotations

import csv
import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "backend.db"
ALL_RECORDS_CSV = PROJECT_ROOT / "results" / "demo_seed_inventory" / "all_records.csv"
DUPLICATE_SUMMARY_CSV = PROJECT_ROOT / "results" / "demo_seed_inventory" / "duplicate_summary.csv"

QUESTION_COUNT = 45
TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S.%f"
@dataclass
class StudentSeed:
    mssv: str
    full_name: str
    exam_code: str


def utc_now_text(offset_minutes: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(minutes=offset_minutes)).strftime(TIMESTAMP_FMT)


def split_pipe(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split("|")]


def first_non_empty(values: list[str]) -> str:
    for value in values:
        if value.strip():
            return value.strip()
    return ""


def normalize_answer(value: str) -> str:
    seen: list[str] = []
    for char in (value or "").upper():
        if char in {"A", "B", "C", "D"} and char not in seen:
            seen.append(char)
    return "".join(seen)


def choose_wrong_answer(student_answer: str) -> str:
    normalized = normalize_answer(student_answer)
    for option in "ABCD":
        if option not in normalized:
            return option
    return "A"


def build_answer_key(code: str, representative_answers: list[str], target_correct: int) -> list[str]:
    normalized_answers = [normalize_answer(answer) for answer in representative_answers[:QUESTION_COUNT]]
    while len(normalized_answers) < QUESTION_COUNT:
        normalized_answers.append("")

    available_indexes = [index for index, answer in enumerate(normalized_answers) if answer]
    target = min(target_correct, len(available_indexes))
    rng = random.Random(f"demo-seed-{code}")
    chosen_indexes = set(rng.sample(available_indexes, target)) if target > 0 else set()

    answer_key: list[str] = []
    for index, answer in enumerate(normalized_answers):
        if index in chosen_indexes and answer:
            answer_key.append(answer)
        else:
            answer_key.append(choose_wrong_answer(answer))
    return answer_key


def build_target_correct_counts(code_count: int) -> list[int]:
    if code_count <= 0:
        return []
    if code_count == 1:
        return [24]
    min_target = 16
    max_target = 34
    return [
        round(min_target + ((max_target - min_target) * index / (code_count - 1)))
        for index in range(code_count)
    ]


def grade_answers(student_answers: list[str], answer_key: list[str]) -> tuple[float, float, list[dict[str, object]]]:
    total = len(answer_key)
    correct_count = 0.0
    details: list[dict[str, object]] = []

    normalized_student_answers = [normalize_answer(answer) for answer in student_answers[:total]]
    while len(normalized_student_answers) < total:
        normalized_student_answers.append("")

    for index, correct_answer in enumerate(answer_key):
        student_answer = normalized_student_answers[index]
        student_set = set(student_answer)
        correct_set = set(normalize_answer(correct_answer))

        result = "WRONG"
        is_correct = False
        score = 0.0

        if not student_set:
            result = "BLANK"
        elif not all(item in correct_set for item in student_set):
            result = "WRONG"
        elif len(student_set) == len(correct_set) and all(item in correct_set for item in student_set):
            result = "CORRECT"
            is_correct = True
            score = 1.0
            correct_count += 1.0
        elif len(correct_set) > 0:
            score = len(student_set) / len(correct_set)
            result = "PARTIAL"
            is_correct = True
            correct_count += score

        details.append(
            {
                "question": index + 1,
                "student_ans": student_answer or "Blank",
                "correct_ans": normalize_answer(correct_answer),
                "result": result,
                "is_correct": is_correct,
            }
        )

    score = round((correct_count / total) * 10, 2) if total else 0.0
    return score, round(correct_count, 2), details


def load_student_truth() -> list[StudentSeed]:
    students: list[StudentSeed] = []
    with DUPLICATE_SUMMARY_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            mssv = (row.get("mssv") or "").strip()
            if not mssv:
                continue
            full_name = first_non_empty(split_pipe(row.get("ocr_names") or ""))
            exam_code = first_non_empty(split_pipe(row.get("ma_de_values") or ""))
            students.append(StudentSeed(mssv=mssv, full_name=full_name or f"Student {mssv}", exam_code=exam_code))
    students.sort(key=lambda item: item.mssv)
    return students


def load_records() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with ALL_RECORDS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("status") or "").strip().lower() != "success":
                continue
            if not (row.get("mssv") or "").strip():
                continue
            rows.append(row)
    return rows


def reset_tables(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    has_sqlite_sequence = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
    ).fetchone() is not None
    for table in ("submissions", "exam_codes", "exams", "students", "classes"):
        conn.execute(f"DELETE FROM {table}")
        if has_sqlite_sequence:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def insert_class(conn: sqlite3.Connection, code: str, name: str, semester: str, ts: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO classes (code, name, semester, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (code, name, semester, ts, ts),
    )
    return int(cursor.lastrowid)


def insert_student(conn: sqlite3.Connection, class_id: int, mssv: str, full_name: str, ts: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO students (class_id, mssv, full_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (class_id, mssv, full_name, ts, ts),
    )
    return int(cursor.lastrowid)


def insert_exam(conn: sqlite3.Connection, class_id: int, title: str, question_count: int, ts: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO exams (class_id, title, question_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (class_id, title, question_count, ts, ts),
    )
    return int(cursor.lastrowid)


def insert_exam_code(conn: sqlite3.Connection, exam_id: int, code: str, answer_key: list[str], ts: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO exam_codes (exam_id, code, answer_key, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (exam_id, code, json.dumps(answer_key, ensure_ascii=False), ts, ts),
    )
    return int(cursor.lastrowid)


def insert_submission(
    conn: sqlite3.Connection,
    *,
    class_id: int,
    exam_id: int,
    exam_code_id: int,
    student_id: int,
    detected_mssv: str,
    detected_name: str,
    detected_exam_code: str,
    answers: list[str],
    score: float,
    correct_count: float,
    grading_details: list[dict[str, object]],
    student_info: dict[str, object],
    crops: dict[str, str | None],
    omr_images: dict[str, str | None],
    ts: str,
    source_image_url: str | None,
    aligned_image_url: str | None,
    result_image_url: str | None,
) -> None:
    grading_payload = {
        "score": score,
        "correct_count": correct_count,
        "total": QUESTION_COUNT,
        "details": grading_details,
    }
    conn.execute(
        """
        INSERT INTO submissions (
            class_id, exam_id, exam_code_id, student_id,
            detected_mssv, detected_name, detected_exam_code,
            answers, score, correct_count, total_questions, status,
            manual_override, source_image_url, aligned_image_url, result_image_url,
            student_info, grading, crops, omr_images, preprocess_images,
            scanned_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            class_id,
            exam_id,
            exam_code_id,
            student_id,
            detected_mssv,
            detected_name,
            detected_exam_code,
            json.dumps(answers, ensure_ascii=False),
            score,
            correct_count,
            QUESTION_COUNT,
            "matched",
            0,
            source_image_url,
            aligned_image_url,
            result_image_url,
            json.dumps(student_info, ensure_ascii=False),
            json.dumps(grading_payload, ensure_ascii=False),
            json.dumps(crops, ensure_ascii=False),
            json.dumps(omr_images, ensure_ascii=False),
            json.dumps({}, ensure_ascii=False),
            ts,
            ts,
            ts,
        ),
    )


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    if not ALL_RECORDS_CSV.exists():
        raise FileNotFoundError(f"Missing inventory file: {ALL_RECORDS_CSV}")
    if not DUPLICATE_SUMMARY_CSV.exists():
        raise FileNotFoundError(f"Missing truth-label file: {DUPLICATE_SUMMARY_CSV}")

    students = load_student_truth()
    records = load_records()
    if not students:
        raise RuntimeError("No students found in duplicate_summary.csv")
    if not records:
        raise RuntimeError("No successful records found in all_records.csv")

    student_truth_by_mssv = {student.mssv: student for student in students}

    class_a_students: list[StudentSeed] = []
    class_b_students: list[StudentSeed] = []
    grouped_by_code: dict[str, list[StudentSeed]] = {}
    for student in students:
        grouped_by_code.setdefault(student.exam_code or "UNKNOWN", []).append(student)
    for code_students in grouped_by_code.values():
        for index, student in enumerate(code_students):
            (class_a_students if index % 2 == 0 else class_b_students).append(student)

    class_groups = [
        ("CLASS-1", "Demo class A", sorted(class_a_students, key=lambda item: item.mssv)),
        ("CLASS-2", "Demo class B", sorted(class_b_students, key=lambda item: item.mssv)),
    ]
    class_groups = [item for item in class_groups if item[2]]

    code_to_representative_answers: dict[str, list[str]] = {}
    for row in records:
        mssv = (row.get("mssv") or "").strip()
        truth = student_truth_by_mssv.get(mssv)
        code = (truth.exam_code if truth and truth.exam_code else (row.get("ma_de") or "").strip())
        if not code or code in code_to_representative_answers:
            continue
        code_to_representative_answers[code] = split_pipe(row.get("answers") or "")

    sorted_codes = sorted(code_to_representative_answers)
    target_counts = build_target_correct_counts(len(sorted_codes))
    code_targets = {code: target_counts[index] for index, code in enumerate(sorted_codes)}
    answer_keys_by_code = {
        code: build_answer_key(code, answers, code_targets[code])
        for code, answers in code_to_representative_answers.items()
    }

    conn = sqlite3.connect(DB_PATH)
    try:
        reset_tables(conn)
        timestamp_base = datetime.now(UTC)

        student_id_by_mssv: dict[str, int] = {}
        class_id_by_mssv: dict[str, int] = {}
        exam_id_by_mssv: dict[str, int] = {}
        exam_code_id_by_code: dict[tuple[int, str], int] = {}

        for class_index, (class_code, class_name, class_students) in enumerate(class_groups):
            ts = (timestamp_base + timedelta(minutes=class_index)).strftime(TIMESTAMP_FMT)
            class_id = insert_class(conn, class_code, class_name, "HK2 2025-2026", ts)
            exam_id = insert_exam(conn, class_id, "Exam 1", QUESTION_COUNT, ts)

            class_codes = sorted({student.exam_code for student in class_students if student.exam_code})
            for code in class_codes:
                answer_key = answer_keys_by_code.get(code) or ["A"] * QUESTION_COUNT
                exam_code_id = insert_exam_code(conn, exam_id, code, answer_key, ts)
                exam_code_id_by_code[(exam_id, code)] = exam_code_id

            for student in class_students:
                student_id = insert_student(conn, class_id, student.mssv, student.full_name, ts)
                student_id_by_mssv[student.mssv] = student_id
                class_id_by_mssv[student.mssv] = class_id
                exam_id_by_mssv[student.mssv] = exam_id

        submission_count = 0
        for row_index, row in enumerate(records):
            mssv = (row.get("mssv") or "").strip()
            if mssv not in student_id_by_mssv or mssv not in class_id_by_mssv or mssv not in exam_id_by_mssv:
                continue

            truth = student_truth_by_mssv[mssv]
            code = truth.exam_code or (row.get("ma_de") or "").strip()
            class_id = class_id_by_mssv[mssv]
            exam_id = exam_id_by_mssv[mssv]
            exam_code_id = exam_code_id_by_code.get((exam_id, code))
            if exam_code_id is None:
                continue

            answers = split_pipe(row.get("answers") or "")[:QUESTION_COUNT]
            while len(answers) < QUESTION_COUNT:
                answers.append("")

            answer_key = answer_keys_by_code.get(code) or ["A"] * QUESTION_COUNT
            score, correct_count, details = grade_answers(answers, answer_key)

            raw_ocr_name = (row.get("ocr_name") or "").strip()
            resolved_name = truth.full_name or raw_ocr_name or f"Student {mssv}"
            name_source = "ocr" if raw_ocr_name and raw_ocr_name == resolved_name else "database"
            similarity = 1.0 if name_source == "ocr" else 0.92

            student_info = {
                "mssv": mssv,
                "ma_de": code,
                "name": resolved_name,
                "ocr_name": raw_ocr_name,
                "matched_name": resolved_name,
                "name_source": name_source,
                "name_similarity": similarity,
            }
            crops = {
                "ho_va_ten": row.get("name_crop_url") or None,
                "lop": None,
                "mssv": row.get("mssv_crop_url") or None,
                "ma_de": row.get("made_crop_url") or None,
            }
            omr_images = {
                "answer_1": row.get("omr_answer_1_url") or None,
                "answer_2": row.get("omr_answer_2_url") or None,
                "answer_3": row.get("omr_answer_3_url") or None,
                "student_id": row.get("mssv_crop_url") or None,
                "exam_code": row.get("made_crop_url") or None,
            }
            ts = (timestamp_base + timedelta(minutes=10 + row_index)).strftime(TIMESTAMP_FMT)

            insert_submission(
                conn,
                class_id=class_id,
                exam_id=exam_id,
                exam_code_id=exam_code_id,
                student_id=student_id_by_mssv[mssv],
                detected_mssv=mssv,
                detected_name=resolved_name,
                detected_exam_code=code,
                answers=answers,
                score=score,
                correct_count=correct_count,
                grading_details=details,
                student_info=student_info,
                crops=crops,
                omr_images=omr_images,
                ts=ts,
                source_image_url=row.get("source_image_url") or None,
                aligned_image_url=row.get("aligned_image_url") or None,
                result_image_url=row.get("result_image_url") or None,
            )
            submission_count += 1

        conn.commit()

        class_count = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        student_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        exam_count = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
        exam_code_count = conn.execute("SELECT COUNT(*) FROM exam_codes").fetchone()[0]
        saved_submission_count = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]

        print(f"[DONE] Reset and seeded {DB_PATH}")
        print(f"[INFO] classes={class_count}, students={student_count}, exams={exam_count}, exam_codes={exam_code_count}, submissions={saved_submission_count}")
        print(f"[INFO] processed_success_rows={submission_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
