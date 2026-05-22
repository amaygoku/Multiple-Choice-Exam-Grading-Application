import argparse
import csv
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path


TASK_CONFIGS = {
    "answer_binary": {"fields": {"answer"}, "negative_ratio": 2.0},
    "id_binary": {"fields": {"mssv", "ma_de"}, "negative_ratio": 3.0},
    "mssv_binary": {"fields": {"mssv"}, "negative_ratio": 3.0},
    "ma_de_binary": {"fields": {"ma_de"}, "negative_ratio": 3.0},
}

CLASS_NAMES = {"1": "filled", "0": "empty"}


def load_manifest(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_images(image_names, val_ratio, test_ratio, seed):
    image_names = sorted(set(image_names))
    rng = random.Random(seed)
    rng.shuffle(image_names)

    n = len(image_names)
    n_test = int(round(n * test_ratio))
    n_val = int(round(n * val_ratio))
    if test_ratio > 0 and n_test == 0 and n >= 3:
        n_test = 1
    if val_ratio > 0 and n_val == 0 and n >= 3:
        n_val = 1
    if n_test + n_val >= n:
        n_test = min(n_test, max(0, n - 2))
        n_val = min(n_val, max(0, n - n_test - 1))

    split_map = {}
    for idx, image_name in enumerate(image_names):
        if idx < n_test:
            split_map[image_name] = "test"
        elif idx < n_test + n_val:
            split_map[image_name] = "val"
        else:
            split_map[image_name] = "train"
    return split_map


def balance_records(records, negative_ratio, seed):
    rng = random.Random(seed)
    grouped = defaultdict(list)
    for record in records:
        grouped[record["split"]].append(record)

    selected = []
    for split_name, split_records in grouped.items():
        positives = [record for record in split_records if record["label"] == "1"]
        negatives = [record for record in split_records if record["label"] == "0"]
        if not positives or negative_ratio is None:
            selected.extend(split_records)
            continue
        max_negatives = int(len(positives) * negative_ratio)
        if max_negatives < len(negatives):
            negatives = rng.sample(negatives, max_negatives)
        selected.extend(positives)
        selected.extend(negatives)
    return selected


def safe_sample_name(record):
    image_stem = Path(record["image"]).stem
    return (
        f"{image_stem}__{record['field']}__g-{record['group']}"
        f"__i-{record['item_index']}__s-{record['sub_index']}__{record['token']}.png"
    )


def copy_task_records(task_name, records, source_root, output_root):
    task_root = output_root / task_name
    copied = []
    for record in records:
        src = source_root / record["cell_path"]
        if not src.exists():
            continue
        dst = task_root / record["split"] / CLASS_NAMES[record["label"]] / safe_sample_name(record)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied_record = dict(record)
        copied_record["dataset_path"] = str(dst.relative_to(output_root))
        copied.append(copied_record)
    return copied


def write_task_manifest(task_root, records):
    manifest_path = task_root / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "image",
            "field",
            "group",
            "item_index",
            "sub_index",
            "token",
            "label",
            "truth",
            "split",
            "dataset_path",
            "cell_path",
            "normalized_path",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record.get(key, "") for key in fieldnames})


def summarize_task(records):
    summary = {"total": len(records), "by_split": {}, "by_split_label": {}}
    by_split = Counter(record["split"] for record in records)
    by_split_label = defaultdict(Counter)
    for record in records:
        by_split_label[record["split"]][record["label"]] += 1
    summary["by_split"] = dict(by_split)
    summary["by_split_label"] = {split: dict(counter) for split, counter in by_split_label.items()}
    return summary


def main():
    parser = argparse.ArgumentParser(description="Export Kaggle-ready binary classification folders from cell manifest.")
    parser.add_argument("--manifest", default="data/cell_dataset/manifest.csv")
    parser.add_argument("--source-root", default="data/cell_dataset")
    parser.add_argument("--output-root", default="data/kaggle_datasets")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--answer-neg-ratio", type=float, default=2.0)
    parser.add_argument("--id-neg-ratio", type=float, default=3.0)
    parser.add_argument("--mssv-neg-ratio", type=float, default=3.0)
    parser.add_argument("--made-neg-ratio", type=float, default=3.0)
    args = parser.parse_args()

    source_root = Path(args.source_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    task_configs = {
        "answer_binary": {"fields": {"answer"}, "negative_ratio": args.answer_neg_ratio},
        "id_binary": {"fields": {"mssv", "ma_de"}, "negative_ratio": args.id_neg_ratio},
        "mssv_binary": {"fields": {"mssv"}, "negative_ratio": args.mssv_neg_ratio},
        "ma_de_binary": {"fields": {"ma_de"}, "negative_ratio": args.made_neg_ratio},
    }

    manifest_rows = load_manifest(args.manifest)
    image_names = [row["image"] for row in manifest_rows]
    split_map = split_images(image_names, args.val_ratio, args.test_ratio, args.seed)

    export_summary = {"splits": Counter(split_map.values()), "tasks": {}}

    for task_name, config in task_configs.items():
        task_root = output_root / task_name
        if task_root.exists():
            shutil.rmtree(task_root)

        task_records = []
        for row in manifest_rows:
            if row["field"] not in config["fields"]:
                continue
            enriched = dict(row)
            enriched["split"] = split_map[row["image"]]
            task_records.append(enriched)

        balanced_records = balance_records(task_records, config["negative_ratio"], args.seed)
        copied_records = copy_task_records(task_name, balanced_records, source_root, output_root)
        write_task_manifest(task_root, copied_records)
        export_summary["tasks"][task_name] = summarize_task(copied_records)

    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(export_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(export_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
