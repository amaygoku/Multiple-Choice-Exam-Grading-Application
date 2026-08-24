from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, List

try:
    import cv2
    from ultralytics import YOLO
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing runtime dependency for YOLO cropping: "
        f"{exc.name}. Install the project requirements in the same environment "
        "that runs this script."
    ) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "images"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "cropped_words"
DEFAULT_YOLO_WEIGHTS = Path(r"D:\X_any_label\X-AnyLabeling\anylabeling_data\models\my_text_detector\best.onnx")


def clamp_bbox(x1: int, y1: int, x2: int, y2: int, width: int, height: int, pad: int) -> tuple[int, int, int, int]:
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(width, x2 + pad)
    y2 = min(height, y2 + pad)
    return x1, y1, x2, y2


def sort_boxes_right_to_left(boxes: List[dict]) -> List[dict]:
    return sorted(
        boxes,
        key=lambda item: (-item["x1"], -item["confidence"]),
    )


def detect_text_boxes(yolo_model: YOLO, image_bgr, conf: float, iou: float) -> List[dict]:
    result = yolo_model.predict(image_bgr, conf=conf, iou=iou, verbose=False)[0]
    boxes: List[dict] = []
    if result.boxes is None:
        return boxes

    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf_value = float(box.conf[0].item()) if box.conf is not None else 0.0
        boxes.append(
            {
                "x1": int(round(x1)),
                "y1": int(round(y1)),
                "x2": int(round(x2)),
                "y2": int(round(y2)),
                "confidence": conf_value,
                "cx": (x1 + x2) / 2.0,
                "cy": (y1 + y2) / 2.0,
                "width": int(round(x2 - x1)),
                "height": int(round(y2 - y1)),
            }
        )
    return boxes


def iter_images(input_dir: Path) -> Iterable[Path]:
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    for path in sorted(input_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in valid_exts:
            yield path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect text with YOLO and save word crops with right-to-left names")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Folder containing source images")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Folder to save cropped words")
    parser.add_argument("--weights", type=Path, default=DEFAULT_YOLO_WEIGHTS, help="YOLO weight path")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO IoU threshold")
    parser.add_argument("--pad", type=int, default=0, help="Padding around detected boxes")
    parser.add_argument("--min-area", type=int, default=0, help="Ignore detections smaller than this area")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing crops with the same name")
    parser.add_argument("--manifest-csv", type=Path, help="Optional CSV manifest with crop name and bbox")
    parser.add_argument("--debug", action="store_true", help="Print step-by-step debug output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.weights.exists():
        raise FileNotFoundError(f"YOLO weights not found: {args.weights}")
    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.manifest_csv:
        args.manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] input_dir: {args.input_dir}")
    print(f"[INFO] output_dir: {args.output_dir}")
    print(f"[INFO] weights: {args.weights}")

    yolo_model = YOLO(str(args.weights))

    manifest_rows = []
    image_files = list(iter_images(args.input_dir))
    print(f"[INFO] found {len(image_files)} images")

    for image_index, image_path in enumerate(image_files, start=1):
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            print(f"[WARN] could not read image: {image_path.name}")
            continue

        height, width = image_bgr.shape[:2]
        raw_boxes = detect_text_boxes(yolo_model, image_bgr, conf=args.conf, iou=args.iou)
        print(f"[INFO] {image_index}/{len(image_files)} {image_path.name}: raw_boxes={len(raw_boxes)}")

        filtered = []
        for box in raw_boxes:
            x1, y1, x2, y2 = clamp_bbox(box["x1"], box["y1"], box["x2"], box["y2"], width, height, args.pad)
            crop_w = max(0, x2 - x1)
            crop_h = max(0, y2 - y1)
            area = crop_w * crop_h
            if area < args.min_area:
                if args.debug:
                    print(f"  [SKIP] bbox=({x1},{y1},{x2},{y2}) area={area}")
                continue

            filtered.append(
                {
                    **box,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": crop_w,
                    "height": crop_h,
                    "cx": (x1 + x2) / 2.0,
                    "cy": (y1 + y2) / 2.0,
                }
            )
        flattened = sort_boxes_right_to_left(filtered)

        if args.debug:
            print(f"  [SORT] right_to_left order, boxes={len(flattened)}")
            for idx, box in enumerate(flattened, start=1):
                print(
                    f"    {idx:02d}: bbox=({box['x1']},{box['y1']},{box['x2']},{box['y2']}) "
                    f"center=({box['cx']:.1f},{box['cy']:.1f}) conf={box['confidence']:.4f}"
                )

        for word_idx, box in enumerate(flattened):
            crop = image_bgr[box["y1"] : box["y2"], box["x1"] : box["x2"]]
            crop_name = f"{image_path.stem}_word_{word_idx:02d}.png"
            crop_path = args.output_dir / crop_name

            if crop_path.exists() and not args.overwrite:
                print(f"  [SKIP] exists: {crop_name}")
            else:
                cv2.imwrite(str(crop_path), crop)
                print(
                    f"  [SAVE] {crop_name} "
                    f"bbox=({box['x1']},{box['y1']},{box['x2']},{box['y2']}) conf={box['confidence']:.4f}"
                )

            manifest_rows.append(
                {
                    "image_name": image_path.name,
                    "crop_name": crop_name,
                    "word_index": word_idx,
                    "x1": box["x1"],
                    "y1": box["y1"],
                    "x2": box["x2"],
                    "y2": box["y2"],
                    "confidence": box["confidence"],
                }
            )

    if args.manifest_csv:
        with open(args.manifest_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["image_name", "crop_name", "word_index", "x1", "y1", "x2", "y2", "confidence"],
            )
            writer.writeheader()
            writer.writerows(manifest_rows)
        print(f"[INFO] manifest saved: {args.manifest_csv}")

    print(f"[DONE] created/updated {len(manifest_rows)} word crops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
