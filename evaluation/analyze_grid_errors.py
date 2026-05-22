import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omr_pipeline import DEFAULT_OMR_CONFIG, pick_bubbled_indices, prepare_omr_canvas


CHOICES = ["A", "B", "C", "D", "E", "F"]


def load_eval_rows(report_json):
    data = json.loads(Path(report_json).read_text(encoding="utf-8"))
    return data.get("details", [])


def compute_row_metrics(answer_crop_path, row_idx, config):
    image = cv2.imread(str(answer_crop_path))
    if image is None:
        raise ValueError(f"Could not read: {answer_crop_path}")

    _, thresh, _ = prepare_omr_canvas(image, config)

    crop_t = thresh[
        config.crop_pad_top : thresh.shape[0] - config.crop_pad_bottom,
        config.crop_pad_left : thresh.shape[1] - config.crop_pad_right,
    ]
    row_height = crop_t.shape[0] / config.num_rows
    start_x = int(crop_t.shape[1] * config.q_col_ratio)
    cell_width = (crop_t.shape[1] - start_x) / config.num_choices

    all_tots = []
    for row in range(config.num_rows):
        tots = []
        for col in range(config.num_choices):
            y1 = int(row * row_height) + config.cell_pad_top
            y2 = int((row + 1) * row_height) - config.cell_pad_bottom
            x1 = start_x + int(col * cell_width) + config.cell_pad_left
            x2 = start_x + int((col + 1) * cell_width) - config.cell_pad_right
            cell = crop_t[y1:y2, x1:x2]
            tots.append(int(cv2.countNonZero(cell)))
        all_tots.append(tots)

    col_baselines = []
    for col in range(config.num_choices):
        col_vals = sorted(all_tots[row][col] for row in range(config.num_rows))
        col_baselines.append(col_vals[len(col_vals) // 2])

    counts = all_tots[row_idx]
    picked_indices, row_min, ranked_scores = pick_bubbled_indices(counts, col_baselines, config)
    score_by_idx = {item["idx"]: item for item in ranked_scores}
    per_choice = []
    picked = [CHOICES[idx] for idx in picked_indices]
    for idx, value in enumerate(counts):
        item = score_by_idx[idx]
        per_choice.append(
            {
                "choice": CHOICES[idx],
                "count": value,
                "col_baseline": col_baselines[idx],
                "delta_row_min": value - row_min,
                "row_signal": item["row_signal"],
                "col_signal": item["col_signal"],
                "score": item["score"],
                "picked": idx in picked_indices,
            }
        )
    return {
        "picked": "".join(picked),
        "counts": counts,
        "row_min": row_min,
        "per_choice": per_choice,
        "col_baselines": col_baselines,
    }


def analyze(report_json, artifacts_dir):
    config = DEFAULT_OMR_CONFIG
    rows = load_eval_rows(report_json)

    mismatch_rows = []
    reason_counter = Counter()
    choice_false_positive = Counter()
    choice_missed = Counter()
    image_error_counter = Counter()

    for row in rows:
        image_name = row["image"]
        pred_answers = row["pred_answers"]
        true_answers = row["true_answers"]
        image_stem = Path(image_name).stem

        for q_idx, (pred, truth) in enumerate(zip(pred_answers, true_answers), start=1):
            if pred == truth:
                continue

            image_error_counter[image_name] += 1
            crop_idx = (q_idx - 1) // config.num_rows + 1
            row_idx = (q_idx - 1) % config.num_rows
            crop_path = Path(artifacts_dir) / image_stem / "crops" / f"answer_{crop_idx}.png"
            metrics = compute_row_metrics(crop_path, row_idx, config)

            pred_set = set(pred)
            truth_set = set(truth)
            fp = sorted(pred_set - truth_set)
            fn = sorted(truth_set - pred_set)

            if fp and fn:
                reason = "mixed_fp_fn"
            elif fp:
                reason = "false_positive"
            elif fn:
                reason = "missed_mark"
            else:
                reason = "other_mismatch"
            reason_counter[reason] += 1

            for ch in fp:
                choice_false_positive[ch] += 1
            for ch in fn:
                choice_missed[ch] += 1

            mismatch_rows.append(
                {
                    "image": image_name,
                    "question": q_idx,
                    "crop": f"answer_{crop_idx}.png",
                    "truth": truth,
                    "pred": pred,
                    "false_positive_choices": fp,
                    "missed_choices": fn,
                    "reason": reason,
                    "picked_by_rules": metrics["picked"],
                    "counts": dict(zip(CHOICES[: config.num_choices], metrics["counts"])),
                    "col_baselines": dict(zip(CHOICES[: config.num_choices], metrics["col_baselines"])),
                    "per_choice": metrics["per_choice"],
                }
            )

    summary = {
        "total_mismatched_questions": len(mismatch_rows),
        "reason_distribution": dict(reason_counter),
        "false_positive_choice_distribution": dict(choice_false_positive),
        "missed_choice_distribution": dict(choice_missed),
        "top_error_images": image_error_counter.most_common(10),
    }
    return summary, mismatch_rows


def main():
    parser = argparse.ArgumentParser(description="Analyze grid OMR mismatch reasons over full eval report.")
    parser.add_argument("--report-json", default="data/eval_report.json")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts")
    parser.add_argument("--output-json", default="data/grid_error_analysis.json")
    args = parser.parse_args()

    summary, mismatch_rows = analyze(args.report_json, args.artifacts_dir)
    output = {
        "summary": summary,
        "mismatches": mismatch_rows,
    }
    Path(args.output_json).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
