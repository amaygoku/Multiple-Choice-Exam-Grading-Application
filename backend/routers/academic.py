from statistics import median as calc_median

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.database import get_db
from backend.models import ClassRoom, Exam, ExamCode, Student, Submission
from backend.schemas import (
    ClassCreate,
    ClassResponse,
    ClassUpdate,
    ExamCodeCreate,
    ExamCodeResponse,
    ExamCodeUpdate,
    ExamCreate,
    ExamResponse,
    ExamUpdate,
    StudentCreate,
    StudentResponse,
    StudentUpdate,
    IdentityResolution,
    IdentityResolutionRequest,
    SubmissionCreate,
    SubmissionResponse,
    SubmissionUpdate,
    AnalyticsComparisonItem,
    AnalyticsDistributionItem,
    AnalyticsGradeBandItem,
    AnalyticsQuestionInsight,
    AnalyticsResponse,
    AnalyticsSummary,
)
from backend.services.identity_resolution import build_identity_resolution


academic_router = APIRouter(prefix="/api/v1", tags=["Academic CRUD"])


def _get_or_404(db: Session, model, item_id: int, label: str):
    obj = db.get(model, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return obj


def _commit_or_409(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(getattr(exc, "orig", exc)).lower()
        if "uq_students_class_mssv" in message or ("students" in message and "mssv" in message):
            detail = "Duplicate student ID in the same class"
        elif "uq_exam_codes_exam_code" in message or ("exam_codes" in message and "code" in message):
            detail = "Duplicate exam code in the same exam"
        else:
            detail = "Constraint conflict"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def _find_existing_submission(db: Session, payload: SubmissionCreate) -> Submission | None:
    query = db.query(Submission).filter(
        Submission.class_id == payload.class_id,
        Submission.exam_id == payload.exam_id,
    )
    if payload.student_id is not None:
        return (
            query
            .filter(Submission.student_id == payload.student_id)
            .order_by(Submission.updated_at.desc(), Submission.id.desc())
            .first()
        )
    return None


def _resolve_submission_student_id(db: Session, class_id: int | None, detected_mssv: str | None) -> int | None:
    detected_mssv = (detected_mssv or "").strip()
    if class_id is None or not detected_mssv:
        return None
    student = (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.mssv == detected_mssv)
        .order_by(Student.id.desc())
        .first()
    )
    return student.id if student else None


def _normalize_submission_payload(db: Session, payload: SubmissionCreate | SubmissionUpdate, fallback: Submission | None = None) -> dict:
    data = payload.model_dump(exclude_unset=isinstance(payload, SubmissionUpdate))
    if "student_id" in payload.model_fields_set:
        return data
    class_id = data.get("class_id", fallback.class_id if fallback is not None else None)
    detected_mssv = data.get("detected_mssv", fallback.detected_mssv if fallback is not None else "")
    data["student_id"] = _resolve_submission_student_id(db, class_id, detected_mssv)
    return data


@academic_router.get("/classes", response_model=list[ClassResponse])
def list_classes(db: Session = Depends(get_db)):
    return db.query(ClassRoom).order_by(ClassRoom.id.desc()).all()


@academic_router.post("/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    item = ClassRoom(**payload.model_dump())
    db.add(item)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.get("/classes/{class_id}", response_model=ClassResponse)
def get_class(class_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, ClassRoom, class_id, "Class")


@academic_router.patch("/classes/{class_id}", response_model=ClassResponse)
def update_class(class_id: int, payload: ClassUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, ClassRoom, class_id, "Class")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, ClassRoom, class_id, "Class")
    db.delete(item)
    db.commit()


@academic_router.get("/students", response_model=list[StudentResponse])
def list_students(class_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Student)
    if class_id is not None:
        query = query.filter(Student.class_id == class_id)
    return query.order_by(Student.id.desc()).all()


@academic_router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    _get_or_404(db, ClassRoom, payload.class_id, "Class")
    item = Student(**payload.model_dump())
    db.add(item)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.get("/students/{student_id}", response_model=StudentResponse)
def get_student(student_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Student, student_id, "Student")


@academic_router.patch("/students/{student_id}", response_model=StudentResponse)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, Student, student_id, "Student")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, Student, student_id, "Student")
    db.delete(item)
    db.commit()


@academic_router.get("/exams", response_model=list[ExamResponse])
def list_exams(class_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Exam)
    if class_id is not None:
        query = query.filter(Exam.class_id == class_id)
    return query.order_by(Exam.id.desc()).all()


@academic_router.post("/exams", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(payload: ExamCreate, db: Session = Depends(get_db)):
    _get_or_404(db, ClassRoom, payload.class_id, "Class")
    item = Exam(**payload.model_dump())
    db.add(item)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.get("/exams/{exam_id}", response_model=ExamResponse)
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Exam, exam_id, "Exam")


