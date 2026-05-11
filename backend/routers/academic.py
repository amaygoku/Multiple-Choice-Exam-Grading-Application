from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    SubmissionCreate,
    SubmissionResponse,
    SubmissionUpdate,
)


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Constraint conflict") from exc


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
    return query.order_by(Submission.id.desc()).all()


@academic_router.post("/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    _get_or_404(db, ClassRoom, payload.class_id, "Class")
    _get_or_404(db, Exam, payload.exam_id, "Exam")
    if payload.exam_code_id is not None:
        _get_or_404(db, ExamCode, payload.exam_code_id, "Exam code")
    if payload.student_id is not None:
        _get_or_404(db, Student, payload.student_id, "Student")
    item = Submission(**payload.model_dump())
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
    if payload.student_id is not None:
        _get_or_404(db, Student, payload.student_id, "Student")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    _commit_or_409(db)
    db.refresh(item)
    return item


@academic_router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(submission_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, Submission, submission_id, "Submission")
    db.delete(item)
    db.commit()
