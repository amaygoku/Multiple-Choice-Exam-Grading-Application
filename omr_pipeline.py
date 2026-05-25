from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass
class OMRConfig:
    num_rows: int = 15
    num_choices: int = 4
    normalized_width: int = 620
    normalized_height: int = 990
    crop_pad_top: int = 1
    crop_pad_bottom: int = 5
    crop_pad_left: int = 8
    crop_pad_right: int = 15
    cell_pad_top: int = 3
    cell_pad_bottom: int = 3
    cell_pad_left: int = 4
    cell_pad_right: int = 4
    q_col_ratio: float = 0.15
    baseline_ratio: float = 1.05
    baseline_offset: int = 20
    row_baseline_ratio: float = 1.15
    row_baseline_offset: int = 55
    use_perspective: bool = True
    alignment_block_size: int = 31
    alignment_c: int = 9
    alignment_close_kernel: int = 5
    alignment_min_area_ratio: float = 0.12
    background_blur_ksize: int = 31
    binary_block_size: int = 31
    binary_c: int = 7
    fill_weight: float = 0.5
    ink_weight: float = 0.4
    empty_score_threshold: float = 0.05
    top_margin_threshold: float = 0.035
    second_ratio_threshold: float = 0.55
    third_ratio_threshold: float = 0.55
    extra_margin_threshold: float = 0.015
    use_lighting_normalization: bool = True
    lighting_sigma: float = 25.0
    lighting_gain: float = 180.0
    min_aspect_ratio: float = 0.35
    max_aspect_ratio: float = 0.9


DEFAULT_OMR_CONFIG = OMRConfig()

OMR_CONFIG_V2 = OMRConfig(
    crop_pad_top=6,
    crop_pad_bottom=6,
    crop_pad_left=9,
    crop_pad_right=11,
    q_col_ratio=0.0,
    normalized_width=330,
    min_aspect_ratio=0.22,
    max_aspect_ratio=0.55,
    empty_score_threshold=0.22
)



def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))
    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def threshold_omr_image(gray, config):
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]


def normalize_paper_lighting(gray, config):
    # Estimate smooth illumination field, then normalize to reduce shadows/vignetting.
    sigma = max(3.0, float(getattr(config, "lighting_sigma", 25.0)))
    bg = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    gain = float(getattr(config, "lighting_gain", 180.0))
    norm = (gray.astype(np.float32) / (bg.astype(np.float32) + 1e-6)) * gain
    return np.clip(norm, 0, 255).astype(np.uint8)


def normalize_answer_area(image, config, preproc_debug=None):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if config.use_lighting_normalization:
        gray = normalize_paper_lighting(gray, config)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        config.alignment_block_size,
        config.alignment_c,
    )

    # Clear question numbers on the left and header text "A B C D" at the top of layout v2 answer crops
    if config.normalized_width == 330:
        h_img, w_img = binary.shape[:2]
        
        # 1. Clear question numbers on the left using vertical projection
        col_sums = np.sum(binary, axis=0) // 255
        border_col = -1
        search_w = min(w_img, 45)
        thresh_val = int(h_img * 0.40)
        for col in range(3, search_w):
            if col_sums[col] > thresh_val:
                border_col = col
                break
        if border_col > 1:
            binary[:, :border_col - 1] = 0

        # 2. Clear letters "A B C D" at the top using horizontal projection
        row_sums = np.sum(binary, axis=1) // 255
        border_row = -1
        search_h = min(h_img, 50)
        thresh_w = int(w_img * 0.50)
        for row in range(3, search_h):
            if row_sums[row] > thresh_w:
                border_row = row
                break
        if border_row > 1:
            binary[:border_row - 1, :] = 0

    kernel_size = max(3, int(config.alignment_close_kernel))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    merged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    merged = cv2.dilate(merged, kernel, iterations=1)

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = image.shape[0] * image.shape[1] * config.alignment_min_area_ratio
    candidate = None
    candidate_area = 0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if h <= 0 or w <= 0:
            continue
        aspect_ratio = w / float(h)
        min_aspect = float(getattr(config, "min_aspect_ratio", 0.35))
        max_aspect = float(getattr(config, "max_aspect_ratio", 0.9))
        if not min_aspect <= aspect_ratio <= max_aspect:
            continue
        if area > candidate_area:
            candidate = contour
            candidate_area = area

    if candidate is None:
        points = cv2.findNonZero(merged)
        if points is None:
            thresh = threshold_omr_image(gray, config)
            if preproc_debug is not None:
                preproc_debug["gray"] = gray.copy()
                preproc_debug["thresholded"] = thresh.copy()
            return image.copy(), thresh, False
        rect = cv2.minAreaRect(points)
        pts = cv2.boxPoints(rect)
    else:
        peri = cv2.arcLength(candidate, True)
        approx = cv2.approxPolyDP(candidate, 0.02 * peri, True)
        if len(approx) == 4:
            pts = approx.reshape(4, 2)
        else:
            rect = cv2.minAreaRect(candidate)
            pts = cv2.boxPoints(rect)

    warped = four_point_transform(image, np.array(pts, dtype="float32"))
    normalized = cv2.resize(
        warped,
        (config.normalized_width, config.normalized_height),
        interpolation=cv2.INTER_CUBIC,
    )
    normalized_gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
    if preproc_debug is not None:
        preproc_debug["gray"] = normalized_gray.copy()
    if config.use_lighting_normalization:
        normalized_gray = normalize_paper_lighting(normalized_gray, config)
        if preproc_debug is not None:
            preproc_debug["lighting_normalized"] = normalized_gray.copy()
    normalized_thresh = threshold_omr_image(normalized_gray, config)
    if preproc_debug is not None:
        preproc_debug["thresholded"] = normalized_thresh.copy()
    return normalized, normalized_thresh, True