@academic_router.patch("/exams/{exam_id}", response_model=ExamResponse)
def update_exam(exam_id: int, payload: ExamUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, Exam, exam_id, "Exam")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, Exam, exam_id, "Exam")
    db.delete(item)
    db.commit()


@academic_router.get("/exam-codes", response_model=list[ExamCodeResponse])
def list_exam_codes(exam_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(ExamCode)
    if exam_id is not None:
        query = query.filter(ExamCode.exam_id == exam_id)
    return query.order_by(ExamCode.id.desc()).all()


@academic_router.post("/exam-codes", response_model=ExamCodeResponse, status_code=status.HTTP_201_CREATED)
def create_exam_code(payload: ExamCodeCreate, db: Session = Depends(get_db)):
    _get_or_404(db, Exam, payload.exam_id, "Exam")
    item = ExamCode(**payload.model_dump())
    db.add(item)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.get("/exam-codes/{exam_code_id}", response_model=ExamCodeResponse)
def get_exam_code(exam_code_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, ExamCode, exam_code_id, "Exam code")


@academic_router.patch("/exam-codes/{exam_code_id}", response_model=ExamCodeResponse)
def update_exam_code(exam_code_id: int, payload: ExamCodeUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, ExamCode, exam_code_id, "Exam code")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.delete("/exam-codes/{exam_code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam_code(exam_code_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, ExamCode, exam_code_id, "Exam code")
    db.delete(item)
    db.commit()


@academic_router.get("/submissions", response_model=list[SubmissionResponse])
def list_submissions(exam_id: int | None = None, class_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Submission)
    if exam_id is not None:
        query = query.filter(Submission.exam_id == exam_id)
    if class_id is not None:
        query = query.filter(Submission.class_id == class_id)
    return query.order_by(Submission.updated_at.desc(), Submission.id.desc()).all()


@academic_router.post("/submissions/resolve-identity", response_model=IdentityResolution)
def resolve_submission_identity(payload: IdentityResolutionRequest, db: Session = Depends(get_db)):
    _get_or_404(db, ClassRoom, payload.class_id, "Class")
    _get_or_404(db, Exam, payload.exam_id, "Exam")
    return build_identity_resolution(
        db,
        payload.class_id,
        payload.exam_id,
        (payload.detected_mssv or "").strip(),
        (payload.detected_name or "").strip(),
    )


@academic_router.post("/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    _get_or_404(db, ClassRoom, payload.class_id, "Class")
    _get_or_404(db, Exam, payload.exam_id, "Exam")
    if payload.exam_code_id is not None:
        _get_or_404(db, ExamCode, payload.exam_code_id, "Exam code")
    data = _normalize_submission_payload(db, payload)
    normalized_payload = SubmissionCreate(**data)
    existing = _find_existing_submission(db, normalized_payload)
    if existing is not None:
        for key, value in data.items():
            setattr(existing, key, value)
        _commit_or_409(db)
        db.refresh(existing)
        return existing

    item = Submission(**data)
    db.add(item)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Submission, submission_id, "Submission")


@academic_router.patch("/submissions/{submission_id}", response_model=SubmissionResponse)
def update_submission(submission_id: int, payload: SubmissionUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, Submission, submission_id, "Submission")
    if payload.class_id is not None:
        _get_or_404(db, ClassRoom, payload.class_id, "Class")
    if payload.exam_id is not None:
        _get_or_404(db, Exam, payload.exam_id, "Exam")
    if payload.exam_code_id is not None:
        _get_or_404(db, ExamCode, payload.exam_code_id, "Exam code")
    data = _normalize_submission_payload(db, payload, fallback=item)

    for key, value in data.items():
        setattr(item, key, value)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(submission_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, Submission, submission_id, "Submission")
    db.delete(item)
    db.commit()


def _normalize_answer_text(value: object) -> str:
    raw = str(value or "").upper()
    letters = [char for char in raw if char in {"A", "B", "C", "D"}]
    normalized: list[str] = []
    for letter in letters:
        if letter not in normalized:
            normalized.append(letter)
    return "".join(normalized)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percent(count: int, total: int) -> float:
    return (count / total) if total > 0 else 0.0


def _build_distribution(scores: list[float]) -> list[AnalyticsDistributionItem]:
    buckets = [0 for _ in range(10)]
    for score in scores:
        bucket = min(9, max(0, int(score)))
        buckets[bucket] += 1
    return [
        AnalyticsDistributionItem(label=f"{index}-{index + 1}", count=count)
        for index, count in enumerate(buckets)
    ]


def _build_grade_bands(total: int, scores: list[float]) -> list[AnalyticsGradeBandItem]:
    bands = [
        ("Gioi (>= 8.0)", sum(1 for score in scores if score >= 8.0)),
        ("Kha (6.5 - 7.9)", sum(1 for score in scores if 6.5 <= score < 8.0)),
        ("Trung binh (5.0 - 6.4)", sum(1 for score in scores if 5.0 <= score < 6.5)),
        ("Yeu / Kem (< 5.0)", sum(1 for score in scores if score < 5.0)),
    ]
    return [
        AnalyticsGradeBandItem(label=label, count=count, percent=_percent(count, total))
        for label, count in bands
    ]


def _submission_effective_code(submission: Submission) -> str:
    if submission.exam_code is not None and submission.exam_code.code:
        return submission.exam_code.code
    return submission.detected_exam_code or ""


def _submission_student_key(submission: Submission) -> str:
    if submission.student_id is not None:
        return f"student:{submission.student_id}"
    if submission.detected_mssv:
        return f"mssv:{submission.detected_mssv.strip()}"
    return f"submission:{submission.id}"


def _dedupe_submissions_by_student(submissions: list[Submission]) -> list[Submission]:
    latest_by_student: dict[str, Submission] = {}
    for submission in submissions:
        key = _submission_student_key(submission)
        if key not in latest_by_student:
            latest_by_student[key] = submission
    return list(latest_by_student.values())


def _build_comparison(
    submissions: list[Submission],
    classes: list[ClassRoom],
    selected_class_id: int | None,
    selected_exam_id: int | None,
) -> list[AnalyticsComparisonItem]:
    if selected_class_id is None:
        grouped: dict[int, list[Submission]] = {}
        for submission in submissions:
            grouped.setdefault(submission.class_id, []).append(submission)
        items: list[AnalyticsComparisonItem] = []
        for class_room in classes:
            group = grouped.get(class_room.id, [])
            if not group:
                continue
            scores = [float(item.score) for item in group]
            items.append(
                AnalyticsComparisonItem(
                    label=class_room.code,
                    sub_label=class_room.name,
                    count=len(group),
                    average_score=_average(scores),
                )
            )
        return sorted(items, key=lambda item: item.average_score, reverse=True)

    if selected_exam_id is None:
        grouped: dict[int, list[Submission]] = {}
        for submission in submissions:
            grouped.setdefault(submission.exam_id, []).append(submission)
        class_room = next((item for item in classes if item.id == selected_class_id), None)
        items: list[AnalyticsComparisonItem] = []
        for exam in class_room.exams if class_room else []:
            group = grouped.get(exam.id, [])
            if not group:
                continue
            scores = [float(item.score) for item in group]
            items.append(
                AnalyticsComparisonItem(
                    label=exam.title,
                    sub_label=f"{len(exam.exam_codes)} code(s)",
                    count=len(group),
                    average_score=_average(scores),
                )
            )
        return sorted(items, key=lambda item: item.average_score, reverse=True)

    grouped_code: dict[str, list[Submission]] = {}
    for submission in submissions:
        effective_code = _submission_effective_code(submission)
        grouped_code.setdefault(effective_code, []).append(submission)

    exam = next(
        (exam_item for class_room in classes for exam_item in class_room.exams if exam_item.id == selected_exam_id),
        None,
    )
    class_room = next(
        (item for item in classes if any(exam_item.id == selected_exam_id for exam_item in item.exams)),
        None,
    )
    items: list[AnalyticsComparisonItem] = []
    for exam_code in exam.exam_codes if exam else []:
        group = grouped_code.get(exam_code.code, [])
        if not group:
            continue
        scores = [float(item.score) for item in group]
        items.append(
            AnalyticsComparisonItem(
                label=exam_code.code,
                sub_label=f"{class_room.code if class_room else 'Unknown class'} - {exam.title if exam else ''}".strip(" -"),
                count=len(group),
                average_score=_average(scores),
            )
        )

    if not items and grouped_code:
        for code, group in grouped_code.items():
            scores = [float(item.score) for item in group]
            items.append(
                AnalyticsComparisonItem(
                    label=code or "UNKNOWN",
                    sub_label=f"{class_room.code if class_room else 'Unknown class'} - {exam.title if exam else ''}".strip(" -"),
                    count=len(group),
                    average_score=_average(scores),
                )
            )
    return sorted(items, key=lambda item: item.average_score, reverse=True)


def _build_question_insights(
    submissions: list[Submission],
    answer_key: list[str],
) -> list[AnalyticsQuestionInsight]:
    if not submissions or not answer_key:
        return []

    question_count = len(answer_key)
    insights: list[AnalyticsQuestionInsight] = []
    for index in range(question_count):
        correct_key = _normalize_answer_text(answer_key[index] if index < len(answer_key) else "")
        correct_set = set(correct_key)
        counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        blank_count = 0
        correct_count = 0

        for submission in submissions:
            answers = submission.answers or []
            answer_value = answers[index] if index < len(answers) else ""
            normalized = _normalize_answer_text(answer_value)
            if not normalized:
                blank_count += 1
                continue

            for letter in normalized:
                if letter in counts:
                    counts[letter] += 1

            if set(normalized) == correct_set:
                correct_count += 1

        total = len(submissions)
        wrong_count = max(0, total - correct_count - blank_count)
        trap_option = "-"
        trap_candidates = sorted(
            ((key, value) for key, value in counts.items() if key not in correct_set),
            key=lambda item: item[1],
            reverse=True,
        )
        if trap_candidates:
            trap_option = trap_candidates[0][0]

        insights.append(
            AnalyticsQuestionInsight(
                question=index + 1,
                difficulty=correct_count / total if total > 0 else 0.0,
                blank_rate=blank_count / total if total > 0 else 0.0,
                correct_count=correct_count,
                wrong_count=wrong_count,
                blank_count=blank_count,
                trap_option=trap_option,
            )
        )

    return sorted(insights, key=lambda item: (-item.wrong_count, item.difficulty))


@academic_router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    class_id: int | None = None,
    exam_id: int | None = None,
    exam_code: str | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(Submission)
        .options(
            joinedload(Submission.classroom),
            joinedload(Submission.exam),
            joinedload(Submission.exam_code),
        )
    )

    if class_id is not None:
        query = query.filter(Submission.class_id == class_id)
    if exam_id is not None:
        query = query.filter(Submission.exam_id == exam_id)
    if exam_code:
        query = query.outerjoin(ExamCode, Submission.exam_code_id == ExamCode.id).filter(
            or_(ExamCode.code == exam_code, Submission.detected_exam_code == exam_code)
        )

    submissions = query.order_by(Submission.updated_at.desc(), Submission.id.desc()).all()
    student_results = _dedupe_submissions_by_student(submissions)
    graded_student_results = [item for item in student_results if item.status == "matched"]

    classes = db.query(ClassRoom).options(
        joinedload(ClassRoom.exams).joinedload(Exam.exam_codes),
    ).order_by(ClassRoom.id.asc()).all()

    scores = [float(item.score) for item in graded_student_results]
    total = len(student_results)
    graded_total = len(graded_student_results)
    summary = AnalyticsSummary(
        total_submissions=total,
        average_score=_average(scores),
        median_score=calc_median(scores) if scores else 0.0,
        highest_score=max(scores) if scores else 0.0,
        lowest_score=min(scores) if scores else 0.0,
        pass_count=sum(1 for item in graded_student_results if float(item.score) >= 5.0),
        pass_rate=_percent(sum(1 for item in graded_student_results if float(item.score) >= 5.0), graded_total),
        excellent_count=sum(1 for item in graded_student_results if float(item.score) >= 8.0),
        excellent_rate=_percent(sum(1 for item in graded_student_results if float(item.score) >= 8.0), graded_total),
        matched_count=sum(1 for item in student_results if item.status == "matched"),
        unmatched_count=sum(1 for item in student_results if item.status == "unmatched"),
        unknown_code_count=sum(1 for item in student_results if item.status == "unknown_code"),
    )

    distribution = _build_distribution(scores)
    grade_bands = _build_grade_bands(graded_total, scores)
    comparison = _build_comparison(graded_student_results, classes, class_id, exam_id)

    target_answer_key: list[str] = []
    if exam_id is not None:
        target_exam = next((exam for class_room in classes for exam in class_room.exams if exam.id == exam_id), None)
        if target_exam and exam_code:
            target_exam_code = next((code for code in target_exam.exam_codes if code.code == exam_code), None)
            if target_exam_code:
                target_answer_key = list(target_exam_code.answer_key or [])
        elif target_exam and len(target_exam.exam_codes) == 1:
            target_answer_key = list(target_exam.exam_codes[0].answer_key or [])

    top_failed_questions = _build_question_insights(graded_student_results, target_answer_key)[:10] if target_answer_key else []

    scope = "overall"
    if class_id is not None and exam_id is None:
        scope = "class"
    elif class_id is not None and exam_id is not None and not exam_code:
        scope = "exam"
    elif class_id is not None and exam_id is not None and exam_code:
        scope = "code"

    return AnalyticsResponse(
        scope=scope,
        summary=summary,
        distribution=distribution,
        grade_bands=grade_bands,
        comparison=comparison,
        top_failed_questions=top_failed_questions,
    )
