# Backend structure

This package keeps the API layer separate from the OCR/OMR algorithms that
already exist at the project root.

## Modules

- `main.py`: creates the FastAPI app, mounts static/result folders, and includes routers.
- `core/config.py`: central paths and runtime directory setup.
- `schemas.py`: Pydantic request/response models.
- `routers/exams.py`: HTTP endpoints for upload, processing, and grading.
- `services/exam_pipeline.py`: in-memory orchestration for document alignment, crop, OCR, OMR, and grading.

## Public endpoints

- `GET /`: serves the existing frontend.
- `POST /upload`: compatibility endpoint used by `static/script.js`; saves debug images by default so the current UI can display them.
- `POST /api/v1/process-exam`: versioned endpoint for new clients; runs without filesystem artifacts by default.
- `POST /api/v1/grade`: grade an answer list without reprocessing an image.

`/api/v1/process-exam` accepts `debug_artifacts=true` as form data when you need
to inspect intermediate images. In normal backend mode, uploaded files are decoded
with OpenCV and passed through the pipeline as `np.ndarray` objects without writing
temporary images to disk.

## Algorithm modules

The image-processing modules are still imported from the project root:

- `detect_paper.py`
- `crop.py`
- `preprocessing_crop.py`
- `ocr.py`
- `omr_pipeline.py`
- `grade_system.py`

They can be moved into a dedicated package later after the API boundary is stable.
