import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.omr_eval_lib import load_answer_crops, load_ground_truth_csv, process_answer_crops
from omr_pipeline import OMRConfig


def normalize_answers(value):
    if not value:
        return []
    return [token.strip().upper() for token in value.split(",")]


def build_tuning_dataset(rows, artifacts_dir):
    dataset = []
    for row in rows:
        if not row.get("true_answers"):
            continue
        image_name = row["image"]
        artifact_dir = artifacts_dir / Path(image_name).stem
        crops = load_answer_crops(artifact_dir)
        dataset.append(
            {
                "image": image_name,
                "true_answers": normalize_answers(row["true_answers"]),
                "crops": crops,
            }
        )
    return dataset


def score_config(dataset, config):
    total_slots = 0
    correct_slots = 0
    exact_match = 0
    total_sheets = 0

    for row in dataset:
        total_sheets += 1
        prediction = process_answer_crops(row["crops"], omr_config=config)
        true_answers = row["true_answers"]
        pred_answers = prediction["answers"]
        max_len = max(len(true_answers), len(pred_answers))
        row_ok = True
        for idx in range(max_len):
            truth = true_answers[idx] if idx < len(true_answers) else ""
            pred = pred_answers[idx] if idx < len(pred_answers) else ""
            total_slots += 1
            if truth == pred:
                correct_slots += 1
            else:
                row_ok = False
        if row_ok and true_answers == pred_answers:
            exact_match += 1

    return {
        "answer_accuracy": (correct_slots / total_slots) if total_slots else 0.0,
        "exact_sheet_match": (exact_match / total_sheets) if total_sheets else 0.0,
        "total_sheets": total_sheets,
    }


def main():
    parser = argparse.ArgumentParser(description="Grid-search OMR parameters against reviewed ground truth.")
    parser.add_argument("--ground-truth", default="data/ground_truth_review.csv")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts")
    parser.add_argument("--report-json", default="data/tuning_report.json")
    args = parser.parse_args()

    rows = load_ground_truth_csv(args.ground_truth)
    dataset = build_tuning_dataset(rows, Path(args.artifacts_dir))
    candidates = []

    for fill_weight in (0.4, 0.5, 0.6, 0.7):
        for ink_weight in (0.3, 0.4, 0.5):
            for empty_score_threshold in (0.04, 0.05, 0.06, 0.08, 0.1):
                for second_ratio_threshold in (0.5, 0.55, 0.6, 0.65):
                    for third_ratio_threshold in (0.5, 0.55, 0.6, 0.65):
                        config = OMRConfig(
                            fill_weight=fill_weight,
                            ink_weight=ink_weight,
                            empty_score_threshold=empty_score_threshold,
                            second_ratio_threshold=second_ratio_threshold,
                            third_ratio_threshold=third_ratio_threshold,
                        )
                        metrics = score_config(dataset, config)
                        candidates.append(
                            {
                                "config": {
                                    "fill_weight": fill_weight,
                                    "ink_weight": ink_weight,
                                    "empty_score_threshold": empty_score_threshold,
                                    "second_ratio_threshold": second_ratio_threshold,
                                    "third_ratio_threshold": third_ratio_threshold,
                                },
                                **metrics,
                            }
                        )
                        print(
                            f"fill={fill_weight:.2f} ink={ink_weight:.2f} empty={empty_score_threshold:.2f} "
                            f"second={second_ratio_threshold:.2f} third={third_ratio_threshold:.2f} "
                            f"acc={metrics['answer_accuracy']:.4f} exact={metrics['exact_sheet_match']:.4f}"
                        )

    candidates.sort(key=lambda item: (item["answer_accuracy"], item["exact_sheet_match"]), reverse=True)
    report = {
        "best": candidates[0] if candidates else None,
        "candidate_count": len(candidates),
        "candidates": candidates[:10],
    }
    Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["best"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
