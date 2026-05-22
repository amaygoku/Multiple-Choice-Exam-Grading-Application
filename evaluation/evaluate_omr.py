import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.omr_eval_lib import load_ground_truth_csv, process_sheet_image


def normalize_answers(value):
    if not value:
        return []
    return [token.strip().upper() for token in value.split(",")]


def main():
    parser = argparse.ArgumentParser(description="Evaluate OMR predictions against reviewed ground truth.")
    parser.add_argument("--ground-truth", default="data/ground_truth_review.csv")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--report-json", default="data/eval_report.json")
    args = parser.parse_args()

    rows = load_ground_truth_csv(args.ground_truth)
    data_dir = Path(args.data_dir)
    report_rows = []
    total_sheets = 0
    exact_match = 0
    mssv_correct = 0
    made_correct = 0
    total_answer_slots = 0
    answer_correct = 0

    for row in rows:
        if not row.get("true_answers"):
            continue
        total_sheets += 1
        prediction = process_sheet_image(data_dir / row["image"])
        true_answers = normalize_answers(row["true_answers"])
        pred_answers = prediction["answers"]
        max_len = max(len(true_answers), len(pred_answers))
        row_correct = 0
        for idx in range(max_len):
            truth = true_answers[idx] if idx < len(true_answers) else ""
            pred = pred_answers[idx] if idx < len(pred_answers) else ""
            if truth == pred:
                row_correct += 1
        total_answer_slots += max_len
        answer_correct += row_correct

        pred_mssv = prediction["student_info"]["mssv"]
        pred_made = prediction["student_info"]["ma_de"]
        true_mssv = (row.get("true_mssv") or "").strip()
        true_made = (row.get("true_ma_de") or "").strip()
        if true_mssv and pred_mssv == true_mssv:
            mssv_correct += 1
        if true_made and pred_made == true_made:
            made_correct += 1
        if true_answers == pred_answers:
            exact_match += 1

        report_rows.append(
            {
                "image": row["image"],
                "pred_mssv": pred_mssv,
                "true_mssv": true_mssv,
                "pred_ma_de": pred_made,
                "true_ma_de": true_made,
                "pred_answers": pred_answers,
                "true_answers": true_answers,
                "answer_correct": row_correct,
                "answer_total": max_len,
            }
        )

    summary = {
        "total_sheets": total_sheets,
        "mssv_accuracy": (mssv_correct / total_sheets) if total_sheets else 0.0,
        "ma_de_accuracy": (made_correct / total_sheets) if total_sheets else 0.0,
        "answer_accuracy": (answer_correct / total_answer_slots) if total_answer_slots else 0.0,
        "exact_sheet_match": (exact_match / total_sheets) if total_sheets else 0.0,
        "details": report_rows,
    }

    Path(args.report_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