def prepare_omr_canvas(image, config, preproc_debug=None):
    if image is None:
        return None, None, False

    if config.use_perspective:
        normalized, normalized_thresh, aligned = normalize_answer_area(image, config, preproc_debug=preproc_debug)
        return normalized, normalized_thresh, aligned

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if preproc_debug is not None:
        preproc_debug["gray"] = gray.copy()
    if config.use_lighting_normalization:
        gray = normalize_paper_lighting(gray, config)
        if preproc_debug is not None:
            preproc_debug["lighting_normalized"] = gray.copy()
    thresh = threshold_omr_image(gray, config)
    if preproc_debug is not None:
        preproc_debug["thresholded"] = thresh.copy()
    return image.copy(), thresh, False


def compute_choice_scores(tots, col_baselines, config):
    row_min = min(tots)
    scores = []
    for idx, val in enumerate(tots):
        row_signal = max(0.0, (val - row_min) / max(row_min, 1))
        col_signal = max(0.0, (val - col_baselines[idx]) / max(col_baselines[idx], 1))
        score = config.fill_weight * col_signal + config.ink_weight * row_signal
        scores.append(
            {
                "idx": idx,
                "value": val,
                "row_signal": row_signal,
                "col_signal": col_signal,
                "score": score,
            }
        )
    scores.sort(key=lambda item: item["score"], reverse=True)
    return row_min, scores


def pick_bubbled_indices(tots, col_baselines, config):
    row_min, ranked_scores = compute_choice_scores(tots, col_baselines, config)
    picked = []
    top = ranked_scores[0]
    if top["score"] < config.empty_score_threshold:
        return picked, row_min, ranked_scores

    picked.append(top["idx"])
    for rank in range(1, len(ranked_scores)):
        candidate = ranked_scores[rank]
        if candidate["score"] < config.empty_score_threshold:
            continue
        ratio_threshold = config.second_ratio_threshold if rank == 1 else config.third_ratio_threshold
        if candidate["score"] + config.extra_margin_threshold < top["score"] * ratio_threshold:
            continue
        picked.append(candidate["idx"])

    picked.sort()
    return picked, row_min, ranked_scores


def extract_answer_grid_data(image, config=None, preproc_debug=None):
    config = config or DEFAULT_OMR_CONFIG
    if image is None:
        return None

    output, working_thresh, aligned = prepare_omr_canvas(image, config, preproc_debug=preproc_debug)
    if output is None or working_thresh is None:
        return None

    top = config.crop_pad_top
    bottom = config.crop_pad_bottom
    left = config.crop_pad_left
    right = config.crop_pad_right
    if working_thresh.shape[1] <= left + right or working_thresh.shape[0] <= top + bottom:
        return None

    normalized_gray = cv2.cvtColor(output, cv2.COLOR_BGR2GRAY)
    crop_gray = normalized_gray[top:normalized_gray.shape[0] - bottom, left:normalized_gray.shape[1] - right]
    crop_thresh = working_thresh[top:working_thresh.shape[0] - bottom, left:working_thresh.shape[1] - right]
    row_height = crop_thresh.shape[0] / config.num_rows
    start_x = int(crop_thresh.shape[1] * config.q_col_ratio)
    cell_width = (crop_thresh.shape[1] - start_x) / config.num_choices

    cells = []
    for row in range(config.num_rows):
        row_cells = []
        for col in range(config.num_choices):
            y1 = int(row * row_height) + config.cell_pad_top
            y2 = int((row + 1) * row_height) - config.cell_pad_bottom
            x1 = start_x + int(col * cell_width) + config.cell_pad_left
            x2 = start_x + int((col + 1) * cell_width) - config.cell_pad_right

            if y2 <= y1 or x2 <= x1:
                row_cells.append({"gray": None, "binary": None, "bbox": (x1, y1, x2, y2)})
                continue

            row_cells.append(
                {
                    "gray": crop_gray[y1:y2, x1:x2],
                    "binary": crop_thresh[y1:y2, x1:x2],
                    "bbox": (x1, y1, x2, y2),
                }
            )
        cells.append(row_cells)

    return {
        "aligned": aligned,
        "output_bgr": output,
        "normalized_gray": normalized_gray,
        "working_thresh": working_thresh,
        "crop_gray": crop_gray,
        "crop_thresh": crop_thresh,
        "cells": cells,
        "top": top,
        "left": left,
        "row_height": row_height,
        "cell_width": cell_width,
        "start_x": start_x,
    }


