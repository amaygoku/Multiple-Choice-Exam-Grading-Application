from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .extract_code import extract_id_and_code, extract_id_and_code_image


SCRIPT_DIR = Path(__file__).resolve().parents[3]
DETECT_TEXT_DIR = SCRIPT_DIR / "detect_text"
if str(DETECT_TEXT_DIR) not in sys.path:
    sys.path.insert(0, str(DETECT_TEXT_DIR))

try:
    import torch
    from yolo_crnn_pipeline import (
        DEFAULT_CRNN_WEIGHTS,
        DEFAULT_YOLO_WEIGHTS,
        build_ocr_runtime,
        process_image_bgr,
    )

    OCR_AVAILABLE = True
except Exception as exc:  # pragma: no cover - runtime fallback
    OCR_AVAILABLE = False
    _OCR_IMPORT_ERROR = exc
    torch = None  # type: ignore[assignment]
    build_ocr_runtime = None  # type: ignore[assignment]
    process_image_bgr = None  # type: ignore[assignment]
    DEFAULT_YOLO_WEIGHTS = None  # type: ignore[assignment]
    DEFAULT_CRNN_WEIGHTS = None  # type: ignore[assignment]
    print(f"[OCR LOAD ERROR] {exc}")


_OCR_RUNTIME = None


def get_ocr_runtime():
    global _OCR_RUNTIME
    if _OCR_RUNTIME is not None:
        return _OCR_RUNTIME
    if not OCR_AVAILABLE:
        return None

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _OCR_RUNTIME = build_ocr_runtime(
        yolo_weights=DEFAULT_YOLO_WEIGHTS,
        crnn_weights=DEFAULT_CRNN_WEIGHTS,
        device=device,
    )
    return _OCR_RUNTIME


def ocr_read_name_image(crop_img):
    if crop_img is None:
        return ""

    runtime = get_ocr_runtime()
    if runtime is None:
        return "KHONG CO MODEL OCR"

    try:
        result = process_image_bgr(
            image_bgr=crop_img,
            runtime=runtime,
            image_name="name_crop",
            image_path_repr=None,
            conf=0.25,
            iou=0.45,
            pad=0,
            min_area=0,
            save_crops_dir=None,
            save_annotated_dir=None,
            debug=False,
            save_debug_dir=None,
        )
        return result["joined_text"] or result["compact_text"] or ""
    except Exception as exc:
        print(f"[ERROR] OCR name failed: {exc}")
        return "LOI OCR"


def ocr_read_name(image_path):
    if not os.path.exists(image_path):
        return "KHONG CO ANH"
    crop_img = cv2.imread(image_path)
    return ocr_read_name_image(crop_img)


def read_student_info_from_crops(crops, use_classifier=True):
    """Read MSSV, exam code, and name from in-memory crops."""
    ma_de = extract_id_and_code_image(crops.get("ma_de"), 3, use_classifier=use_classifier)
    mssv = extract_id_and_code_image(crops.get("mssv"), 8, use_classifier=use_classifier)
    name_crop = crops.get("ho_va_ten_refined")
    if name_crop is None:
        name_crop = crops.get("ho_va_ten")
    name = ocr_read_name_image(name_crop)

    return {
        "mssv": mssv,
        "ma_de": ma_de,
        "name": name,
    }


def read_student_info(crops_dir, use_classifier=True):
    ma_de = extract_id_and_code(os.path.join(crops_dir, "ma_de.png"), 3, use_classifier=use_classifier)
    mssv = extract_id_and_code(os.path.join(crops_dir, "mssv.png"), 8, use_classifier=use_classifier)
    name = ocr_read_name(os.path.join(crops_dir, "ho_va_ten_refined.png"))

    return {
        "mssv": mssv,
        "ma_de": ma_de,
        "name": name,
    }


if __name__ == "__main__":
    print(ocr_read_name("D:\\OCR\\results\\crops\\ho_va_ten_refined.png"))
