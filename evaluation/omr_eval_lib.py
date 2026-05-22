import csv
import json
from pathlib import Path

import cv2

from crop import crop_regions_image
from detect_paper import align_document_image
from extract_code import extract_id_and_code_image
from ocr import ocr_read_name_image
from omr_pipeline import DEFAULT_OMR_CONFIG, omr_config_to_dict, process_omr_image
from preprocessing_crop import preprocess_text_crop_images


ANSWER_CROP_NAMES = ("answer_1", "answer_2", "answer_3")


def process_sheet_image(image_path, output_dir=None, omr_config=None):
    image_path = Path(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    output_dir = Path(output_dir) if output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    aligned = align_document_image(image)
    if aligned is None:
        raise ValueError(f"Could not align sheet: {image_path.name}")
    if output_dir:
        cv2.imwrite(str(output_dir / "aligned.png"), aligned)

    visualized, crops = crop_regions_image(aligned)
    if visualized is None or not crops:
        raise ValueError(f"Could not crop regions: {image_path.name}")
    if output_dir:
        cv2.imwrite(str(output_dir / "visualized_boxes.png"), visualized)

    crops = preprocess_text_crop_images(crops)
    if output_dir:
        crops_dir = output_dir / "crops"
        crops_dir.mkdir(exist_ok=True)
        for name, crop in crops.items():
            if crop is not None:
                cv2.imwrite(str(crops_dir / f"{name}.png"), crop)

    name_crop = crops.get("ho_va_ten_refined")
    if name_crop is None:
        name_crop = crops.get("ho_va_ten")

    student_info = {
        "mssv": extract_id_and_code_image(crops.get("mssv"), 8),
        "ma_de": extract_id_and_code_image(crops.get("ma_de"), 3),
        "name": ocr_read_name_image(name_crop),
    }

    answers = []
    omr_details = {}
    config = omr_config or DEFAULT_OMR_CONFIG
    for crop_name in ANSWER_CROP_NAMES:
        detected, result_image = process_omr_image(
            crops.get(crop_name),
            start_question_idx=len(answers) + 1,
            config=config,
        )
        if detected:
            answers.extend(detected)
        if output_dir and result_image is not None:
            omr_dir = output_dir / "omr"
            omr_dir.mkdir(exist_ok=True)
            cv2.imwrite(str(omr_dir / f"{crop_name}_result.png"), result_image)
        omr_details[crop_name] = detected

    return {
        "image": image_path.name,
        "student_info": student_info,
        "answers": answers,
        "answer_count": len(answers),
        "omr_config": omr_config_to_dict(config),
        "omr_details": omr_details,
    }


def load_answer_crops(artifact_dir):
    artifact_dir = Path(artifact_dir)
    crops_dir = artifact_dir / "crops"
    crops = {}
    for crop_name in ANSWER_CROP_NAMES:
        crop_path = crops_dir / f"{crop_name}.png"
        crops[crop_name] = cv2.imread(str(crop_path)) if crop_path.exists() else None
    return crops


def process_answer_crops(crops, omr_config=None):
    answers = []
    omr_details = {}
    config = omr_config or DEFAULT_OMR_CONFIG

    for crop_name in ANSWER_CROP_NAMES:
        detected, _ = process_omr_image(
            crops.get(crop_name),
            start_question_idx=len(answers) + 1,
            config=config,
        )
        if detected:
            answers.extend(detected)
        omr_details[crop_name] = detected

    return {
        "answers": answers,
        "answer_count": len(answers),
        "omr_config": omr_config_to_dict(config),
        "omr_details": omr_details,
    }


def write_bootstrap_files(records, output_jsonl, output_csv):
    output_jsonl = Path(output_jsonl)
    output_csv = Path(output_csv)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_jsonl.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "image",
                "pred_mssv",
                "pred_ma_de",
                "pred_name",
                "pred_answers",
                "true_mssv",
                "true_ma_de",
                "true_answers",
                "notes",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "image": record["image"],
                    "pred_mssv": record["student_info"]["mssv"],
                    "pred_ma_de": record["student_info"]["ma_de"],
                    "pred_name": record["student_info"]["name"],
                    "pred_answers": ",".join(record["answers"]),
                    "true_mssv": "",
                    "true_ma_de": "",
                    "true_answers": "",
                    "notes": "",
                }
            )


def load_ground_truth_csv(csv_path):
    rows = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows
