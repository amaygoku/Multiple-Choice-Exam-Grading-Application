import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.export_circle_only_dataset import (
    centered_ellipse_mask,
    contour_circle_normalized,
    contour_to_ellipse,
    detect_best_bubble_contour,
    ellipse_crop_and_mask,
    fit_ellipse_from_partial_arcs,
)


SPLITS = ("train", "val", "test")
CLASSES = ("empty", "filled")


def ensure_clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def mask_cell(gray, mode, pad_ratio, pad_px, ellipse_axis_ratio_x, ellipse_axis_ratio_y):
    contour = detect_best_bubble_contour(gray)
    ellipse = contour_to_ellipse(contour) if contour is not None else None

    if mode == "contour_circle_normalized":
        if ellipse is not None:
            return contour_circle_normalized(gray, ellipse, out_size=96), "contour"
        ellipse_arc = fit_ellipse_from_partial_arcs(gray)
        if ellipse_arc is not None:
            return contour_circle_normalized(gray, ellipse_arc, out_size=96), "partial_arc"
        out, _ = centered_ellipse_mask(gray, ellipse_axis_ratio_x, ellipse_axis_ratio_y)
        out = cv2.resize(out, (96, 96), interpolation=cv2.INTER_AREA)
        return out, "fallback"

    if mode == "contour_ellipse":
        if ellipse is not None:
            return ellipse_crop_and_mask(gray, ellipse, pad_ratio=pad_ratio, pad_px=pad_px), "contour"
        ellipse_arc = fit_ellipse_from_partial_arcs(gray)
        if ellipse_arc is not None:
            return ellipse_crop_and_mask(gray, ellipse_arc, pad_ratio=pad_ratio, pad_px=pad_px), "partial_arc"
        out, _ = centered_ellipse_mask(gray, ellipse_axis_ratio_x, ellipse_axis_ratio_y)
        return out, "fallback"

    out, _ = centered_ellipse_mask(gray, ellipse_axis_ratio_x, ellipse_axis_ratio_y)
    return out, "fallback"


def main():
    parser = argparse.ArgumentParser(description="Export masked answer dataset for classification training.")
    parser.add_argument("--input-dir", default="data/kaggle_datasets/answer_binary")
    parser.add_argument("--output-dir", default="data/kaggle_datasets/answer_binary_masked")
    parser.add_argument(
        "--mode",
        default="contour_circle_normalized",
        choices=["contour_circle_normalized", "contour_ellipse", "ellipse_centered"],
    )
    parser.add_argument("--keep-fallback", action="store_true", help="Keep fallback samples instead of dropping them")
    parser.add_argument("--pad-ratio", type=float, default=0.15)
    parser.add_argument("--pad-px", type=int, default=2)
    parser.add_argument("--ellipse-axis-ratio-x", type=float, default=0.72)
    parser.add_argument("--ellipse-axis-ratio-y", type=float, default=0.62)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    ensure_clean_dir(output_dir)

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "mode": args.mode,
        "keep_fallback": bool(args.keep_fallback),
        "splits": {},
        "methods": Counter(),
        "dropped_fallback": 0,
        "total_saved": 0,
    }

    for split in SPLITS:
        split_stats = defaultdict(int)
        for cls in CLASSES:
            src_dir = input_dir / split / cls
            if not src_dir.exists():
                continue
            dst_dir = output_dir / split / cls
            dst_dir.mkdir(parents=True, exist_ok=True)
            files = sorted(src_dir.glob("*.png"))
            split_stats[f"{cls}_input"] = len(files)

            for src in files:
                gray = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE)
                if gray is None:
                    continue
                masked, method = mask_cell(
                    gray,
                    mode=args.mode,
                    pad_ratio=args.pad_ratio,
                    pad_px=args.pad_px,
                    ellipse_axis_ratio_x=args.ellipse_axis_ratio_x,
                    ellipse_axis_ratio_y=args.ellipse_axis_ratio_y,
                )
                summary["methods"][method] += 1
                if method == "fallback" and not args.keep_fallback:
                    summary["dropped_fallback"] += 1
                    continue

                ok = cv2.imwrite(str(dst_dir / src.name), masked)
                if ok:
                    split_stats[f"{cls}_output"] += 1
                    summary["total_saved"] += 1

        summary["splits"][split] = dict(split_stats)

    summary["methods"] = dict(summary["methods"])
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
