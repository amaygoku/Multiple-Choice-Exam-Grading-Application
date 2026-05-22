import argparse
import csv
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extract_code import analyze_id_and_code_image, render_id_code_debug_image


def main():
    parser = argparse.ArgumentParser(description="Export MSSV and ma_de debug images and metrics.")
    parser.add_argument("--ground-truth", default="data/ground_truth_review.csv")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts")
    parser.add_argument("--output-dir", default="data/id_code_debug")
    parser.add_argument("--summary-json", default="data/id_code_debug/summary.json")
    parser.add_argument("--summary-csv", default="data/id_code_debug/summary.csv")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    with Path(args.ground_truth).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_name = (row.get("image") or "").strip()
            if not image_name:
                continue

            stem = Path(image_name).stem
            image_output_dir = output_dir / stem
            image_output_dir.mkdir(parents=True, exist_ok=True)
            crop_dir = Path(args.artifacts_dir) / stem / "crops"

            for field_name, num_cols, truth_key in (("mssv", 8, "true_mssv"), ("ma_de", 3, "true_ma_de")):
                crop_path = crop_dir / f"{field_name}.png"
                image = cv2.imread(str(crop_path))
                analysis = analyze_id_and_code_image(image, num_cols)
                debug_image = render_id_code_debug_image(analysis["normalized_gray"], analysis, num_cols)
                if debug_image is not None:
                    cv2.imwrite(str(image_output_dir / f"{field_name}_debug.png"), debug_image)

                summary.append(
                    {
                        "image": image_name,
                        "field": field_name,
                        "truth": (row.get(truth_key) or "").strip(),
                        "pred": analysis["prediction"],
                        "correct": analysis["prediction"] == (row.get(truth_key) or "").strip(),
                        "crop_path": str(crop_path),
                        "debug_path": str(image_output_dir / f"{field_name}_debug.png"),
                        "columns": analysis["columns"],
                    }
                )

    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with Path(args.summary_csv).open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["image", "field", "truth", "pred", "correct", "crop_path", "debug_path"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary:
            writer.writerow({key: row[key] for key in fieldnames})

    print(f"Exported {len(summary)} records to {output_dir}")


if __name__ == "__main__":
    main()
