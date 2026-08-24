from __future__ import annotations

import argparse
import json
import sys
import csv
import difflib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from ultralytics import YOLO
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing runtime dependency for the OCR pipeline: "
        f"{exc.name}. Install the project requirements in the same environment "
        "that runs this script."
    ) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
CRNN_DIR = SCRIPT_DIR / "crnn-pytorch-master"
if str(CRNN_DIR) not in sys.path:
    sys.path.insert(0, str(CRNN_DIR))

import dataset  # type: ignore
import models.crnn as crnn  # type: ignore
import params  # type: ignore
import utils  # type: ignore


DEFAULT_YOLO_WEIGHTS = Path(r"D:\X_any_label\X-AnyLabeling\anylabeling_data\models\my_text_detector\best.onnx")
DEFAULT_CRNN_WEIGHTS = CRNN_DIR / "models" / "best.pth"
DEFAULT_LABELS_CSV = SCRIPT_DIR / "cropped_words" / "labels.csv"


@dataclass
class OCRDetection:
    index: int
    bbox: List[int]
    confidence: float
    raw_text: str
    text: str
    crop_path: Optional[str] = None

    @property
    def x1(self) -> int:
        return self.bbox[0]

    @property
    def y1(self) -> int:
        return self.bbox[1]

    @property
    def x2(self) -> int:
        return self.bbox[2]

    @property
    def y2(self) -> int:
        return self.bbox[3]

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass
class OCRRuntime:
    device: torch.device
    yolo_model: YOLO
    crnn_model: torch.nn.Module
    converter: utils.strLabelConverter
    canonical_by_norm: dict[str, str]
    frequency: Counter[str]


def debug_print(enabled: bool, message: str) -> None:
    if enabled:
        print(message)


