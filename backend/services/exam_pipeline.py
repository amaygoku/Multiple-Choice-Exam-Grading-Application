import time
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from crop import crop_regions_image
from detect_paper import align_document_image
from grade_system import grade_paper
from ocr import read_student_info_from_crops
from omr_pipeline import process_omr_image
from preprocessing_crop import preprocess_text_crop_images

from backend.core.config import RESULTS_DIR


ANSWER_CROP_NAMES = ("answer_1", "answer_2", "answer_3")


class ArtifactStore:
    """Optional filesystem writer for debug images."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or uuid.uuid4().hex
        self.root = RESULTS_DIR / self.request_id
        self.crops_dir = self.root / "crops"
        self.omr_dir = self.root / "omr"

    def prepare(self) -> None:
        self.crops_dir.mkdir(parents=True, exist_ok=True)
        self.omr_dir.mkdir(parents=True, exist_ok=True)

    def save_image(self, relative_path: str, image) -> Optional[str]:
        if image is None:
            return None

        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)
        timestamp = int(time.time())
        url_path = relative_path.replace("\\", "/")
        return f"/results/{self.request_id}/{url_path}?t={timestamp}"


def decode_upload_image(upload_bytes: bytes):
    """Decode an uploaded image into an OpenCV BGR image without writing to disk."""
    data = np.frombuffer(upload_bytes, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image format or corrupted image.")
    return image


def run_exam_pipeline(
    image,
    correct_answers: str = "",
    debug_artifacts: bool = False,
) -> dict:
    """Run the exam pipeline in memory.

    Filesystem writes happen only when debug_artifacts=True.
    """
    artifact_store = ArtifactStore() if debug_artifacts else None
    if artifact_store:
        artifact_store.prepare()
        artifact_store.save_image("upload.png", image)

    aligned_image = align_document_image(image)
    if aligned_image is None:
        raise ValueError("Could not detect or align the answer sheet.")
    if artifact_store:
        artifact_store.save_image("aligned_paper.png", aligned_image)

    visualized_image, crops = crop_regions_image(aligned_image)
    if visualized_image is None or not crops:
        raise ValueError("Could not crop answer sheet regions.")

    crops = preprocess_text_crop_images(crops)
    student_info = read_student_info_from_crops(crops)

    answers = []
    omr_result_images = {}
    for crop_name in ANSWER_CROP_NAMES:
        detected, result_image = process_omr_image(
            crops.get(crop_name),
            start_question_idx=len(answers) + 1,
            debug=debug_artifacts,
        )
        if detected:
            answers.extend(detected)
        if result_image is not None:
            omr_result_images[crop_name] = result_image

    grading = None
    if correct_answers and correct_answers.strip():
        grading = grade_paper(answers, correct_answers)

    image_urls = _save_debug_artifacts(
        artifact_store,
        visualized_image,
        crops,
        omr_result_images,
    )

    return {
        "success": True,
        "message": "Processed answer sheet successfully.",
        "student_info": student_info,
        "answers": answers,
        "grading": grading,
        "result_image_url": image_urls["visualized"],
        "crops": image_urls["crops"],
    }


def _save_debug_artifacts(artifact_store, visualized_image, crops, omr_result_images):
    crop_urls = {
        "ho_va_ten": None,
        "lop": None,
        "mssv": None,
        "ma_de": None,
    }
    if not artifact_store:
        return {"visualized": None, "crops": crop_urls}

    visualized_url = artifact_store.save_image("visualized_boxes.png", visualized_image)

    for name, image in crops.items():
        artifact_store.save_image(f"crops/{name}.png", image)

    for name, image in omr_result_images.items():
        artifact_store.save_image(f"omr/{name}_result.png", image)

    crop_urls["ho_va_ten"] = _artifact_crop_url(artifact_store, "ho_va_ten_refined")
    crop_urls["lop"] = _artifact_crop_url(artifact_store, "lop_refined")
    crop_urls["mssv"] = _artifact_crop_url(artifact_store, "mssv")
    crop_urls["ma_de"] = _artifact_crop_url(artifact_store, "ma_de")

    return {"visualized": visualized_url, "crops": crop_urls}


def _artifact_crop_url(artifact_store: ArtifactStore, name: str) -> str:
    path = Path("crops") / f"{name}.png"
    timestamp = int(time.time())
    return f"/results/{artifact_store.request_id}/{path.as_posix()}?t={timestamp}"
