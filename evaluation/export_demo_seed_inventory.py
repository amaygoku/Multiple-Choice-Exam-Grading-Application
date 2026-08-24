from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2

from backend.core.config import ensure_runtime_dirs
from backend.services.exam_pipeline import run_exam_pipeline

SOURCE_DIRS = [
    PROJECT_ROOT / "v2_test_results" / "data_test",
    PROJECT_ROOT / "v2_test_results" / "data_v2" / "evaluation_data",
]
OUTPUT_DIR = PROJECT_ROOT / "results" / "demo_seed_inventory"


def iter_images() -> Iterable[tuple[str, Path]]:
    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            continue
        for image_path in sorted(source_dir.glob("*.jpg")):
            yield source_dir.name, image_path


def normalize_answers(answers: list[str] | None) -> str:
    if not answers:
        return ""
    return "|".join(str(item).strip() for item in answers)


def main() -> None:
    ensure_runtime_dirs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []
    grouped_by_mssv: dict[str, list[dict[str, str]]] = defaultdict(list)

    image_entries = list(iter_images())
    print(f"[INFO] Found {len(image_entries)} images.")

    for index, (source_name, image_path) in enumerate(image_entries, start=1):
        print(f"[{index}/{len(image_entries)}] Processing {source_name}/{image_path.name}")
        image = cv2.imread(str(image_path))
        if image is None:
            row = {
                "source_folder": source_name,
                "image_name": image_path.name,
                "image_path": str(image_path),
                "status": "failed_read",
                "mssv": "",
                "ma_de": "",
                "ocr_name": "",
                "answers": "",
                "answer_count": "0",
                "source_image_url": "",
                "aligned_image_url": "",
                "result_image_url": "",
                "name_crop_url": "",
                "mssv_crop_url": "",
                "made_crop_url": "",
                "omr_answer_1_url": "",
                "omr_answer_2_url": "",
                "omr_answer_3_url": "",
                "duplicate_count": "",
                "duplicate_images": "",
            }
            all_rows.append(row)
            continue

        try:
            result = run_exam_pipeline(
                image,
                correct_answers="",
                debug_artifacts=True,
                use_classifier=True,
                layout_version="v2",
            )
            student_info = result.get("student_info") or {}
            crops = result.get("crops") or {}
            omr_images = result.get("omr_images") or {}
            answers = result.get("answers") or []

            row = {
                "source_folder": source_name,
                "image_name": image_path.name,
                "image_path": str(image_path),
                "status": "success",
                "mssv": str(student_info.get("mssv") or "").strip(),
                "ma_de": str(student_info.get("ma_de") or "").strip(),
                "ocr_name": str(student_info.get("name") or "").strip(),
                "answers": normalize_answers(answers),
                "answer_count": str(len(answers)),
                "source_image_url": str(result.get("source_image_url") or ""),
                "aligned_image_url": str(result.get("aligned_image_url") or ""),
                "result_image_url": str(result.get("result_image_url") or ""),
                "name_crop_url": str(crops.get("ho_va_ten") or ""),
                "mssv_crop_url": str(crops.get("mssv") or ""),
                "made_crop_url": str(crops.get("ma_de") or ""),
                "omr_answer_1_url": str(omr_images.get("answer_1") or ""),
                "omr_answer_2_url": str(omr_images.get("answer_2") or ""),
                "omr_answer_3_url": str(omr_images.get("answer_3") or ""),
                "duplicate_count": "",
                "duplicate_images": "",
            }
        except Exception as exc:  # pragma: no cover - utility script
            row = {
                "source_folder": source_name,
                "image_name": image_path.name,
                "image_path": str(image_path),
                "status": f"failed: {exc}",
                "mssv": "",
                "ma_de": "",
                "ocr_name": "",
                "answers": "",
                "answer_count": "0",
                "source_image_url": "",
                "aligned_image_url": "",
                "result_image_url": "",
                "name_crop_url": "",
                "mssv_crop_url": "",
                "made_crop_url": "",
                "omr_answer_1_url": "",
                "omr_answer_2_url": "",
                "omr_answer_3_url": "",
                "duplicate_count": "",
                "duplicate_images": "",
            }

        all_rows.append(row)
        key = row["mssv"].strip()
        if key:
            grouped_by_mssv[key].append(row)

    for row in all_rows:
        key = row["mssv"].strip()
        if not key:
            row["duplicate_count"] = "1"
            row["duplicate_images"] = row["image_name"]
            continue
        dup_rows = grouped_by_mssv[key]
        row["duplicate_count"] = str(len(dup_rows))
        row["duplicate_images"] = "|".join(item["image_name"] for item in dup_rows)

    dedup_rows: list[dict[str, str]] = []
    for row in all_rows:
        key = row["mssv"].strip()
        if not key:
            continue
        if grouped_by_mssv[key][0] is row:
            dedup_rows.append(row)

    duplicate_summary_rows = []
    for mssv, rows in sorted(grouped_by_mssv.items()):
        duplicate_summary_rows.append(
            {
                "mssv": mssv,
                "duplicate_count": str(len(rows)),
                "image_names": "|".join(item["image_name"] for item in rows),
                "source_folders": "|".join(item["source_folder"] for item in rows),
                "ocr_names": "|".join(item["ocr_name"] for item in rows),
                "ma_de_values": "|".join(item["ma_de"] for item in rows),
            }
        )

    fieldnames = [
        "source_folder",
        "image_name",
        "image_path",
        "status",
        "mssv",
        "ma_de",
        "ocr_name",
        "answers",
        "answer_count",
        "source_image_url",
        "aligned_image_url",
        "result_image_url",
        "name_crop_url",
        "mssv_crop_url",
        "made_crop_url",
        "omr_answer_1_url",
        "omr_answer_2_url",
        "omr_answer_3_url",
        "duplicate_count",
        "duplicate_images",
    ]

    with (OUTPUT_DIR / "all_records.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    with (OUTPUT_DIR / "dedup_by_mssv.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dedup_rows)

    with (OUTPUT_DIR / "duplicate_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames_dup = [
            "mssv",
            "duplicate_count",
            "image_names",
            "source_folders",
            "ocr_names",
            "ma_de_values",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames_dup)
        writer.writeheader()
        writer.writerows(duplicate_summary_rows)

    print(f"[DONE] Wrote {len(all_rows)} rows to {OUTPUT_DIR / 'all_records.csv'}")
    print(f"[DONE] Wrote {len(dedup_rows)} deduplicated rows to {OUTPUT_DIR / 'dedup_by_mssv.csv'}")
    print(f"[DONE] Wrote {len(duplicate_summary_rows)} duplicate summary rows to {OUTPUT_DIR / 'duplicate_summary.csv'}")


if __name__ == "__main__":
    main()
