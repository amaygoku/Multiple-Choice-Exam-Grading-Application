import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


DEFAULT_IMAGE_DIRS = [
    project_root / "v2_test_results" / "data_v2" / "evaluation_data",
    project_root / "v2_test_results" / "data_test",
]
DEFAULT_GROUND_TRUTH = project_root / "v2_test_results" / "data_test" / "ground_truth.csv"
DEFAULT_REPORT_PATH = project_root / "v2_test_results" / "evaluation_report.json"
DEFAULT_RESULT_DIR = project_root / "v2_test_results" / "evaluation_result_omr"
DEFAULT_MATRIX_DIR = project_root / "v2_test_results" / "evaluation_matrices"


def _normalize_row(row):
    normalized = {}
    for key, value in row.items():
        normalized[(key or "").strip()] = (value or "").strip()
    return normalized


def _read_ground_truth_by_mssv(csv_path):
    ground_truth_by_mssv = {}
    duplicate_mssv = defaultdict(int)

    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = _normalize_row(row)
            mssv = row.get("MSSV", "")
            if not mssv:
                continue

            answers = []
            for q_idx in range(1, 46):
                answers.append(row.get(f"Q{q_idx}", "").strip().upper())

            if mssv in ground_truth_by_mssv:
                duplicate_mssv[mssv] += 1

            ground_truth_by_mssv[mssv] = {
                "file_name": row.get("File Name", ""),
                "mssv": mssv,
                "ma_de": row.get("Ma De", ""),
                "answers": answers,
            }

    return ground_truth_by_mssv, duplicate_mssv


def _collect_image_paths(image_dirs):
    image_entries = []
    for image_dir in image_dirs:
        folder = Path(image_dir)
        if not folder.exists():
            print(f"[WARNING] Image folder not found: {folder}")
            continue

        for image_path in sorted(folder.iterdir()):
            if image_path.is_file() and image_path.suffix.lower() in (".jpg", ".jpeg", ".png"):
                image_entries.append((folder, image_path))

    return image_entries


def _split_answer_tokens(answer_text):
    if not answer_text:
        return set()
    return {char for char in answer_text.strip().upper().replace(" ", "") if char in {"A", "B", "C", "D"}}


