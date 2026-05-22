import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.export_circle_only_dataset import (
    contour_to_ellipse,
    detect_best_bubble_contour,
    ellipse_crop_and_mask,
)


def list_inputs(input_path: Path, pattern: str, recursive: bool, limit: int):
    if input_path.is_file():
        return [input_path]
    if recursive:
        files = sorted(input_path.rglob(pattern))
    else:
        files = sorted(input_path.glob(pattern))
    return files[:limit] if limit > 0 else files


def save_preview(image_path: Path, out_root: Path, pad_ratio: float, pad_px: int):
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return False, None

    contour = detect_best_bubble_contour(gray)
    ellipse = contour_to_ellipse(contour) if contour is not None else None
    masked = ellipse_crop_and_mask(gray, ellipse, pad_ratio=pad_ratio, pad_px=pad_px) if ellipse is not None else gray.copy()

    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if contour is not None:
        cv2.drawContours(overlay, [contour], -1, (0, 255, 255), 1)
    if ellipse is not None:
        cx, cy, ax, ay, angle = ellipse
        cv2.ellipse(overlay, (cx, cy), (ax, ay), angle, 0, 360, (255, 0, 255), 2)

    stem = image_path.stem
    item_dir = out_root / stem
    item_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(item_dir / "01_original.png"), gray)
    cv2.imwrite(str(item_dir / "02_overlay.png"), overlay)
    cv2.imwrite(str(item_dir / "03_masked.png"), masked)
    return True, ellipse


def main():
    parser = argparse.ArgumentParser(description="Preview bubble masking for one or many cell images.")
    parser.add_argument("--input", required=True, help="Input image file or directory")
    parser.add_argument("--output-dir", default="data/single_mask_preview", help="Output folder")
    parser.add_argument("--pattern", default="*.png", help="Glob pattern when input is a directory")
    parser.add_argument("--recursive", action="store_true", help="Recursively scan input directory")
    parser.add_argument("--limit", type=int, default=20, help="Max files to process (<=0 means all)")
    parser.add_argument("--pad-ratio", type=float, default=0.15)
    parser.add_argument("--pad-px", type=int, default=2)
    args = parser.parse_args()

    input_path = Path(args.input)
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    files = list_inputs(input_path, args.pattern, args.recursive, args.limit)
    if not files:
        print(f"No input files found at: {input_path}")
        return

    ok_count = 0
    for file_path in files:
        ok, ellipse = save_preview(file_path, out_root, pad_ratio=args.pad_ratio, pad_px=args.pad_px)
        if ok:
            ok_count += 1
            print(f"[OK] {file_path.name} ellipse={ellipse}")
        else:
            print(f"[SKIP] {file_path}")

    print(f"Done: {ok_count}/{len(files)} files. Output: {out_root}")


if __name__ == "__main__":
    main()
