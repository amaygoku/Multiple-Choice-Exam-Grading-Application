import argparse
import csv
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from answer_classifier_omr import TorchAnswerCellClassifier, process_answer_crop_with_classifier
from omr_pipeline import DEFAULT_OMR_CONFIG


ANSWER_CROP_NAMES = ("answer_1", "answer_2", "answer_3")


def parse_answers_csv(value):
    if not value:
        return []
    return [token.strip().upper() for token in value.split(",")]


def main():
    parser = argparse.ArgumentParser(description="Evaluate answer OMR using a cell classifier instead of pixel counting.")
    parser.add_argument("--ground-truth", default="data/ground_truth_review.csv")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts")
    parser.add_argument("--weight", default="data/answer_binary_model.pth")
    parser.add_argument("--image-size", type=int, default=96)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--report-json", default="data/eval_answer_classifier_report.json")
    parser.add_argument("--debug-dir", default="data/eval_answer_classifier_debug")
    args = parser.parse_args()

    classifier = TorchAnswerCellClassifier(args.weight, image_size=args.image_size, threshold=args.threshold)
    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)

    total_sheets = 0
    exact_match = 0
    total_answer_slots = 0
    answer_correct = 0
    details = []

    with Path(args.ground_truth).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_name = (row.get("image") or "").strip()
            if not image_name:
                continue

            truth_answers = parse_answers_csv((row.get("true_answers") or "").strip())
            if not truth_answers:
                continue

            stem = Path(image_name).stem
            crop_dir = Path(args.artifacts_dir) / stem / "crops"
            if not crop_dir.exists():
                continue

            total_sheets += 1
            pred_answers = []
            crop_details = {}

            for crop_name in ANSWER_CROP_NAMES:
                crop_path = crop_dir / f"{crop_name}.png"
                image = cv2.imread(str(crop_path))
                answers, debug_image, row_details = process_answer_crop_with_classifier(
                    image,
                    classifier=classifier,
                    config=DEFAULT_OMR_CONFIG,
                    threshold=args.threshold,
                )
                pred_answers.extend(answers)
                crop_details[crop_name] = row_details

                if debug_image is not None:
                    image_debug_dir = debug_dir / stem
                    image_debug_dir.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(image_debug_dir / f"{crop_name}_classifier.png"), debug_image)

            max_len = max(len(truth_answers), len(pred_answers))
            row_correct = 0
            for idx in range(max_len):
                truth = truth_answers[idx] if idx < len(truth_answers) else ""
                pred = pred_answers[idx] if idx < len(pred_answers) else ""
                if truth == pred:
                    row_correct += 1

            total_answer_slots += max_len
            answer_correct += row_correct
            if truth_answers == pred_answers:
                exact_match += 1

            details.append(
                {
                    "image": image_name,
                    "pred_answers": pred_answers,
                    "true_answers": truth_answers,
                    "answer_correct": row_correct,
                    "answer_total": max_len,
                    "crop_details": crop_details,
                }
            )

    report = {
        "weight": args.weight,
        "threshold": args.threshold,
        "total_sheets": total_sheets,
        "answer_accuracy": (answer_correct / total_answer_slots) if total_answer_slots else 0.0,
        "exact_sheet_match": (exact_match / total_sheets) if total_sheets else 0.0,
        "details": details,
    }
    Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