def _rate(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _evaluate_sheet(image_path, result_root, config):
    import cv2

    from crop import crop_regions_image
    from detect_paper import align_document_image
    from extract_code import analyze_id_and_code_image, render_id_code_debug_image
    from preprocessing_crop import preprocess_text_crop_images
    from omr_pipeline import process_omr_image

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path.name}")

    stem = image_path.stem
    folder_name = image_path.parent.name
    img_output_dir = result_root / folder_name / stem
    img_output_dir.mkdir(parents=True, exist_ok=True)

    crops_dir = img_output_dir / "crops"
    crops_dir.mkdir(exist_ok=True)
    omr_grids_dir = img_output_dir / "omr_grids"
    omr_grids_dir.mkdir(exist_ok=True)
    preprocess_dir = img_output_dir / "preprocess"
    preprocess_dir.mkdir(exist_ok=True)

    cv2.imwrite(str(img_output_dir / "01_original.jpg"), image)

    aligned = align_document_image(image)
    if aligned is None:
        raise ValueError("Could not detect or align the answer sheet.")
    cv2.imwrite(str(img_output_dir / "02_aligned.png"), aligned)

    visualized, crops = crop_regions_image(aligned, layout_version="v2")
    if visualized is None or not crops:
        raise ValueError("Could not crop answer sheet regions.")
    cv2.imwrite(str(img_output_dir / "03_visualized_boxes.png"), visualized)

    for name, crop_img in crops.items():
        if crop_img is not None:
            cv2.imwrite(str(crops_dir / f"{name}.png"), crop_img)

    crops = preprocess_text_crop_images(crops)
    for name in ("ho_va_ten_refined", "lop_refined", "mon_refined"):
        if name in crops and crops[name] is not None:
            cv2.imwrite(str(crops_dir / f"{name}.png"), crops[name])

    mssv_analysis = analyze_id_and_code_image(crops.get("mssv"), num_cols=8, use_classifier=False)
    pred_mssv = mssv_analysis["prediction"]

    mssv_grid = render_id_code_debug_image(mssv_analysis["normalized_gray"], mssv_analysis, num_cols=8)
    if mssv_grid is not None:
        cv2.imwrite(str(omr_grids_dir / "mssv_grid.png"), mssv_grid)
    if mssv_analysis["normalized_gray"] is not None:
        cv2.imwrite(str(preprocess_dir / "mssv_gray.png"), mssv_analysis["normalized_gray"])
    if mssv_analysis["normalized_thresh"] is not None:
        cv2.imwrite(str(preprocess_dir / "mssv_thresholded.png"), mssv_analysis["normalized_thresh"])

    made_analysis = analyze_id_and_code_image(crops.get("ma_de"), num_cols=3, use_classifier=False)
    pred_made = made_analysis["prediction"]

    made_grid = render_id_code_debug_image(made_analysis["normalized_gray"], made_analysis, num_cols=3)
    if made_grid is not None:
        cv2.imwrite(str(omr_grids_dir / "ma_de_grid.png"), made_grid)
    if made_analysis["normalized_gray"] is not None:
        cv2.imwrite(str(preprocess_dir / "ma_de_gray.png"), made_analysis["normalized_gray"])
    if made_analysis["normalized_thresh"] is not None:
        cv2.imwrite(str(preprocess_dir / "ma_de_thresholded.png"), made_analysis["normalized_thresh"])

    pred_answers = []
    for crop_name in ("answer_1", "answer_2", "answer_3"):
        preproc_debug = {}
        detected, result_image = process_omr_image(
            crops.get(crop_name),
            start_question_idx=len(pred_answers) + 1,
            config=config,
            use_classifier=False,
            preproc_debug=preproc_debug,
        )
        if detected:
            pred_answers.extend(detected)

        if result_image is not None:
            cv2.imwrite(str(omr_grids_dir / f"{crop_name}_grid.png"), result_image)

        for step_name, img_step in preproc_debug.items():
            if img_step is not None:
                cv2.imwrite(str(preprocess_dir / f"{crop_name}_{step_name}.png"), img_step)

    if len(pred_answers) < 45:
        pred_answers += [""] * (45 - len(pred_answers))
    elif len(pred_answers) > 45:
        pred_answers = pred_answers[:45]

    return {
        "pred_mssv": pred_mssv,
        "pred_made": pred_made,
        "pred_answers": pred_answers,
        "output_dir": str(img_output_dir),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate OMR results using MSSV-based ground truth lookup.")
    parser.add_argument(
        "--image-dirs",
        nargs="+",
        default=[str(path) for path in DEFAULT_IMAGE_DIRS],
        help="One or more folders containing evaluation images.",
    )
    parser.add_argument(
        "--ground-truth",
        default=str(DEFAULT_GROUND_TRUTH),
        help="CSV file containing MSSV and answer ground truth.",
    )
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help="Where to write the evaluation summary JSON.",
    )
    parser.add_argument(
        "--result-dir",
        default=str(DEFAULT_RESULT_DIR),
        help="Where to store per-sheet debug artifacts.",
    )
    parser.add_argument(
        "--matrix-dir",
        default=str(DEFAULT_MATRIX_DIR),
        help="Where to write report-ready CSV matrices.",
    )
    args = parser.parse_args()

    from omr_pipeline import OMR_CONFIG_V2

    result_root = Path(args.result_dir)
    result_root.mkdir(parents=True, exist_ok=True)

    mssv_gt, duplicate_mssv = _read_ground_truth_by_mssv(args.ground_truth)
    print(f"[INFO] Loaded ground truth answers for {len(mssv_gt)} MSSVs from {args.ground_truth}.")
    if duplicate_mssv:
        print(f"[WARNING] Found {len(duplicate_mssv)} duplicate MSSV entries in ground truth. Last occurrence wins.")

    image_entries = _collect_image_paths(args.image_dirs)
    if not image_entries:
        print("[ERROR] No evaluation images found.")
        return

    print(f"[INFO] Found {len(image_entries)} images across {len(args.image_dirs)} folders.")

    totals_by_folder = defaultdict(lambda: {
        "total_sheets": 0,
        "correct_mssvs": 0,
        "exact_matches": 0,
        "total_answers": 0,
        "correct_answers": 0,
        "mssv_not_found": 0,
        "failed_sheets": 0,
    })
    question_stats = [
        {
            "question": q_idx,
            "total": 0,
            "exact_correct": 0,
            "partial_overlap": 0,
            "wrong": 0,
            "skipped": 0,
        }
        for q_idx in range(1, 46)
    ]
    bubble_stats = {
        choice: {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
        for choice in ("A", "B", "C", "D")
    }
    overall = {
        "total_sheets": 0,
        "correct_mssvs": 0,
        "exact_matches": 0,
        "total_answers": 0,
        "correct_answers": 0,
        "mssv_not_found": 0,
        "failed_sheets": 0,
    }
    details = []
    sheet_rows = []

    for idx, (source_folder, img_path) in enumerate(image_entries, start=1):
        print(f"[{idx}/{len(image_entries)}] Processing {source_folder.name}/{img_path.name}...")
        folder_key = source_folder.name
        stats = totals_by_folder[folder_key]
        stats["total_sheets"] += 1
        overall["total_sheets"] += 1

        try:
            sheet_result = _evaluate_sheet(img_path, result_root, OMR_CONFIG_V2)
            pred_mssv = sheet_result["pred_mssv"]
            pred_made = sheet_result["pred_made"]
            pred_answers = sheet_result["pred_answers"]

            gt_row = mssv_gt.get(pred_mssv)
            mssv_found = gt_row is not None

            row_correct_answers = 0
            is_exact = False
            true_answers = None

            if mssv_found:
                true_answers = gt_row["answers"]
                stats["correct_mssvs"] += 1
                overall["correct_mssvs"] += 1

                for q_idx in range(45):
                    truth = true_answers[q_idx]
                    pred = pred_answers[q_idx]
                    question_item = question_stats[q_idx]
                    question_item["total"] += 1

                    truth_set = _split_answer_tokens(truth)
                    pred_set = _split_answer_tokens(pred)

                    if pred == truth:
                        row_correct_answers += 1
                        question_item["exact_correct"] += 1
                    elif truth_set & pred_set:
                        question_item["partial_overlap"] += 1
                    else:
                        question_item["wrong"] += 1

                    if not truth_set and not pred_set:
                        question_item["skipped"] += 1

                    for choice in ("A", "B", "C", "D"):
                        truth_has = choice in truth_set
                        pred_has = choice in pred_set
                        if truth_has and pred_has:
                            bubble_stats[choice]["TP"] += 1
                        elif truth_has and not pred_has:
                            bubble_stats[choice]["FN"] += 1
                        elif not truth_has and pred_has:
                            bubble_stats[choice]["FP"] += 1
                        else:
                            bubble_stats[choice]["TN"] += 1

                stats["total_answers"] += 45
                stats["correct_answers"] += row_correct_answers
                overall["total_answers"] += 45
                overall["correct_answers"] += row_correct_answers

                is_exact = pred_answers == true_answers
                if is_exact:
                    stats["exact_matches"] += 1
                    overall["exact_matches"] += 1
            else:
                stats["mssv_not_found"] += 1
                overall["mssv_not_found"] += 1
                print(f"  [WARNING] Predicted MSSV '{pred_mssv}' not found in ground truth.")
                sheet_rows.append(
                    {
                        "source_folder": folder_key,
                        "image": img_path.name,
                        "pred_mssv": pred_mssv,
                        "true_mssv": "",
                        "mssv_found": False,
                        "pred_made": pred_made,
                        "correct_answers": 0,
                        "total_answers": 0,
                        "answer_accuracy": 0.0,
                        "exact_match": False,
                        "output_dir": sheet_result["output_dir"],
                    }
                )

            details.append(
                {
                    "source_folder": folder_key,
                    "image": img_path.name,
                    "pred_mssv": pred_mssv,
                    "pred_made": pred_made,
                    "mssv_found": mssv_found,
                    "pred_answers": pred_answers,
                    "true_mssv": gt_row["mssv"] if mssv_found else None,
                    "true_answers": true_answers,
                    "correct_answers": row_correct_answers if mssv_found else 0,
                    "exact_match": is_exact,
                    "output_dir": sheet_result["output_dir"],
                }
            )
            if mssv_found:
                sheet_rows.append(
                    {
                        "source_folder": folder_key,
                        "image": img_path.name,
                        "pred_mssv": pred_mssv,
                        "true_mssv": gt_row["mssv"],
                        "mssv_found": True,
                        "pred_made": pred_made,
                        "correct_answers": row_correct_answers,
                        "total_answers": 45,
                        "answer_accuracy": _rate(row_correct_answers, 45),
                        "exact_match": is_exact,
                        "output_dir": sheet_result["output_dir"],
                    }
                )

            print(
                f"  MSSV: {pred_mssv}, Ma De: {pred_made}, "
                f"Correct: {row_correct_answers}/45, Exact Match: {is_exact}"
            )

        except Exception as exc:
            stats["failed_sheets"] += 1
            overall["failed_sheets"] += 1
            print(f"  [ERROR] Failed to process sheet {img_path.name}: {exc}")
            details.append(
                {
                    "source_folder": folder_key,
                    "image": img_path.name,
                    "error": str(exc),
                }
            )

    folder_reports = {}
    for folder_name, stats in totals_by_folder.items():
        folder_reports[folder_name] = {
            **stats,
            "mssv_accuracy": _rate(stats["correct_mssvs"], stats["total_sheets"]),
            "exact_sheet_match": _rate(stats["exact_matches"], stats["total_sheets"]),
            "answer_accuracy": _rate(stats["correct_answers"], stats["total_answers"]),
        }

    question_rows = []
    for item in question_stats:
        question_rows.append(
            {
                **item,
                "accuracy": _rate(item["exact_correct"], item["total"]),
            }
        )

    bubble_rows = []
    for choice, stats in bubble_stats.items():
        precision = _rate(stats["TP"], stats["TP"] + stats["FP"])
        recall = _rate(stats["TP"], stats["TP"] + stats["FN"])
        f1 = _rate(2 * precision * recall, precision + recall) if (precision + recall) else 0.0
        accuracy = _rate(stats["TP"] + stats["TN"], stats["TP"] + stats["TN"] + stats["FP"] + stats["FN"])
        bubble_rows.append(
            {
                "choice": choice,
                **stats,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "accuracy": accuracy,
            }
        )

    summary = {
        "image_dirs": [str(Path(path)) for path in args.image_dirs],
        "ground_truth": str(Path(args.ground_truth)),
        "total_sheets": overall["total_sheets"],
        "correct_mssvs": overall["correct_mssvs"],
        "mssv_accuracy": _rate(overall["correct_mssvs"], overall["total_sheets"]),
        "exact_matches": overall["exact_matches"],
        "exact_sheet_match": _rate(overall["exact_matches"], overall["total_sheets"]),
        "total_answers_evaluated": overall["total_answers"],
        "correct_answers": overall["correct_answers"],
        "answer_accuracy": _rate(overall["correct_answers"], overall["total_answers"]),
        "mssv_not_found": overall["mssv_not_found"],
        "failed_sheets": overall["failed_sheets"],
        "by_folder": folder_reports,
        "details": details,
    }

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    matrix_dir = Path(args.matrix_dir)
    matrix_dir.mkdir(parents=True, exist_ok=True)

    with (matrix_dir / "question_metrics.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["question", "total", "exact_correct", "partial_overlap", "wrong", "skipped", "accuracy"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in question_rows:
            writer.writerow({key: row[key] for key in fieldnames})

    with (matrix_dir / "bubble_confusion_matrix.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["choice", "TP", "FP", "FN", "TN", "precision", "recall", "f1", "accuracy"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in bubble_rows:
            writer.writerow({key: row[key] for key in fieldnames})

    with (matrix_dir / "sheet_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "source_folder",
            "image",
            "pred_mssv",
            "true_mssv",
            "mssv_found",
            "pred_made",
            "correct_answers",
            "total_answers",
            "answer_accuracy",
            "exact_match",
            "output_dir",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sheet_rows:
            writer.writerow({key: row[key] for key in fieldnames})

    print("\n" + "=" * 50)
    print(" EVALUATION SUMMARY FOR V2 DATA")
    print("=" * 50)
    print(f"Image folders: {', '.join(args.image_dirs)}")
    print(f"Ground truth: {args.ground_truth}")
    print(f"Total Sheets Evaluated: {overall['total_sheets']}")
    print(f"MSSV Prediction Accuracy: {summary['mssv_accuracy'] * 100:.2f}% ({overall['correct_mssvs']}/{overall['total_sheets']})")
    print(f"Exact Sheet Match Rate: {summary['exact_sheet_match'] * 100:.2f}% ({overall['exact_matches']}/{overall['total_sheets']})")
    print(f"Answer Level Accuracy (on matched MSSV): {summary['answer_accuracy'] * 100:.2f}% ({overall['correct_answers']}/{overall['total_answers']})")
    print(f"MSSV not found: {overall['mssv_not_found']}")
    print(f"Failed sheets: {overall['failed_sheets']}")
    print(f"Detailed debug folder: {result_root}")
    print(f"Detailed report saved to: {report_path}")
    print(f"Report tables saved to: {matrix_dir}")
    print("=" * 50)


if __name__ == "__main__":
    main()
