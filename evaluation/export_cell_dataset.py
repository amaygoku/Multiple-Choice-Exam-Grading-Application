import argparse
import csv
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extract_code import GRID_ROWS, normalize_code_grid
from omr_pipeline import DEFAULT_OMR_CONFIG, prepare_omr_canvas


ANSWER_CROP_NAMES = ("answer_1", "answer_2", "answer_3")
ANSWER_CHOICES = ("A", "B", "C", "D")


def parse_answers_csv(value):
    if not value:
        return []
    return [token.strip().upper() for token in value.split(",")]


def export_image(path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def crop_answer_cells(image, crop_name, image_name, truth_answers, output_dir, records, config):
    normalized_bgr, normalized_thresh, aligned = prepare_omr_canvas(image, config)
    if normalized_bgr is None or normalized_thresh is None:
        return 0

    normalized_gray = cv2.cvtColor(normalized_bgr, cv2.COLOR_BGR2GRAY)
    normalized_dir = output_dir / "normalized" / Path(image_name).stem
    export_image(normalized_dir / f"{crop_name}.png", normalized_gray)
    export_image(normalized_dir / f"{crop_name}_binary.png", normalized_thresh)

    top = config.crop_pad_top
    bottom = config.crop_pad_bottom
    left = config.crop_pad_left
    right = config.crop_pad_right
    if normalized_gray.shape[1] <= left + right or normalized_gray.shape[0] <= top + bottom:
        return 0

    work_gray = normalized_gray[top:normalized_gray.shape[0] - bottom, left:normalized_gray.shape[1] - right]
    row_height = work_gray.shape[0] / config.num_rows
    start_x = int(work_gray.shape[1] * config.q_col_ratio)
    cell_width = (work_gray.shape[1] - start_x) / config.num_choices
    exported = 0

    crop_idx = ANSWER_CROP_NAMES.index(crop_name)
    question_offset = crop_idx * config.num_rows

    for row_idx in range(config.num_rows):
        question_idx = question_offset + row_idx + 1
        truth = truth_answers[question_offset + row_idx] if question_offset + row_idx < len(truth_answers) else ""
        truth_set = set(truth)

        for col_idx, choice in enumerate(ANSWER_CHOICES[: config.num_choices]):
            y1 = int(row_idx * row_height) + config.cell_pad_top
            y2 = int((row_idx + 1) * row_height) - config.cell_pad_bottom
            x1 = start_x + int(col_idx * cell_width) + config.cell_pad_left
            x2 = start_x + int((col_idx + 1) * cell_width) - config.cell_pad_right
            if y2 <= y1 or x2 <= x1:
                continue

            cell = work_gray[y1:y2, x1:x2]
            label = 1 if choice in truth_set else 0
            rel_path = (
                Path("cells")
                / "answer"
                / f"label_{label}"
                / Path(image_name).stem
                / f"{crop_name}_q{question_idx:02d}_{choice}.png"
            )
            export_image(output_dir / rel_path, cell)
            records.append(
                {
                    "image": image_name,
                    "field": "answer",
                    "group": crop_name,
                    "item_index": question_idx,
                    "sub_index": col_idx,
                    "token": choice,
                    "label": label,
                    "truth": truth,
                    "aligned": aligned,
                    "normalized_path": str((normalized_dir / f"{crop_name}.png").relative_to(output_dir)),
                    "cell_path": str(rel_path),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": x2 - x1,
                    "height": y2 - y1,
                }
            )
            exported += 1

    return exported


def crop_code_cells(image, field_name, image_name, truth_value, num_cols, output_dir, records):
    normalized_gray, normalized_thresh = normalize_code_grid(image)
    if normalized_gray is None or normalized_thresh is None:
        return 0

    normalized_dir = output_dir / "normalized" / Path(image_name).stem
    export_image(normalized_dir / f"{field_name}.png", normalized_gray)
    export_image(normalized_dir / f"{field_name}_binary.png", normalized_thresh)

    cell_width = normalized_gray.shape[1] / num_cols
    cell_height = normalized_gray.shape[0] / GRID_ROWS
    exported = 0

    for col_idx in range(num_cols):
        truth_digit = truth_value[col_idx] if col_idx < len(truth_value) else "?"
        for row_idx in range(GRID_ROWS):
            x1 = int(col_idx * cell_width)
            x2 = int((col_idx + 1) * cell_width)
            y1 = int(row_idx * cell_height)
            y2 = int((row_idx + 1) * cell_height)
            if y2 <= y1 or x2 <= x1:
                continue

            cell = normalized_gray[y1:y2, x1:x2]
            token = str(row_idx)
            label = 1 if truth_digit == token else 0
            rel_path = (
                Path("cells")
                / field_name
                / f"label_{label}"
                / Path(image_name).stem
                / f"{field_name}_c{col_idx + 1:02d}_d{token}.png"
            )
            export_image(output_dir / rel_path, cell)
            records.append(
                {
                    "image": image_name,
                    "field": field_name,
                    "group": field_name,
                    "item_index": col_idx + 1,
                    "sub_index": row_idx,
                    "token": token,
                    "label": label,
                    "truth": truth_digit,
                    "aligned": True,
                    "normalized_path": str((normalized_dir / f"{field_name}.png").relative_to(output_dir)),
                    "cell_path": str(rel_path),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": x2 - x1,
                    "height": y2 - y1,
                }
            )
            exported += 1

    return exported


def main():
    parser = argparse.ArgumentParser(description="Export OMR cell dataset using grid coordinates and reviewed ground truth.")
    parser.add_argument("--ground-truth", default="data/ground_truth_review.csv")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts")
    parser.add_argument("--output-dir", default="data/cell_dataset")
    parser.add_argument("--manifest-csv", default="data/cell_dataset/manifest.csv")
    parser.add_argument("--manifest-json", default="data/cell_dataset/manifest.json")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = Path(args.artifacts_dir)
    config = DEFAULT_OMR_CONFIG

    records = []
    summary = {
        "images": 0,
        "answer_cells": 0,
        "mssv_cells": 0,
        "ma_de_cells": 0,
    }

    with Path(args.ground_truth).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_name = (row.get("image") or "").strip()
            if not image_name:
                continue

            stem = Path(image_name).stem
            crop_dir = artifacts_dir / stem / "crops"
            if not crop_dir.exists():
                continue

            summary["images"] += 1
            truth_answers = parse_answers_csv((row.get("true_answers") or "").strip())
            truth_mssv = (row.get("true_mssv") or "").strip()
            truth_made = (row.get("true_ma_de") or "").strip()

            for crop_name in ANSWER_CROP_NAMES:
                crop_path = crop_dir / f"{crop_name}.png"
                image = cv2.imread(str(crop_path))
                if image is None:
                    continue
                summary["answer_cells"] += crop_answer_cells(
                    image=image,
                    crop_name=crop_name,
                    image_name=image_name,
                    truth_answers=truth_answers,
                    output_dir=output_dir,
                    records=records,
                    config=config,
                )

            mssv_path = crop_dir / "mssv.png"
            mssv_image = cv2.imread(str(mssv_path))
            if mssv_image is not None and truth_mssv:
                summary["mssv_cells"] += crop_code_cells(
                    image=mssv_image,
                    field_name="mssv",
                    image_name=image_name,
                    truth_value=truth_mssv,
                    num_cols=8,
                    output_dir=output_dir,
                    records=records,
                )

            made_path = crop_dir / "ma_de.png"
            made_image = cv2.imread(str(made_path))
            if made_image is not None and truth_made:
                summary["ma_de_cells"] += crop_code_cells(
                    image=made_image,
                    field_name="ma_de",
                    image_name=image_name,
                    truth_value=truth_made,
                    num_cols=3,
                    output_dir=output_dir,
                    records=records,
                )

    manifest_csv = Path(args.manifest_csv)
    manifest_csv.parent.mkdir(parents=True, exist_ok=True)
    with manifest_csv.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "image",
            "field",
            "group",
            "item_index",
            "sub_index",
            "token",
            "label",
            "truth",
            "aligned",
            "normalized_path",
            "cell_path",
            "x1",
            "y1",
            "x2",
            "y2",
            "width",
            "height",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)

    manifest_json = Path(args.manifest_json)
    manifest_json.parent.mkdir(parents=True, exist_ok=True)
    manifest_json.write_text(
        json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({"summary": summary, "manifest_csv": str(manifest_csv), "manifest_json": str(manifest_json)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
