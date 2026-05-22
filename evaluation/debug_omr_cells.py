import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omr_pipeline import DEFAULT_OMR_CONFIG, pick_bubbled_indices, prepare_omr_canvas


CHOICES = ["A", "B", "C", "D", "E", "F"]


def parse_questions(raw):
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def load_answer_crop(artifact_dir, question_number):
    crop_idx = (question_number - 1) // DEFAULT_OMR_CONFIG.num_rows + 1
    crop_path = artifact_dir / "crops" / f"answer_{crop_idx}.png"
    image = cv2.imread(str(crop_path))
    if image is None:
        raise ValueError(f"Could not read crop: {crop_path}")
    return image, crop_idx


def compute_debug_row(image, question_number, config):
    row_idx = (question_number - 1) % config.num_rows
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
    details = []
    picked = [CHOICES[idx] for idx in picked_indices]
    for idx, value in enumerate(counts):
        item = score_by_idx[idx]
        details.append(
            {
                "choice": CHOICES[idx],
                "count": value,
                "vs_row_min": value - row_min,
                "col_baseline": col_baselines[idx],
                "row_signal": item["row_signal"],
                "col_signal": item["col_signal"],
                "score": item["score"],
                "picked": idx in picked_indices,
            }
        )

    return {
        "question": question_number,
        "row_index_in_crop": row_idx + 1,
        "counts": dict(zip(CHOICES[: config.num_choices], counts)),
        "row_min": row_min,
        "picked": "".join(picked),
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect OMR cell counts and rule decisions for selected questions.")
    parser.add_argument("artifact_dir", help="Path to one eval_artifacts/<image_stem> directory")
    parser.add_argument("--questions", required=True, help="Comma-separated question numbers, e.g. 1,2,12,31")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir)
    config = DEFAULT_OMR_CONFIG
    results = []

    for question_number in parse_questions(args.questions):
        image, crop_idx = load_answer_crop(artifact_dir, question_number)
        row_debug = compute_debug_row(image, question_number, config)
        row_debug["crop"] = f"answer_{crop_idx}.png"
        results.append(row_debug)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
