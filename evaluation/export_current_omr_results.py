import argparse
import csv
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omr_pipeline import DEFAULT_OMR_CONFIG, process_omr_image


ANSWER_CROPS = ("answer_1", "answer_2", "answer_3")


def parse_answers_csv(raw):
    if not raw:
        return []
    return [token.strip().upper() for token in raw.split(",")]


def main():
    parser = argparse.ArgumentParser(description="Export current OMR result images for all reviewed sheets.")
    parser.add_argument("--ground-truth", default="data/ground_truth_review.csv")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts")
    parser.add_argument("--output-dir", default="data/eval_results_current")
    parser.add_argument("--summary-json", default="data/eval_results_current/summary.json")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    artifacts_dir = Path(args.artifacts_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    with gt_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_name = (row.get("image") or "").strip()
            true_answers = parse_answers_csv((row.get("true_answers") or "").strip())
            if not image_name:
                continue

            stem = Path(image_name).stem
            image_output_dir = output_dir / stem
            image_output_dir.mkdir(parents=True, exist_ok=True)

            pred_answers = []
            for crop_name in ANSWER_CROPS:
                crop_path = artifacts_dir / stem / "crops" / f"{crop_name}.png"
                crop = cv2.imread(str(crop_path))
                detected, result_image = process_omr_image(
                    crop,
                    start_question_idx=len(pred_answers) + 1,
                    config=DEFAULT_OMR_CONFIG,
                )
                if detected:
                    pred_answers.extend(detected)
                if result_image is not None:
                    cv2.imwrite(str(image_output_dir / f"{crop_name}_result.png"), result_image)

            matches = 0
            for idx in range(max(len(true_answers), len(pred_answers))):
                truth = true_answers[idx] if idx < len(true_answers) else ""
                pred = pred_answers[idx] if idx < len(pred_answers) else ""
                if truth == pred:
                    matches += 1

            summary.append(
                {
                    "image": image_name,
                    "result_dir": str(image_output_dir),
                    "answer_correct": matches,
                    "answer_total": max(len(true_answers), len(pred_answers)),
                }
            )

    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported results for {len(summary)} images to: {output_dir}")


if __name__ == "__main__":
    main()