def normalize_vietnamese_token(text: str) -> str:
    text = text.strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def title_case_token(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


def normalize_vietnamese_token(text: str) -> str:
    text = text.strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("\u0111", "d")
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def load_name_lexicon(labels_csv_path: Path) -> tuple[dict[str, str], Counter[str]]:
    if not labels_csv_path.exists():
        return {}, Counter()

    canonical_by_norm: dict[str, str] = {}
    frequency: Counter[str] = Counter()
    with open(labels_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                continue
            for token in label.split():
                token = token.strip()
                if not token:
                    continue
                frequency[token] += 1
                norm = normalize_vietnamese_token(token)
                if not norm:
                    continue
                current = canonical_by_norm.get(norm)
                if current is None or frequency[token] > frequency[current]:
                    canonical_by_norm[norm] = token

    return canonical_by_norm, frequency


def postprocess_name_token(
    raw_text: str,
    canonical_by_norm: dict[str, str],
    frequency: Counter[str],
    debug: bool = False,
) -> str:
    raw_text = raw_text.strip()
    if not raw_text:
        return raw_text

    # Keep short numeric/symbol-like outputs untouched.
    if len(normalize_vietnamese_token(raw_text)) < 2:
        return raw_text

    raw_norm = normalize_vietnamese_token(raw_text)
    if not raw_norm:
        return raw_text

    if raw_norm in canonical_by_norm:
        return canonical_by_norm[raw_norm]

    if not canonical_by_norm:
        return title_case_token(raw_text)

    # Prefer candidates with the same first letter and similar length.
    candidates = []
    first = raw_norm[0]
    raw_len = len(raw_norm)
    for norm, token in canonical_by_norm.items():
        if not norm:
            continue
        if norm[0] != first and norm[:2] != raw_norm[:2]:
            continue
        if abs(len(norm) - raw_len) > 3:
            continue
        score = difflib.SequenceMatcher(None, raw_norm, norm).ratio()
        # Favor more frequent tokens when the score is similar.
        freq_bonus = min(0.15, frequency[token] * 0.005)
        candidates.append((score + freq_bonus, token, norm))

    if not candidates:
        # Fall back to a broader search before giving up.
        for norm, token in canonical_by_norm.items():
            if abs(len(norm) - raw_len) > 4:
                continue
            score = difflib.SequenceMatcher(None, raw_norm, norm).ratio()
            freq_bonus = min(0.1, frequency[token] * 0.003)
            candidates.append((score + freq_bonus, token, norm))

    if not candidates:
        return title_case_token(raw_text)

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_token, best_norm = candidates[0]

    # Avoid over-correcting when the OCR result is already reasonable.
    raw_vs_best = difflib.SequenceMatcher(None, raw_norm, best_norm).ratio()
    if debug:
        print(
            f"[DEBUG][POST] raw={raw_text!r} norm={raw_norm!r} "
            f"best={best_token!r} best_norm={best_norm!r} score={best_score:.3f}"
        )

    if raw_vs_best < 0.58:
        return title_case_token(raw_text)

    return best_token


def load_crnn_model(weights_path: Path, device: torch.device) -> tuple[torch.nn.Module, utils.strLabelConverter]:
    if not weights_path.exists():
        raise FileNotFoundError(f"CRNN weights not found: {weights_path}")

    nclass = len(params.alphabet) + 1
    model = crnn.CRNN(params.imgH, params.nc, nclass, params.nh).to(device)

    state = torch.load(weights_path, map_location=device)
    if isinstance(state, dict) and "state_dict" in state and isinstance(state["state_dict"], dict):
        state = state["state_dict"]

    if not isinstance(state, dict):
        raise TypeError(f"Unsupported CRNN checkpoint format: {type(state)!r}")

    cleaned_state = {}
    for key, value in state.items():
        cleaned_state[key[7:] if key.startswith("module.") else key] = value

    missing, unexpected = model.load_state_dict(cleaned_state, strict=False)
    if missing or unexpected:
        print(f"[CRNN] missing keys: {missing}")
        print(f"[CRNN] unexpected keys: {unexpected}")

    model.eval()
    converter = utils.strLabelConverter(params.alphabet)
    return model, converter


def build_ocr_runtime(
    yolo_weights: Path = DEFAULT_YOLO_WEIGHTS,
    crnn_weights: Path = DEFAULT_CRNN_WEIGHTS,
    labels_csv: Path = DEFAULT_LABELS_CSV,
    device: Optional[torch.device] = None,
    use_lexicon: bool = False,
) -> OCRRuntime:
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if not yolo_weights.exists():
        raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
    if not crnn_weights.exists():
        raise FileNotFoundError(f"CRNN weights not found: {crnn_weights}")

    yolo_model = YOLO(str(yolo_weights))
    crnn_model, converter = load_crnn_model(crnn_weights, device)
    if use_lexicon:
        canonical_by_norm, frequency = load_name_lexicon(labels_csv)
    else:
        canonical_by_norm, frequency = {}, Counter()
    return OCRRuntime(
        device=device,
        yolo_model=yolo_model,
        crnn_model=crnn_model,
        converter=converter,
        canonical_by_norm=canonical_by_norm,
        frequency=frequency,
    )


def predict_crnn_text(
    model: torch.nn.Module,
    converter: utils.strLabelConverter,
    crop_bgr: np.ndarray,
    device: torch.device,
) -> str:
    if crop_bgr.size == 0:
        return ""

    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_pil = Image.fromarray(crop_rgb).convert("L")
    transformer = dataset.resizeNormalize((params.imgW, params.imgH))
    image = transformer(crop_pil).unsqueeze(0).to(device)

    with torch.no_grad():
        preds = model(image)

    _, preds = preds.max(2)
    preds = preds.transpose(1, 0).contiguous().view(-1)
    preds_size = torch.IntTensor([preds.size(0)])
    return converter.decode(preds.cpu(), preds_size, raw=False)


def sort_reading_order(detections: List[dict]) -> List[dict]:
    if not detections:
        return []
    return sorted(detections, key=lambda item: (item["x1"], -item["confidence"]))


def bbox_area(det: dict) -> int:
    return max(0, det["x2"] - det["x1"]) * max(0, det["y2"] - det["y1"])


def intersection_area(a: dict, b: dict) -> int:
    x1 = max(a["x1"], b["x1"])
    y1 = max(a["y1"], b["y1"])
    x2 = min(a["x2"], b["x2"])
    y2 = min(a["y2"], b["y2"])
    if x2 <= x1 or y2 <= y1:
        return 0
    return (x2 - x1) * (y2 - y1)


def suppress_nested_boxes(
    detections: List[dict],
    *,
    overlap_threshold: float = 0.9,
    area_ratio_threshold: float = 0.9,
    iou_threshold: float = 0.18,
    debug: bool = False,
) -> List[dict]:
    if len(detections) < 2:
        return detections

    # Prefer larger boxes first so we only suppress smaller nested boxes.
    indexed = sorted(
        enumerate(detections),
        key=lambda item: (bbox_area(item[1]), item[1]["confidence"]),
        reverse=True,
    )
    keep = [True] * len(detections)

    for outer_rank, (outer_idx, outer) in enumerate(indexed):
        if not keep[outer_idx]:
            continue
        outer_area = bbox_area(outer)
        if outer_area <= 0:
            continue
        for inner_idx, inner in indexed[outer_rank + 1 :]:
            if not keep[inner_idx]:
                continue
            inner_area = bbox_area(inner)
            if inner_area <= 0:
                continue

            inter_area = intersection_area(outer, inner)
            if inter_area <= 0:
                continue

            outer_area = max(1, outer_area)
            overlap_with_inner = inter_area / float(inner_area)
            area_ratio = inner_area / float(outer_area)
            union_area = outer_area + inner_area - inter_area
            iou = inter_area / float(union_area) if union_area > 0 else 0.0

            if (
                overlap_with_inner >= overlap_threshold and area_ratio <= area_ratio_threshold
            ) or (
                overlap_with_inner >= 0.75
                and iou >= iou_threshold
                and area_ratio <= 0.95
            ):
                keep[inner_idx] = False
                debug_print(
                    debug,
                    "[DEBUG][NESTED] "
                    f"drop inner bbox=({inner['x1']}, {inner['y1']}, {inner['x2']}, {inner['y2']}) "
                    f"conf={inner['confidence']:.4f} because it is nested in "
                    f"({outer['x1']}, {outer['y1']}, {outer['x2']}, {outer['y2']}) "
                    f"overlap={overlap_with_inner:.3f} area_ratio={area_ratio:.3f} iou={iou:.3f}",
                )

    return [det for idx, det in enumerate(detections) if keep[idx]]


def clamp_bbox(x1: int, y1: int, x2: int, y2: int, width: int, height: int, pad: int) -> tuple[int, int, int, int]:
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(width, x2 + pad)
    y2 = min(height, y2 + pad)
    return x1, y1, x2, y2


def detect_text_boxes(
    yolo_model: YOLO,
    image_bgr: np.ndarray,
    conf: float,
    iou: float,
    debug: bool = False,
) -> List[dict]:
    result = yolo_model.predict(image_bgr, conf=conf, iou=iou, verbose=False)[0]
    detections: List[dict] = []

    debug_print(debug, f"[DEBUG][YOLO] raw result boxes: {0 if result.boxes is None else len(result.boxes)}")
    if result.boxes is None:
        return detections

    for idx, box in enumerate(result.boxes, start=1):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf_value = float(box.conf[0].item()) if box.conf is not None else 0.0
        detections.append(
            {
                "x1": int(round(x1)),
                "y1": int(round(y1)),
                "x2": int(round(x2)),
                "y2": int(round(y2)),
                "confidence": conf_value,
            }
        )
        debug_print(
            debug,
            f"[DEBUG][YOLO] box {idx}: "
            f"({int(round(x1))}, {int(round(y1))}, {int(round(x2))}, {int(round(y2))}) "
            f"conf={conf_value:.4f}",
        )

    return detections


def process_image_bgr(
    image_bgr: np.ndarray,
    runtime: OCRRuntime,
    image_name: str = "image",
    image_path_repr: Optional[str] = None,
    conf: float = 0.25,
    iou: float = 0.45,
    pad: int = 0,
    min_area: int = 0,
    save_crops_dir: Optional[Path] = None,
    save_annotated_dir: Optional[Path] = None,
    debug: bool = False,
    save_debug_dir: Optional[Path] = None,
) -> dict:
    debug_print(debug, f"[DEBUG][IMAGE] path={image_path_repr or image_name}")
    debug_print(debug, f"[DEBUG][IMAGE] shape={image_bgr.shape}")

    raw_detections = detect_text_boxes(runtime.yolo_model, image_bgr, conf=conf, iou=iou, debug=debug)
    filtered: List[dict] = []
    h, w = image_bgr.shape[:2]
    debug_print(debug, f"[DEBUG][FILTER] pad={pad} min_area={min_area}")
    for det in raw_detections:
        x1, y1, x2, y2 = clamp_bbox(det["x1"], det["y1"], det["x2"], det["y2"], w, h, pad)
        width = max(0, x2 - x1)
        height = max(0, y2 - y1)
        area = width * height
        debug_print(
            debug,
            f"[DEBUG][FILTER] candidate bbox=({x1}, {y1}, {x2}, {y2}) "
            f"size={width}x{height} area={area}",
        )
        if width * height < min_area:
            debug_print(debug, "[DEBUG][FILTER] -> skipped (too small)")
            continue
        filtered.append({**det, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": width, "height": height, "cx": (x1 + x2) / 2.0, "cy": (y1 + y2) / 2.0})
        debug_print(debug, "[DEBUG][FILTER] -> kept")

    filtered = suppress_nested_boxes(filtered, debug=debug)
    debug_print(debug, f"[DEBUG][FILTER] after nested suppression={len(filtered)}")

    ordered = sort_reading_order(filtered)
    debug_print(debug, f"[DEBUG][SORT] kept={len(filtered)} ordered={len(ordered)}")
    for idx, det in enumerate(ordered, start=1):
        debug_print(
            debug,
            f"[DEBUG][SORT] {idx}: bbox=({det['x1']}, {det['y1']}, {det['x2']}, {det['y2']}) "
            f"center=({det['cx']:.1f}, {det['cy']:.1f}) size={det['width']}x{det['height']} conf={det['confidence']:.4f}",
        )

    save_crops_dir = save_crops_dir.resolve() if save_crops_dir else None
    if save_crops_dir:
        save_crops_dir.mkdir(parents=True, exist_ok=True)

    save_debug_dir = save_debug_dir.resolve() if save_debug_dir else None
    if save_debug_dir:
        save_debug_dir.mkdir(parents=True, exist_ok=True)
        debug_image_path = save_debug_dir / f"{Path(image_name).stem}_01_raw_detections.png"
        raw_vis = annotate_image(image_bgr, [OCRDetection(index=i + 1, bbox=[d["x1"], d["y1"], d["x2"], d["y2"]], confidence=float(d["confidence"]), raw_text="", text="") for i, d in enumerate(raw_detections)])
        cv2.imwrite(str(debug_image_path), raw_vis)
        debug_print(debug, f"[DEBUG][SAVE] raw detections: {debug_image_path}")

    detections: List[OCRDetection] = []
    image_stem = Path(image_name).stem
    for idx, det in enumerate(ordered, start=1):
        crop = image_bgr[det["y1"] : det["y2"], det["x1"] : det["x2"]]
        debug_print(debug, f"[DEBUG][CROP] {idx}: crop_shape={crop.shape}")
        raw_text = predict_crnn_text(runtime.crnn_model, runtime.converter, crop, runtime.device)
        text = postprocess_name_token(raw_text, runtime.canonical_by_norm, runtime.frequency, debug=debug)
        debug_print(debug, f"[DEBUG][CRNN] {idx}: raw={raw_text!r} post={text!r}")
        crop_path = None
        if save_crops_dir is not None:
            crop_path = str(save_crops_dir / f"{image_stem}_{idx:03d}.png")
            cv2.imwrite(crop_path, crop)
            debug_print(debug, f"[DEBUG][SAVE] crop: {crop_path}")

        if save_debug_dir is not None:
            crop_debug_path = save_debug_dir / f"{image_stem}_{idx:03d}_crop.png"
            cv2.imwrite(str(crop_debug_path), crop)
            debug_print(debug, f"[DEBUG][SAVE] debug crop: {crop_debug_path}")

        detections.append(
            OCRDetection(
                index=idx,
                bbox=[det["x1"], det["y1"], det["x2"], det["y2"]],
                confidence=float(det["confidence"]),
                raw_text=raw_text,
                text=text,
                crop_path=crop_path,
            )
        )

    annotated_path = None
    if save_annotated_dir is not None:
        save_annotated_dir.mkdir(parents=True, exist_ok=True)
        annotated = annotate_image(image_bgr, detections)
        annotated_path = str(save_annotated_dir / f"{image_stem}_annotated.png")
        cv2.imwrite(annotated_path, annotated)
        debug_print(debug, f"[DEBUG][SAVE] annotated: {annotated_path}")

    if save_debug_dir is not None:
        final_debug_path = save_debug_dir / f"{image_stem}_02_final_annotated.png"
        cv2.imwrite(str(final_debug_path), annotate_image(image_bgr, detections))
        debug_print(debug, f"[DEBUG][SAVE] final debug annotated: {final_debug_path}")

    text_by_box = [det.text for det in detections]
    raw_text_by_box = [det.raw_text for det in detections]
    compact_text = "".join(text_by_box)
    joined_text = " ".join(item for item in text_by_box if item)
    multiline_text = joined_text

    return {
        "image_path": image_path_repr or image_name,
        "image_name": image_name,
        "num_boxes": len(detections),
        "raw_text_by_box": raw_text_by_box,
        "text_by_box": text_by_box,
        "joined_text": joined_text,
        "compact_text": compact_text,
        "multiline_text": multiline_text,
        "detections": [asdict(det) for det in detections],
        "annotated_path": annotated_path,
    }


def annotate_image(image_bgr: np.ndarray, detections: List[OCRDetection]) -> np.ndarray:
    annotated = image_bgr.copy()
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{det.index}: {det.text}".strip()
        label = label[:60] if label else f"{det.index}"
        y_text = max(18, y1 - 6)
        cv2.putText(
            annotated,
            label,
            (x1, y_text),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    return annotated


def process_image(
    image_path: Path,
    yolo_model: YOLO,
    crnn_model: torch.nn.Module,
    converter: utils.strLabelConverter,
    canonical_by_norm: dict[str, str],
    frequency: Counter[str],
    device: torch.device,
    conf: float,
    iou: float,
    pad: int,
    min_area: int,
    save_crops_dir: Optional[Path] = None,
    save_annotated_dir: Optional[Path] = None,
    debug: bool = False,
    save_debug_dir: Optional[Path] = None,
) -> dict:
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise ValueError(f"Could not read image: {image_path}")

    debug_print(debug, f"[DEBUG][IMAGE] path={image_path}")
    debug_print(debug, f"[DEBUG][IMAGE] shape={image_bgr.shape}")

    raw_detections = detect_text_boxes(yolo_model, image_bgr, conf=conf, iou=iou, debug=debug)
    filtered: List[dict] = []
    h, w = image_bgr.shape[:2]
    debug_print(debug, f"[DEBUG][FILTER] pad={pad} min_area={min_area}")
    for det in raw_detections:
        x1, y1, x2, y2 = clamp_bbox(det["x1"], det["y1"], det["x2"], det["y2"], w, h, pad)
        width = max(0, x2 - x1)
        height = max(0, y2 - y1)
        area = width * height
        debug_print(
            debug,
            f"[DEBUG][FILTER] candidate bbox=({x1}, {y1}, {x2}, {y2}) "
            f"size={width}x{height} area={area}",
        )
        if width * height < min_area:
            debug_print(debug, "[DEBUG][FILTER] -> skipped (too small)")
            continue
        filtered.append({**det, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": width, "height": height, "cx": (x1 + x2) / 2.0, "cy": (y1 + y2) / 2.0})
        debug_print(debug, "[DEBUG][FILTER] -> kept")

    filtered = suppress_nested_boxes(filtered, debug=debug)
    debug_print(debug, f"[DEBUG][FILTER] after nested suppression={len(filtered)}")

    ordered = sort_reading_order(filtered)
    debug_print(debug, f"[DEBUG][SORT] kept={len(filtered)} ordered={len(ordered)}")
    for idx, det in enumerate(ordered, start=1):
        debug_print(
            debug,
            f"[DEBUG][SORT] {idx}: bbox=({det['x1']}, {det['y1']}, {det['x2']}, {det['y2']}) "
            f"center=({det['cx']:.1f}, {det['cy']:.1f}) size={det['width']}x{det['height']} conf={det['confidence']:.4f}",
        )

    save_crops_dir = save_crops_dir.resolve() if save_crops_dir else None
    if save_crops_dir:
        save_crops_dir.mkdir(parents=True, exist_ok=True)

    save_debug_dir = save_debug_dir.resolve() if save_debug_dir else None
    if save_debug_dir:
        save_debug_dir.mkdir(parents=True, exist_ok=True)
        debug_image_path = save_debug_dir / f"{image_path.stem}_01_raw_detections.png"
        raw_vis = annotate_image(image_bgr, [OCRDetection(index=i + 1, bbox=[d["x1"], d["y1"], d["x2"], d["y2"]], confidence=float(d["confidence"]), text="") for i, d in enumerate(raw_detections)])
        cv2.imwrite(str(debug_image_path), raw_vis)
        debug_print(debug, f"[DEBUG][SAVE] raw detections: {debug_image_path}")

    detections: List[OCRDetection] = []
    for idx, det in enumerate(ordered, start=1):
        crop = image_bgr[det["y1"] : det["y2"], det["x1"] : det["x2"]]
        debug_print(debug, f"[DEBUG][CROP] {idx}: crop_shape={crop.shape}")
        raw_text = predict_crnn_text(crnn_model, converter, crop, device)
        text = postprocess_name_token(raw_text, canonical_by_norm, frequency, debug=debug)
        debug_print(debug, f"[DEBUG][CRNN] {idx}: raw={raw_text!r} post={text!r}")
        crop_path = None
        if save_crops_dir is not None:
            crop_path = str(save_crops_dir / f"{image_path.stem}_{idx:03d}.png")
            cv2.imwrite(crop_path, crop)
            debug_print(debug, f"[DEBUG][SAVE] crop: {crop_path}")

        if save_debug_dir is not None:
            crop_debug_path = save_debug_dir / f"{image_path.stem}_{idx:03d}_crop.png"
            cv2.imwrite(str(crop_debug_path), crop)
            debug_print(debug, f"[DEBUG][SAVE] debug crop: {crop_debug_path}")

        detections.append(
            OCRDetection(
                index=idx,
                bbox=[det["x1"], det["y1"], det["x2"], det["y2"]],
                confidence=float(det["confidence"]),
                raw_text=raw_text,
                text=text,
                crop_path=crop_path,
            )
        )

    annotated_path = None
    if save_annotated_dir is not None:
        save_annotated_dir.mkdir(parents=True, exist_ok=True)
        annotated = annotate_image(image_bgr, detections)
        annotated_path = str(save_annotated_dir / f"{image_path.stem}_annotated.png")
        cv2.imwrite(annotated_path, annotated)
        debug_print(debug, f"[DEBUG][SAVE] annotated: {annotated_path}")

    if save_debug_dir is not None:
        final_debug_path = save_debug_dir / f"{image_path.stem}_02_final_annotated.png"
        cv2.imwrite(str(final_debug_path), annotate_image(image_bgr, detections))
        debug_print(debug, f"[DEBUG][SAVE] final debug annotated: {final_debug_path}")

    text_by_box = [det.text for det in detections]
    raw_text_by_box = [det.raw_text for det in detections]
    compact_text = "".join(text_by_box)
    joined_text = " ".join(item for item in text_by_box if item)
    multiline_text = joined_text

    return {
        "image_path": str(image_path),
        "image_name": image_path.name,
        "num_boxes": len(detections),
        "raw_text_by_box": raw_text_by_box,
        "text_by_box": text_by_box,
        "joined_text": joined_text,
        "compact_text": compact_text,
        "multiline_text": multiline_text,
        "detections": [asdict(det) for det in detections],
        "annotated_path": annotated_path,
    }


def iter_input_images(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return

    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    for item in sorted(path.iterdir()):
        if item.is_file() and item.suffix.lower() in valid_exts:
            yield item


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YOLO text detection + CRNN OCR pipeline")
    parser.add_argument("--image", type=Path, help="Path to a single image")
    parser.add_argument("--input-dir", type=Path, help="Folder containing images to process")
    parser.add_argument("--yolo-weights", type=Path, default=DEFAULT_YOLO_WEIGHTS, help="YOLO weight path")
    parser.add_argument("--crnn-weights", type=Path, default=DEFAULT_CRNN_WEIGHTS, help="CRNN weight path")
    parser.add_argument("--labels-csv", type=Path, default=DEFAULT_LABELS_CSV, help="CSV labels used as Vietnamese name lexicon")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO IoU threshold")
    parser.add_argument("--pad", type=int, default=0, help="Padding added around detected boxes")
    parser.add_argument("--min-area", type=int, default=0, help="Filter detections smaller than this area")
    parser.add_argument("--save-crops-dir", type=Path, help="Optional folder to save cropped detections")
    parser.add_argument("--save-annotated-dir", type=Path, help="Optional folder to save annotated images")
    parser.add_argument("--save-debug-dir", type=Path, help="Optional folder to save step-by-step debug images")
    parser.add_argument("--debug", action="store_true", help="Print detailed logs for each pipeline step")
    parser.add_argument("--json-output", type=Path, help="Optional JSON output path")
    parser.add_argument("--no-lexicon", action="store_true", help="Skip matching detected words against the name lexicon (default)")
    parser.add_argument("--lexicon", action="store_true", help="Enable matching detected words against the name lexicon")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.image and not args.input_dir:
        parser.error("Please provide --image or --input-dir")

    input_root = args.image or args.input_dir
    if input_root is None:
        parser.error("No input provided")

    if not args.yolo_weights.exists():
        raise FileNotFoundError(f"YOLO weights not found: {args.yolo_weights}")
    if not args.crnn_weights.exists():
        raise FileNotFoundError(f"CRNN weights not found: {args.crnn_weights}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Using device: {device}")
    print(f"[INFO] YOLO weights: {args.yolo_weights}")
    print(f"[INFO] CRNN weights: {args.crnn_weights}")
    
    # Lexicon is disabled by default because evaluation showed that token-level
    # correction over-corrects many already-correct CRNN outputs.
    use_lexicon = args.lexicon and not args.no_lexicon
    
    if not use_lexicon:
        print("[INFO] Lexicon matching disabled")
    else:
        print(f"[INFO] labels csv: {args.labels_csv}")
        
    if args.debug:
        print("[INFO] Debug mode enabled")

    yolo_model = YOLO(str(args.yolo_weights))
    crnn_model, converter = load_crnn_model(args.crnn_weights, device)
    
    if not use_lexicon:
        canonical_by_norm, frequency = {}, Counter()
    else:
        canonical_by_norm, frequency = load_name_lexicon(args.labels_csv)
        print(f"[INFO] lexicon size: {len(canonical_by_norm)}")

    results = []
    for image_path in iter_input_images(input_root):
        print(f"[INFO] Processing: {image_path}")
        result = process_image(
            image_path=image_path,
            yolo_model=yolo_model,
            crnn_model=crnn_model,
            converter=converter,
            canonical_by_norm=canonical_by_norm,
            frequency=frequency,
            device=device,
            conf=args.conf,
            iou=args.iou,
            pad=args.pad,
            min_area=args.min_area,
            save_crops_dir=args.save_crops_dir,
            save_annotated_dir=args.save_annotated_dir,
            debug=args.debug,
            save_debug_dir=args.save_debug_dir,
        )
        results.append(result)
        print(f"[RESULT] {image_path.name}")
        print(f"  boxes: {result['num_boxes']}")
        print(f"  joined: {result['joined_text']}")
        print(f"  compact: {result['compact_text']}")
        if result["multiline_text"]:
            print("  multiline:")
            for line in result["multiline_text"].splitlines():
                print(f"    {line}")
        if result["annotated_path"]:
            print(f"  annotated: {result['annotated_path']}")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[INFO] JSON saved to {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
