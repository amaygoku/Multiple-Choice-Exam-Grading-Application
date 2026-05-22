import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.omr_eval_lib import process_sheet_image, write_bootstrap_files


def main():
    parser = argparse.ArgumentParser(description="Bootstrap OMR labels from a folder of sheet images.")
    parser.add_argument("--data-dir", default="data", help="Folder containing sheet images")
    parser.add_argument("--artifacts-dir", default="data/eval_artifacts", help="Where to save debug artifacts")
    parser.add_argument("--jsonl", default="data/bootstrap_predictions.jsonl", help="Bootstrap JSONL output")
    parser.add_argument("--csv", default="data/ground_truth_review.csv", help="CSV to review/fill true labels")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    image_paths = sorted([p for p in data_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    records = []

    for image_path in image_paths:
        artifact_dir = Path(args.artifacts_dir) / image_path.stem
        record = process_sheet_image(image_path, output_dir=artifact_dir)
        records.append(record)
        print(f"Processed {image_path.name}: mssv={record['student_info']['mssv']} ma_de={record['student_info']['ma_de']} answers={record['answer_count']}")

    write_bootstrap_files(records, args.jsonl, args.csv)
    print(f"Wrote {len(records)} records to {args.jsonl}")
    print(f"Wrote review CSV to {args.csv}")


if __name__ == "__main__":
    main()
