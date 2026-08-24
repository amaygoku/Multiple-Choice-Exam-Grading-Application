import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.services.ocr.crop import crop_regions_image
from backend.services.ocr.detect_paper import align_document_image
from backend.services.ocr.grade_system import grade_paper
from backend.services.ocr.ocr import ocr_read_name_image
from backend.services.ocr.extract_code import analyze_id_and_code_image, render_id_code_debug_image
from backend.services.ocr.omr_pipeline import DEFAULT_OMR_CONFIG, OMR_CONFIG_V2, process_omr_image
from backend.services.ocr.preprocessing_crop import preprocess_text_crop_images

from backend.core.config import STORAGE_BACKEND
from backend.core.storage import get_storage_backend


ANSWER_CROP_NAMES = ("answer_1", "answer_2", "answer_3")


class ArtifactStore:
    """Optional filesystem writer for debug images."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or uuid.uuid4().hex
        self.storage = get_storage_backend()

    def prepare(self) -> None:
        return None

    def save_image(self, relative_path: str, image) -> Optional[str]:
        if image is None:
            return None

        object_key = f"{self.request_id}/{relative_path}".replace("\\", "/")
        return self.storage.save_image(object_key, image)


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
    use_classifier: bool = True,
    layout_version: str = "v2",
) -> dict:
    """Run the exam pipeline in memory.

    Filesystem writes happen only when debug_artifacts=True.
    """
    if layout_version == "v2":
        # Classifier models are trained on v1 cell aspect ratios/positions.
        # Traditional pipeline is 100% accurate for v2, so we force-bypass classifier.
        use_classifier = False

    artifact_store = ArtifactStore() if (debug_artifacts or STORAGE_BACKEND == "s3") else None
    if artifact_store:
        artifact_store.prepare()
        artifact_store.save_image("upload.png", image)

    aligned_image = align_document_image(image)
    if aligned_image is None:
        raise ValueError("Could not detect or align the answer sheet.")
    if artifact_store:
        artifact_store.save_image("aligned_paper.png", aligned_image)

    visualized_image, crops = crop_regions_image(aligned_image, layout_version=layout_version)

    if visualized_image is None or not crops:
        raise ValueError("Could not crop answer sheet regions.")

    crops = preprocess_text_crop_images(crops)

    # Analyze student ID (MSSV) and exam code (Ma De) to get both prediction and OMR grid visualization
    mssv_analysis = analyze_id_and_code_image(crops.get("mssv"), num_cols=8, use_classifier=use_classifier)
    ma_de_analysis = analyze_id_and_code_image(crops.get("ma_de"), num_cols=3, use_classifier=use_classifier)

    mssv_grid = render_id_code_debug_image(mssv_analysis["normalized_gray"], mssv_analysis, num_cols=8)
    ma_de_grid = render_id_code_debug_image(ma_de_analysis["normalized_gray"], ma_de_analysis, num_cols=3)

    # Overwrite the crops in the dictionary with their OMR-visualized grid counterparts
    if mssv_grid is not None:
        crops["mssv"] = mssv_grid
    if ma_de_grid is not None:
        crops["ma_de"] = ma_de_grid

    # Perform student name OCR
    name_crop = crops.get("ho_va_ten_refined")
    if name_crop is None:
        name_crop = crops.get("ho_va_ten")
    name = ocr_read_name_image(name_crop)

    student_info = {
        "mssv": mssv_analysis["prediction"],
        "ma_de": ma_de_analysis["prediction"],
        "name": name,
    }

    omr_config = OMR_CONFIG_V2 if layout_version == "v2" else DEFAULT_OMR_CONFIG

    answers = []
    omr_result_images = {}
    omr_preproc_debug = {}
    for crop_name in ANSWER_CROP_NAMES:
        crop_preproc = {}
        detected, result_image = process_omr_image(
            crops.get(crop_name),
            start_question_idx=len(answers) + 1,
            debug=debug_artifacts,
            use_classifier=use_classifier,
            preproc_debug=crop_preproc,
            config=omr_config,
        )
        if detected:
            answers.extend(detected)
        if result_image is not None:
            omr_result_images[crop_name] = result_image
        if crop_preproc:
            omr_preproc_debug[crop_name] = crop_preproc

    grading = None
    if correct_answers and correct_answers.strip():
        grading = grade_paper(answers, correct_answers)

    image_urls = _save_debug_artifacts(
        artifact_store,
        image,
        aligned_image,
        visualized_image,
        crops,
        omr_result_images,
        omr_preproc_debug=omr_preproc_debug,
    )

    return {
        "success": True,
        "message": "Processed answer sheet successfully.",
        "student_info": student_info,
        "answers": answers,
        "grading": grading,
        "source_image_url": image_urls["source"],
        "aligned_image_url": image_urls["aligned"],
        "result_image_url": image_urls["visualized"],
        "crops": image_urls["crops"],
        "omr_images": image_urls["omr"],
        "preprocess_images": image_urls["preprocess"],
    }


def _save_debug_artifacts(artifact_store, source_image, aligned_image, visualized_image, crops, omr_result_images, omr_preproc_debug=None):
    crop_urls = {
        "ho_va_ten": None,
        "lop": None,
        "mssv": None,
        "ma_de": None,
    }
    omr_urls = {}
    preprocess_urls = {}
    if not artifact_store:
        return {
            "source": None,
            "aligned": None,
            "visualized": None,
            "crops": crop_urls,
            "omr": omr_urls,
            "preprocess": preprocess_urls,
        }

    source_url = artifact_store.save_image("upload.png", source_image)
    aligned_url = artifact_store.save_image("aligned_paper.png", aligned_image)
    visualized_url = artifact_store.save_image("visualized_boxes.png", visualized_image)

    crop_url_map = {
        "ho_va_ten_refined": "ho_va_ten",
        "ho_va_ten": "ho_va_ten",
        "lop_refined": "lop",
        "lop": "lop",
        "mssv": "mssv",
        "ma_de": "ma_de",
    }

    for name, image in crops.items():
        saved_url = artifact_store.save_image(f"crops/{name}.png", image)
        mapped_key = crop_url_map.get(name)
        if mapped_key:
            crop_urls[mapped_key] = saved_url

    for name, image in omr_result_images.items():
        omr_urls[name] = artifact_store.save_image(f"omr/{name}_result.png", image)

    if omr_preproc_debug:
        for crop_name, preproc in omr_preproc_debug.items():
            for step_name, img in preproc.items():
                url = artifact_store.save_image(f"preprocess/{crop_name}_{step_name}.png", img)
                preprocess_urls[f"{crop_name}_{step_name}"] = url

    return {
        "source": source_url,
        "aligned": aligned_url,
        "visualized": visualized_url,
        "crops": crop_urls,
        "omr": omr_urls,
        "preprocess": preprocess_urls,
    }
