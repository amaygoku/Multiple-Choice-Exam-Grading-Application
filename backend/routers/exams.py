from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models import Exam, Student
from backend.schemas import GradeRequest, GradingResult, ProcessExamResponse
from backend.services.exam_pipeline import decode_upload_image, run_exam_pipeline
from backend.services.ocr.grade_system import grade_paper
from backend.services.student_matching import resolve_student_name


legacy_router = APIRouter(tags=["Legacy frontend"])
api_router = APIRouter(prefix="/api/v1", tags=["OMR pipeline"])


@legacy_router.post("/upload", response_model=ProcessExamResponse)
async def upload_file(
    file: UploadFile = File(...),
    correct_answers: str = Form(""),
    debug_artifacts: bool = Form(True),
    force_legacy_for_camera: bool = Form(False),
    layout_version: str = Form("v2"),
):
    try:
        is_camera_capture = (file.filename == "camera_capture.png")
        use_classifier = not (force_legacy_for_camera and is_camera_capture)
        image = decode_upload_image(await file.read())
        return run_exam_pipeline(
            image,
            correct_answers,
            debug_artifacts=debug_artifacts,
            use_classifier=use_classifier,
            layout_version=layout_version,
        )
    except Exception as exc:
        return {
            "success": False,
            "message": "Processing failed.",
            "error": str(exc),
        }


@api_router.post(
    "/process-exam",
    response_model=ProcessExamResponse,
    summary="Process an answer sheet image",
)
async def process_exam(
    class_id: str | None = Form(None, description="Optional class id for persistence"),
    exam_id: str | None = Form(None, description="Optional exam id for persistence"),
    file: UploadFile = File(..., description="Answer sheet image"),
    correct_answers: str = Form("", description="Comma-separated answer key"),
    debug_artifacts: bool = Form(False, description="Save intermediate images for debugging"),
    force_legacy_for_camera: bool = Form(
        False,
        description="If true, force camera_capture.png to use legacy OMR scoring (no classifier).",
    ),
    layout_version: str = Form("v2", description="Layout version to use ('v1' or 'v2')"),
    db: Session = Depends(get_db),
):
    try:
        is_camera_capture = (file.filename == "camera_capture.png")
        use_classifier = not (force_legacy_for_camera and is_camera_capture)
        image = decode_upload_image(await file.read())
        result = run_exam_pipeline(
            image,
            correct_answers,
            debug_artifacts=debug_artifacts,
            use_classifier=use_classifier,
            layout_version=layout_version,
        )
        _resolve_student_preview_name(result, db, class_id, exam_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _resolve_student_preview_name(result: dict, db: Session, class_id: str | None, exam_id: str | None) -> None:
    student_info = dict(result.get("student_info") or {})
    detected_mssv = str(student_info.get("mssv") or "").strip()
    ocr_name = str(student_info.get("name") or "").strip()
    resolved_class_id = _resolve_class_id(db, class_id, exam_id)

    if not detected_mssv:
        student_info.setdefault("ocr_name", ocr_name)
        student_info.setdefault("matched_name", "")
        student_info.setdefault("name_source", "ocr")
        student_info.setdefault("name_similarity", 0.0)
        result["student_info"] = student_info
        return

    matched_student = None
    if resolved_class_id is not None:
        matched_student = (
            db.query(Student)
            .filter(Student.class_id == resolved_class_id, Student.mssv == detected_mssv)
            .first()
        )

    if matched_student is None:
        student_info["ocr_name"] = ocr_name
        student_info["matched_name"] = ""
        student_info["name_source"] = "ocr"
        student_info["name_similarity"] = 0.0
        student_info["name"] = ocr_name
        result["student_info"] = student_info
        return

    resolved = resolve_student_name(matched_student.full_name, ocr_name)
    student_info["ocr_name"] = resolved.ocr_name
    student_info["matched_name"] = resolved.matched_name
    student_info["name_source"] = resolved.name_source
    student_info["name_similarity"] = resolved.similarity
    student_info["name"] = resolved.resolved_name
    result["student_info"] = student_info


def _resolve_class_id(db: Session, class_id: str | None, exam_id: str | None) -> int | None:
    if class_id and str(class_id).strip():
        try:
            return int(class_id)
        except ValueError:
            return None

    if not exam_id or not str(exam_id).strip():
        return None

    try:
        resolved_exam_id = int(exam_id)
    except ValueError:
        return None

    exam = db.query(Exam).filter(Exam.id == resolved_exam_id).first()
    return exam.class_id if exam is not None else None


@api_router.post("/grade", response_model=GradingResult, summary="Grade answers only")
async def grade_only(request: GradeRequest):
    try:
        return grade_paper(request.student_answers, request.correct_answers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
