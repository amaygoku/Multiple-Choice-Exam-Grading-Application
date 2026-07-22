import cv2
import numpy as np
import os
from pathlib import Path

from .detect_paper import four_point_transform


def improve_single_crop_image(img):
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_cnt = max(contours, key=cv2.contourArea)

        peri = cv2.arcLength(largest_cnt, True)
        approx = cv2.approxPolyDP(largest_cnt, 0.02 * peri, True)

        if len(approx) == 4:
            warped = four_point_transform(img, approx.reshape(4, 2))
        else:
            rect = cv2.minAreaRect(largest_cnt)
            box = cv2.boxPoints(rect)
            box = np.int32(box)
            warped = four_point_transform(img, box.reshape(4, 2))

        h, w = warped.shape[:2]
        margin = 5
        iy = margin
        ih = h - 2 * margin
        ix = margin
        iw = w - 2 * margin
        if iw > 0 and ih > 0:
            crop = warped[iy:iy + ih, ix:ix + iw]
            lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = cv2.normalize(l, None, 0, 255, cv2.NORM_MINMAX)
            l = cv2.addWeighted(l, 1.2, l, 0, -30)
            final_lab = cv2.merge((l, a, b))
            result = cv2.cvtColor(final_lab, cv2.COLOR_LAB2BGR)
            return result

    return img


def _improve_single_crop(img_path, output_path):
    img = cv2.imread(img_path)
    result = improve_single_crop_image(img)
    if result is not None:
        cv2.imwrite(output_path, result)


def preprocess_text_crop_images(crops):
    """Return refined text crops while keeping the original crop dict intact."""
    refined = dict(crops)
    for field in ["ho_va_ten", "lop", "mon"]:
        if field in crops:
            refined[f"{field}_refined"] = improve_single_crop_image(crops[field])
    return refined


def preprocess_text_crops(crops_dir):
    """Tien xu ly anh cac vung text (Ho ten, Lop, Mon hoc)"""
    crops_dir = Path(crops_dir)
    for field in ["ho_va_ten", "lop", "mon"]:
        input_p = crops_dir / f"{field}.png"
        out_p = crops_dir / f"{field}_refined.png"
        if input_p.exists():
            _improve_single_crop(str(input_p), str(out_p))
