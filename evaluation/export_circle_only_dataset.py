import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np


SPLITS = ("train", "val", "test")
CLASSES = ("empty", "filled")


def ensure_clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def detectpaper_style_edges(gray: np.ndarray):
    # Keep the edge pipeline aligned with detect_paper.py for consistency.
    bilateral = cv2.bilateralFilter(gray, 5, 75, 75)
    thresh = cv2.adaptiveThreshold(
        bilateral,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        115,
        4,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    bordered = cv2.copyMakeBorder(opened, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=0)
    edges = cv2.Canny(bordered, 10, 450)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    # Auto-bridge broken edge segments so bubble contours close more reliably.
    bridge_h = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))
    bridge_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
    closed = cv2.morphologyEx(closed, cv2.MORPH_CLOSE, bridge_h, iterations=1)
    closed = cv2.morphologyEx(closed, cv2.MORPH_CLOSE, bridge_v, iterations=1)
    closed = cv2.dilate(closed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    return closed


def detect_circle_hough(gray: np.ndarray):
    h, w = gray.shape[:2]
    min_side = min(h, w)
    edges = detectpaper_style_edges(gray)
    # Remove the 5px border added in edge preprocessing.
    if edges.shape[0] > 10 and edges.shape[1] > 10:
        edges = edges[5:-5, 5:-5]

    circles = cv2.HoughCircles(
        edges,
        cv2.HOUGH_GRADIENT,
        dp=1.1,
        minDist=max(8, min_side // 4),
        param1=120,
        param2=10,
        minRadius=max(5, int(min_side * 0.18)),
        maxRadius=max(8, int(min_side * 0.48)),
    )
    if circles is None:
        return None

    circles = np.round(circles[0, :]).astype(int)
    cx0, cy0 = w // 2, h // 2
    best = None
    best_score = None
    for cx, cy, r in circles:
        dist = abs(cx - cx0) + abs(cy - cy0)
        # Prefer centered circles with larger radius.
        score = dist - 0.35 * r
        if best is None or score < best_score:
            best = (cx, cy, r)
            best_score = score
    return best


def detect_circle_contour(gray: np.ndarray):
    h, w = gray.shape[:2]
    min_side = min(h, w)
    edges = detectpaper_style_edges(gray)
    if edges.shape[0] > 10 and edges.shape[1] > 10:
        edges = edges[5:-5, 5:-5]
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    cx0, cy0 = w // 2, h // 2
    best = None
    best_score = None
    min_area = max(20.0, (min_side * min_side) * 0.04)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 1e-6:
            continue
        circularity = (4.0 * np.pi * area) / (perimeter * perimeter)
        if circularity < 0.55:
            continue

        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        if radius < min_side * 0.15 or radius > min_side * 0.5:
            continue
        dist = abs(cx - cx0) + abs(cy - cy0)
        score = dist - 0.25 * radius - 25.0 * circularity
        if best is None or score < best_score:
            best = (int(round(cx)), int(round(cy)), int(round(radius)))
            best_score = score
    return best


def detect_circle(gray: np.ndarray):
    circle = detect_circle_hough(gray)
    if circle is not None:
        return circle, "hough"
    circle = detect_circle_contour(gray)
    if circle is not None:
        return circle, "contour"
    return None, "fallback"


def detect_best_bubble_contour(gray: np.ndarray):
    h, w = gray.shape[:2]
    min_side = min(h, w)
    edges = detectpaper_style_edges(gray)
    if edges.shape[0] > 10 and edges.shape[1] > 10:
        edges = edges[5:-5, 5:-5]
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    cx0, cy0 = w / 2.0, h / 2.0
    min_area = max(24.0, (min_side * min_side) * 0.03)
    max_area = (min_side * min_side) * 0.85
    best = None
    best_area = -1.0
    best_dist = 1e18
    border_margin = 1

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 1e-6:
            continue
        circularity = (4.0 * np.pi * area) / (perimeter * perimeter)
        if circularity < 0.18:
            continue

        x, y, bw, bh = cv2.boundingRect(contour)
        if bw <= 0 or bh <= 0:
            continue
        touches_border = (
            x <= border_margin
            or y <= border_margin
            or (x + bw) >= (w - border_margin)
            or (y + bh) >= (h - border_margin)
        )
        aspect = bw / float(bh)
        if not 0.45 <= aspect <= 1.9:
            continue
        rel_w = bw / float(w)
        rel_h = bh / float(h)
        if not (0.18 <= rel_w <= 0.98 and 0.18 <= rel_h <= 0.98):
            continue

        moments = cv2.moments(contour)
        if abs(moments["m00"]) < 1e-6:
            continue
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
        # Penalize vertical shift more because artifacts often appear near bottom edge.
        dist = abs(cx - cx0) + 1.2 * abs(cy - cy0)
        # Border-touching contours are often broken arcs, but keep them if they are otherwise good.
        border_penalty = 0.0
        if touches_border:
            border_penalty = min_side * (0.02 if circularity >= 0.62 else 0.22)
        dist += border_penalty
        # Primary criterion: larger contour (outer bubble ring).
        # Secondary tie-breaker: closer to center.
        if (area > best_area * 1.03) or (abs(area - best_area) <= max(10.0, best_area * 0.03) and dist < best_dist):
            best = contour
            best_area = float(area)
            best_dist = float(dist)

    return best


def fit_ellipse_from_partial_arcs(gray: np.ndarray):
    h, w = gray.shape[:2]
    edges = detectpaper_style_edges(gray)
    if edges.shape[0] > 10 and edges.shape[1] > 10:
        edges = edges[5:-5, 5:-5]

    ys, xs = np.where(edges > 0)
    if len(xs) < 20:
        return None

    cx0, cy0 = w / 2.0, h / 2.0
    pts = np.column_stack((xs.astype(np.float32), ys.astype(np.float32)))

    # Keep a center-focused ring area so open arcs can still contribute.
    rx = max(6.0, w * 0.48)
    ry = max(6.0, h * 0.48)
    norm = ((pts[:, 0] - cx0) / rx) ** 2 + ((pts[:, 1] - cy0) / ry) ** 2
    pts = pts[norm <= 1.45]
    if len(pts) < 20:
        return None

    # Drop bottom-most points to reduce baseline artifacts.
    y_cut = np.percentile(pts[:, 1], 90)
    pts = pts[pts[:, 1] <= y_cut]
    if len(pts) < 16:
        return None

    try:
        (cx, cy), (major, minor), angle = cv2.fitEllipse(pts.reshape(-1, 1, 2))
    except cv2.error:
        return None

    if major <= 0 or minor <= 0:
        return None
    ax = max(4, int(round(major / 2.0)))
    ay = max(4, int(round(minor / 2.0)))
    if ax > w or ay > h:
        return None
    return (int(round(cx)), int(round(cy)), ax, ay, float(angle))


def contour_to_ellipse(contour):
    if contour is None:
        return None
    if len(contour) >= 5:
        (cx, cy), (major, minor), angle = cv2.fitEllipse(contour)
        ax = max(4, int(round(major / 2.0)))
        ay = max(4, int(round(minor / 2.0)))
        return (int(round(cx)), int(round(cy)), ax, ay, float(angle))

    x, y, w, h = cv2.boundingRect(contour)
    cx = x + w // 2
    cy = y + h // 2
    ax = max(4, w // 2)
    ay = max(4, h // 2)
    return (cx, cy, ax, ay, 0.0)


def ellipse_crop_and_mask(gray: np.ndarray, ellipse, pad_ratio: float, pad_px: int):
    h, w = gray.shape[:2]
    cx, cy, ax, ay, angle = ellipse
    pad_x = max(int(round(ax * pad_ratio)), int(pad_px))
    pad_y = max(int(round(ay * pad_ratio)), int(pad_px))

    x1 = max(0, cx - ax - pad_x)
    y1 = max(0, cy - ay - pad_y)
    x2 = min(w, cx + ax + pad_x)
    y2 = min(h, cy + ay + pad_y)

    cropped = gray[y1:y2, x1:x2]
    if cropped.size == 0:
        return gray.copy()

    local_cx = cx - x1
    local_cy = cy - y1
    mask = np.zeros(cropped.shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (local_cx, local_cy), (ax, ay), angle, 0, 360, 255, -1)
    masked = cv2.bitwise_and(cropped, cropped, mask=mask)
    return masked


def contour_circle_normalized(gray: np.ndarray, ellipse, out_size: int = 96):
    h, w = gray.shape[:2]
    cx, cy, ax, ay, angle = ellipse
    ax = max(4, int(ax))
    ay = max(4, int(ay))
    x1 = max(0, cx - ax)
    y1 = max(0, cy - ay)
    x2 = min(w, cx + ax)
    y2 = min(h, cy + ay)
    roi = gray[y1:y2, x1:x2]
    if roi.size == 0:
        return cv2.resize(gray, (out_size, out_size), interpolation=cv2.INTER_AREA)

    # Rotate ROI so ellipse axes align with image axes.
    roi_h, roi_w = roi.shape[:2]
    m = cv2.getRotationMatrix2D((roi_w / 2.0, roi_h / 2.0), angle, 1.0)
    rotated = cv2.warpAffine(roi, m, (roi_w, roi_h), flags=cv2.INTER_LINEAR, borderValue=0)

    # Normalize anisotropic distortion: make the ellipse circular.
    major = max(ax, ay) * 2
    sx = major / max(ax * 2, 1)
    sy = major / max(ay * 2, 1)
    normalized = cv2.resize(
        rotated,
        (max(8, int(round(roi_w * sx))), max(8, int(round(roi_h * sy)))),
        interpolation=cv2.INTER_CUBIC,
    )

    # Center-crop around transformed bubble center.
    cx_n = normalized.shape[1] // 2
    cy_n = normalized.shape[0] // 2
    rad = max(6, int(round(major / 2.0)))
    nx1 = max(0, cx_n - rad)
    ny1 = max(0, cy_n - rad)
    nx2 = min(normalized.shape[1], cx_n + rad)
    ny2 = min(normalized.shape[0], cy_n + rad)
    bubble = normalized[ny1:ny2, nx1:nx2]
    if bubble.size == 0:
        bubble = normalized

    bubble = cv2.resize(bubble, (out_size, out_size), interpolation=cv2.INTER_AREA)
    mask = np.zeros((out_size, out_size), dtype=np.uint8)
    cv2.circle(mask, (out_size // 2, out_size // 2), int(out_size * 0.43), 255, -1)
    return cv2.bitwise_and(bubble, bubble, mask=mask)


def crop_and_mask(gray: np.ndarray, circle, pad_ratio: float, pad_px: int):
    h, w = gray.shape[:2]
    cx, cy, radius = circle
    pad = max(int(round(radius * pad_ratio)), int(pad_px))
    side_r = radius + pad

    x1 = max(0, cx - side_r)
    y1 = max(0, cy - side_r)
    x2 = min(w, cx + side_r)
    y2 = min(h, cy + side_r)

    cropped = gray[y1:y2, x1:x2]
    if cropped.size == 0:
        return gray.copy()

    local_cx = cx - x1
    local_cy = cy - y1
    mask = np.zeros(cropped.shape[:2], dtype=np.uint8)
    cv2.circle(mask, (local_cx, local_cy), radius, 255, -1)
    masked = cv2.bitwise_and(cropped, cropped, mask=mask)
    return masked


def centered_ellipse_mask(gray: np.ndarray, axis_ratio_x: float, axis_ratio_y: float):
    h, w = gray.shape[:2]
    cx, cy = w // 2, h // 2
    ax = max(4, int(round((w * 0.5) * axis_ratio_x)))
    ay = max(4, int(round((h * 0.5) * axis_ratio_y)))
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
    return cv2.bitwise_and(gray, gray, mask=mask), (cx, cy, ax, ay)


def process_image(
    src: Path,
    dst: Path,
    pad_ratio: float,
    pad_px: int,
    mode: str,
    ellipse_axis_ratio_x: float,
    ellipse_axis_ratio_y: float,
):
    gray = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return {"ok": False, "method": "read_error", "debug": None}

    if mode == "ellipse_centered":
        output, ellipse = centered_ellipse_mask(gray, ellipse_axis_ratio_x, ellipse_axis_ratio_y)
        circle = None
        method = "ellipse_centered"
        debug = {"gray": gray, "circle": None, "output": output, "ellipse": ellipse, "contour": None}
    elif mode == "contour_circle_normalized":
        contour = detect_best_bubble_contour(gray)
        ellipse = contour_to_ellipse(contour)
        if ellipse is None:
            ellipse = fit_ellipse_from_partial_arcs(gray)
            if ellipse is not None:
                output = contour_circle_normalized(gray, ellipse, out_size=96)
                method = "partial_arc_circle_normalized"
            else:
                output, ellipse = centered_ellipse_mask(gray, ellipse_axis_ratio_x, ellipse_axis_ratio_y)
                output = cv2.resize(output, (96, 96), interpolation=cv2.INTER_AREA)
                method = "contour_circle_norm_fallback"
            contour = None
        else:
            output = contour_circle_normalized(gray, ellipse, out_size=96)
            method = "contour_circle_normalized"
        circle = None
        debug = {"gray": gray, "circle": None, "output": output, "ellipse": ellipse, "contour": contour}
    elif mode == "contour_ellipse":
        contour = detect_best_bubble_contour(gray)
        ellipse = contour_to_ellipse(contour)
        if ellipse is None:
            ellipse = fit_ellipse_from_partial_arcs(gray)
            if ellipse is not None:
                output = ellipse_crop_and_mask(gray, ellipse, pad_ratio=pad_ratio, pad_px=pad_px)
                method = "partial_arc_ellipse"
            else:
                output, ellipse = centered_ellipse_mask(gray, ellipse_axis_ratio_x, ellipse_axis_ratio_y)
                method = "contour_ellipse_fallback"
            contour = None
        else:
            output = ellipse_crop_and_mask(gray, ellipse, pad_ratio=pad_ratio, pad_px=pad_px)
            method = "contour_ellipse"
        circle = None
        debug = {"gray": gray, "circle": None, "output": output, "ellipse": ellipse, "contour": contour}
    else:
        circle, method = detect_circle(gray)
        if circle is None:
            output = gray
        else:
            output = crop_and_mask(gray, circle, pad_ratio=pad_ratio, pad_px=pad_px)
        debug = {"gray": gray, "circle": circle, "output": output, "ellipse": None, "contour": None}

    dst.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dst), output)
    return {"ok": bool(ok), "method": method, "debug": debug}


def make_debug_panel(gray: np.ndarray, circle, output: np.ndarray, ellipse=None, contour=None):
    edges = detectpaper_style_edges(gray)
    if edges.shape[0] > 10 and edges.shape[1] > 10:
        edges = edges[5:-5, 5:-5]
    src_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    edge_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    if edge_bgr.shape[:2] != src_bgr.shape[:2]:
        edge_bgr = cv2.resize(edge_bgr, (src_bgr.shape[1], src_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

    overlay = src_bgr.copy()
    if circle is not None:
        cx, cy, radius = circle
        cv2.circle(overlay, (cx, cy), radius, (0, 0, 255), 2)
        cv2.circle(overlay, (cx, cy), 2, (0, 255, 0), -1)
    if ellipse is not None:
        if len(ellipse) == 4:
            cx, cy, ax, ay = ellipse
            angle = 0.0
        else:
            cx, cy, ax, ay, angle = ellipse
        cv2.ellipse(overlay, (cx, cy), (ax, ay), angle, 0, 360, (255, 0, 255), 2)
    if contour is not None:
        cv2.drawContours(overlay, [contour], -1, (0, 255, 255), 1)

    out_bgr = cv2.cvtColor(output, cv2.COLOR_GRAY2BGR)
    if out_bgr.shape[:2] != src_bgr.shape[:2]:
        out_bgr = cv2.resize(out_bgr, (src_bgr.shape[1], src_bgr.shape[0]), interpolation=cv2.INTER_AREA)

    panel = np.concatenate([src_bgr, edge_bgr, overlay, out_bgr], axis=1)
    return panel


def main():
    parser = argparse.ArgumentParser(
        description="Create circle-focused OMR dataset: detect circle, crop around circle, mask outside circle."
    )
    parser.add_argument("--input-dir", default="data/kaggle_datasets/answer_binary")
    parser.add_argument("--output-dir", default="data/kaggle_datasets/answer_binary_circle_only")
    parser.add_argument("--pad-ratio", type=float, default=0.15)
    parser.add_argument("--pad-px", type=int, default=2)
    parser.add_argument(
        "--mode",
        default="circle_detect",
        choices=["circle_detect", "ellipse_centered", "contour_ellipse", "contour_circle_normalized"],
    )
    parser.add_argument("--ellipse-axis-ratio-x", type=float, default=0.72)
    parser.add_argument("--ellipse-axis-ratio-y", type=float, default=0.62)
    parser.add_argument("--debug-dir", default="data/circle_only_debug")
    parser.add_argument("--debug-limit-per-class", type=int, default=40)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    debug_dir = Path(args.debug_dir)
    ensure_clean_dir(output_dir)
    ensure_clean_dir(debug_dir)

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "splits": {},
        "methods": Counter(),
        "failures": 0,
        "total": 0,
    }

    for split in SPLITS:
        split_counts = defaultdict(int)
        for cls in CLASSES:
            src_dir = input_dir / split / cls
            if not src_dir.exists():
                continue
            files = sorted(src_dir.glob("*.png"))
            split_counts[f"{cls}_input"] = len(files)
            debug_saved = 0
            for src in files:
                dst = output_dir / split / cls / src.name
                result = process_image(
                    src,
                    dst,
                    pad_ratio=args.pad_ratio,
                    pad_px=args.pad_px,
                    mode=args.mode,
                    ellipse_axis_ratio_x=args.ellipse_axis_ratio_x,
                    ellipse_axis_ratio_y=args.ellipse_axis_ratio_y,
                )
                if not result["ok"]:
                    summary["failures"] += 1
                    continue
                summary["total"] += 1
                split_counts[f"{cls}_output"] += 1
                summary["methods"][result["method"]] += 1
                if debug_saved < args.debug_limit_per_class and result["debug"] is not None:
                    panel = make_debug_panel(
                        result["debug"]["gray"],
                        result["debug"]["circle"],
                        result["debug"]["output"],
                        ellipse=result["debug"].get("ellipse"),
                        contour=result["debug"].get("contour"),
                    )
                    dbg_name = f"{split}__{cls}__{result['method']}__{src.name}"
                    dbg_path = debug_dir / split / cls / dbg_name
                    dbg_path.parent.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(dbg_path), panel)
                    debug_saved += 1
        summary["splits"][split] = dict(split_counts)

    summary["methods"] = dict(summary["methods"])
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