ANSWER_CLASSIFIER_PATH = "data/answer_binary_model.pth"
_answer_classifier = None

def get_answer_classifier():
    global _answer_classifier
    if _answer_classifier is None:
        import os
        if os.path.exists(ANSWER_CLASSIFIER_PATH):
            try:
                from answer_classifier_omr import TorchAnswerCellClassifier
                _answer_classifier = TorchAnswerCellClassifier(ANSWER_CLASSIFIER_PATH, image_size=96)
                print(f"[INFO] Loaded answer classifier model from {ANSWER_CLASSIFIER_PATH}")
            except Exception as e:
                print(f"[WARNING] Failed to load answer classifier model: {e}")
    return _answer_classifier


def process_omr_image(
    image,
    start_question_idx=1,
    num_choices=4,
    debug=False,
    config=None,
    use_classifier=True,
    preproc_debug=None,
):
    config = config or DEFAULT_OMR_CONFIG
    num_choices = config.num_choices if config else num_choices

    if image is None:
        return [], None

    if use_classifier:
        classifier = get_answer_classifier()
        if classifier is not None:
            from answer_classifier_omr import process_answer_crop_with_classifier
            answers, output, _ = process_answer_crop_with_classifier(
                image, classifier, config=config, threshold=classifier.threshold, preproc_debug=preproc_debug
            )
            return answers, output

    grid = extract_answer_grid_data(image, config=config, preproc_debug=preproc_debug)
    if grid is None:
        return [], None
    output = grid["output_bgr"]
    crop_t = grid["crop_thresh"]
    top = grid["top"]
    left = grid["left"]
    num_rows = config.num_rows
    row_height = grid["row_height"]
    start_x = grid["start_x"]
    cell_width = grid["cell_width"]
    choices = ["A", "B", "C", "D", "E", "F"][:num_choices]

    all_tots = []
    for row in range(num_rows):
        tots = []
        for col in range(num_choices):
            cell_info = grid["cells"][row][col]
            x1, y1, x2, y2 = cell_info["bbox"]
            if cell_info["binary"] is None:
                tots.append(0)
                continue

            tots.append(cv2.countNonZero(cell_info["binary"]))
            cv2.rectangle(output, (left + x1, top + y1), (left + x2, top + y2), (0, 255, 0), 2)
        all_tots.append(tots)

    cell_area = cell_width * row_height
    max_baseline = int(cell_area * 0.16)

    col_baselines = []
    for col in range(num_choices):
        col_vals = sorted(all_tots[row][col] for row in range(num_rows))
        # Use 25th percentile (len // 4) instead of median (len // 2)
        # to prevent baseline escalation when a choice is chosen very frequently.
        # Cap the baseline to prevent escalation in extreme cases (e.g. 100% selection of one option).
        val_25th = col_vals[len(col_vals) // 4]
        col_baselines.append(min(max_baseline, val_25th))

    answers = []
    for row in range(num_rows):
        tots = all_tots[row]
        bubbled_indices, row_min, ranked_scores = pick_bubbled_indices(tots, col_baselines, config)

        choice_str = "".join(choices[idx] for idx in bubbled_indices) if bubbled_indices else ""
        answers.append(choice_str)

        for idx in bubbled_indices:
            jx = start_x + int((idx + 0.5) * cell_width)
            cv2.putText(
                output,
                choices[idx],
                (left + jx - 5, top + int(row * row_height) + int(row_height / 2) + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

        if debug:
            score_debug = [(choices[item["idx"]], round(item["score"], 3)) for item in ranked_scores]
            print(
                f"  + Cau {start_question_idx + row}: Dap an {choice_str if choice_str else 'Chua to'} "
                f"(Tots: {tots}, row_min={row_min}, scores={score_debug})"
            )

    return answers, output


def process_omr(image_path, start_question_idx=1, num_choices=4, use_classifier=True):
    print(f"\n[{image_path}]")
    image = cv2.imread(image_path)
    answers, output = process_omr_image(
        image,
        start_question_idx=start_question_idx,
        num_choices=num_choices,
        debug=True,
        config=DEFAULT_OMR_CONFIG,
        use_classifier=use_classifier,
    )
    if output is not None:
        cv2.imwrite(image_path.replace(".png", "_result.png"), output)
        print(f"-> Da luu anh ket qua: {image_path.replace('.png', '_result.png')}")
    return answers


def omr_config_to_dict(config=None):
    return asdict(config or DEFAULT_OMR_CONFIG)


if __name__ == "__main__":
    start_idx = 1
    for f in ["answer_1.png", "answer_2.png", "answer_3.png"]:
        ans = process_omr(f"d:/OCR/crops/{f}", start_question_idx=start_idx)
        if ans:
            start_idx += len(ans)
