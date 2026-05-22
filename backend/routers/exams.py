from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.schemas import GradeRequest, GradingResult, ProcessExamResponse
from backend.services.exam_pipeline import decode_upload_image, run_exam_pipeline
from grade_system import grade_paper


legacy_router = APIRouter(tags=["Legacy frontend"])
api_router = APIRouter(prefix="/api/v1", tags=["OMR pipeline"])


@legacy_router.post("/upload", response_model=ProcessExamResponse)
async def upload_file(
    file: UploadFile = File(...),
    correct_answers: str = Form(""),
    debug_artifacts: bool = Form(True),
    force_legacy_for_camera: bool = Form(False),
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
    file: UploadFile = File(..., description="Answer sheet image"),
    correct_answers: str = Form("", description="Comma-separated answer key"),
    debug_artifacts: bool = Form(False, description="Save intermediate images for debugging"),
    force_legacy_for_camera: bool = Form(
        False,
        description="If true, force camera_capture.png to use legacy OMR scoring (no classifier).",
    ),
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
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api_router.post("/grade", response_model=GradingResult, summary="Grade answers only")
async def grade_only(request: GradeRequest):
    try:
        return grade_paper(request.student_answers, request.correct_answers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
