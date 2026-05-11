import os

import cv2
import numpy as np
from PIL import Image

from extract_code import extract_id_and_code, extract_id_and_code_image


OCR_AVAILABLE = False
try:
    from vietocr.tool.config import Cfg
    from vietocr.tool.predictor import Predictor

    config = Cfg.load_config_from_name("vgg_seq2seq")
    config["weights"] = "./seq2seqocr2.pth"
    config["cnn"]["pretrained"] = False
    config["predictor"]["beam_width"] = 5
    config["device"] = "cpu"
    detector = Predictor(config)
    OCR_AVAILABLE = True
except Exception as e:
    print(f"[OCR LOAD ERROR] {e}")


def kmeans_binarize(img):
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    pixel_values = np.float32(gray.reshape((-1, 1)))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(pixel_values, 2, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    bg_label, fg_label = (0, 1) if centers[0] > centers[1] else (1, 0)
    res = np.zeros_like(labels, dtype=np.uint8)
    res[labels == bg_label] = 255
    res[labels == fg_label] = 0
    return res.reshape(gray.shape)


def adaptive_resize_pad(img_np, target_h=50, target_w=512):
    h, w = img_np.shape[:2]
    new_w = int(w * (target_h / h))
    if new_w > target_w:
        resized = cv2.resize(img_np, (target_w, target_h), interpolation=cv2.INTER_AREA)
        new_w = target_w
    else:
        resized = cv2.resize(img_np, (new_w, target_h), interpolation=cv2.INTER_AREA)
    pad_right = target_w - new_w
    return cv2.copyMakeBorder(resized, 0, 0, 0, pad_right, cv2.BORDER_CONSTANT, value=255)


def ocr_read_name_image(crop_img):
    if not OCR_AVAILABLE:
        return "KHONG CO MODEL OCR"
    if crop_img is None:
        return ""

    try:
        cleaned_img_np = kmeans_binarize(crop_img)
        cleaned_img_np = adaptive_resize_pad(cleaned_img_np)
        cleaned_img_pil = Image.fromarray(cleaned_img_np).convert("RGB")
        return detector.predict(cleaned_img_pil)
    except Exception:
        return "LOI OCR"


def ocr_read_name(image_path):
    if not os.path.exists(image_path):
        return "KHONG CO ANH"
    crop_img = cv2.imread(image_path)
    return ocr_read_name_image(crop_img)


def read_student_info_from_crops(crops):
    """Read MSSV, exam code, and name from in-memory crops."""
    ma_de = extract_id_and_code_image(crops.get("ma_de"), 3)
    mssv = extract_id_and_code_image(crops.get("mssv"), 8)
    name_crop = crops.get("ho_va_ten_refined")
    if name_crop is None:
        name_crop = crops.get("ho_va_ten")
    name = ocr_read_name_image(name_crop)

    return {
        "mssv": mssv,
        "ma_de": ma_de,
        "name": name,
    }


def read_student_info(crops_dir):
    ma_de = extract_id_and_code(os.path.join(crops_dir, "ma_de.png"), 3)
    mssv = extract_id_and_code(os.path.join(crops_dir, "mssv.png"), 8)
    name = ocr_read_name(os.path.join(crops_dir, "ho_va_ten_refined.png"))

    return {
        "mssv": mssv,
        "ma_de": ma_de,
        "name": name,
    }


if __name__ == "__main__":
    print(ocr_read_name("D:\\OCR\\results\\crops\\ho_va_ten_refined.png"))
