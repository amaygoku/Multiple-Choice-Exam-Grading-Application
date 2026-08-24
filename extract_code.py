import cv2
import numpy as np


GRID_ROWS = 10
GRID_PAD = 6
CORE_MARGIN_RATIO_X = 0.22
CORE_MARGIN_RATIO_Y = 0.22
EMPTY_SCORE_THRESHOLD = 0.10
TOP1_ADVANTAGE_THRESHOLD = 0.12
TOP1_RATIO_THRESHOLD = 1.18
MADE_EMPTY_SCORE_THRESHOLD = 0.16
MADE_TOP1_ADVANTAGE_THRESHOLD = 0.12
MADE_TOP1_RATIO_THRESHOLD = 1.08
MSSV_CORE_COUNT_DIVISOR = 1000.0
MADE_CORE_COUNT_DIVISOR = 900.0


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
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def normalize_code_grid(image):
    if image is None:
        return None, None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 5
    )

    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        pts = np.array([[0, 0], [gray.shape[1]-1, 0], [gray.shape[1]-1, gray.shape[0]-1], [0, gray.shape[0]-1]], dtype="float32")
    else:
        contour = max(cnts, key=cv2.contourArea)
        crop_area = gray.shape[0] * gray.shape[1]
        
        # If the detected contour is too small (broken border), fallback to using the whole crop
        if cv2.contourArea(contour) < crop_area * 0.50:
            pts = np.array([[0, 0], [gray.shape[1]-1, 0], [gray.shape[1]-1, gray.shape[0]-1], [0, gray.shape[0]-1]], dtype="float32")
        else:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2)
            else:
                rect = cv2.minAreaRect(contour)
                pts = cv2.boxPoints(rect)

    warped_gray = four_point_transform(gray, pts)
    from omr_pipeline import DEFAULT_OMR_CONFIG, normalize_paper_lighting
    warped_gray = normalize_paper_lighting(warped_gray, DEFAULT_OMR_CONFIG)
    warped_thresh = cv2.threshold(warped_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

    if warped_thresh.shape[1] <= 2 * GRID_PAD or warped_thresh.shape[0] <= 2 * GRID_PAD:
        # Fallback if warped area is tiny
        norm_gray = normalize_paper_lighting(gray, DEFAULT_OMR_CONFIG)
        norm_thresh = cv2.threshold(norm_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        crop_gray = norm_gray[GRID_PAD:norm_gray.shape[0] - GRID_PAD, GRID_PAD:norm_gray.shape[1] - GRID_PAD]
        crop_thresh = norm_thresh[GRID_PAD:norm_thresh.shape[0] - GRID_PAD, GRID_PAD:norm_thresh.shape[1] - GRID_PAD]
        return crop_gray, crop_thresh

    crop_gray = warped_gray[GRID_PAD:warped_gray.shape[0] - GRID_PAD, GRID_PAD:warped_gray.shape[1] - GRID_PAD]
    crop_thresh = warped_thresh[GRID_PAD:warped_thresh.shape[0] - GRID_PAD, GRID_PAD:warped_thresh.shape[1] - GRID_PAD]
    return crop_gray, crop_thresh


def compute_digit_cell_stats(crop_thresh, num_cols):
    cell_width = crop_thresh.shape[1] / num_cols
    cell_height = crop_thresh.shape[0] / GRID_ROWS
    stats = []

    for col_idx in range(num_cols):
        col_stats = []
        for row_idx in range(GRID_ROWS):
            y1 = int(row_idx * cell_height)
            y2 = int((row_idx + 1) * cell_height)
            x1 = int(col_idx * cell_width)
            x2 = int((col_idx + 1) * cell_width)

            cell = crop_thresh[y1:y2, x1:x2]
            if cell.size == 0:
                col_stats.append({"count": 0, "core_count": 0, "fill_ratio": 0.0})
                continue

            inner_dx = max(1, int(cell.shape[1] * CORE_MARGIN_RATIO_X))
            inner_dy = max(1, int(cell.shape[0] * CORE_MARGIN_RATIO_Y))
            ix1 = min(inner_dx, cell.shape[1] - 1)
            ix2 = max(ix1 + 1, cell.shape[1] - inner_dx)
            iy1 = min(inner_dy, cell.shape[0] - 1)
            iy2 = max(iy1 + 1, cell.shape[0] - inner_dy)
            core = cell[iy1:iy2, ix1:ix2]

            count = int(cv2.countNonZero(cell))
            core_count = int(cv2.countNonZero(core))
            core_area = max(core.shape[0] * core.shape[1], 1)
            fill_ratio = core_count / core_area

            col_stats.append(
                {
                    "count": count,
                    "core_count": core_count,
                    "fill_ratio": fill_ratio,
                }
            )
        stats.append(col_stats)

    return stats


def choose_digit_from_column(col_stats, num_cols):
    fill_ratios = [item["fill_ratio"] for item in col_stats]
    baseline = float(np.median(fill_ratios))
    if num_cols == 3:
        empty_score_threshold = MADE_EMPTY_SCORE_THRESHOLD
        top1_advantage_threshold = MADE_TOP1_ADVANTAGE_THRESHOLD
        top1_ratio_threshold = MADE_TOP1_RATIO_THRESHOLD
        core_count_divisor = MADE_CORE_COUNT_DIVISOR
    else:
        empty_score_threshold = EMPTY_SCORE_THRESHOLD
        top1_advantage_threshold = TOP1_ADVANTAGE_THRESHOLD
        top1_ratio_threshold = TOP1_RATIO_THRESHOLD
        core_count_divisor = MSSV_CORE_COUNT_DIVISOR

    scored = []
    for digit, item in enumerate(col_stats):
        normalized_fill = max(0.0, item["fill_ratio"] - baseline)
        score = normalized_fill + (item["core_count"] / core_count_divisor)
        scored.append(
            {
                "digit": digit,
                "count": item["count"],
                "core_count": item["core_count"],
                "fill_ratio": item["fill_ratio"],
                "baseline": baseline,
                "score": score,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    top1 = scored[0]
    top2 = scored[1] if len(scored) > 1 else {"score": 0.0}

    passes_empty = top1["score"] >= empty_score_threshold
    passes_advantage = (top1["score"] - top2["score"]) >= top1_advantage_threshold
    passes_ratio = top2["score"] <= 0 or top1["score"] >= top2["score"] * top1_ratio_threshold

    if passes_empty and (passes_advantage or passes_ratio):
        chosen_digit = str(top1["digit"])
    else:
        chosen_digit = "?"

    return chosen_digit, scored


ID_CLASSIFIER_PATH = "data/id_model.pth"
_id_classifier = None

def get_id_classifier():
    global _id_classifier
    if _id_classifier is None:
        import os
        # Check if model exists
        if os.path.exists(ID_CLASSIFIER_PATH):
            try:
                from answer_classifier_omr import TorchAnswerCellClassifier
                # Both models use the same torchvision small mobilenet model arch
                _id_classifier = TorchAnswerCellClassifier(ID_CLASSIFIER_PATH, image_size=96)
                print(f"[INFO] Loaded student ID/exam code classifier model from {ID_CLASSIFIER_PATH}")
            except Exception as e:
                print(f"[WARNING] Failed to load ID classifier model: {e}")
    return _id_classifier


def analyze_id_and_code_image_with_classifier(image, num_cols, classifier, threshold=None):
    if threshold is None:
        threshold = classifier.threshold if classifier is not None else 0.75
    crop_gray, crop_thresh = normalize_code_grid(image)
    if crop_gray is None or crop_thresh is None:
        return {
            "prediction": "",
            "normalized_gray": None,
            "normalized_thresh": None,
            "columns": [],
        }

    cell_width = crop_gray.shape[1] / num_cols
    cell_height = crop_gray.shape[0] / GRID_ROWS

    all_gray_cells = []
    for col_idx in range(num_cols):
        for row_idx in range(GRID_ROWS):
            y1 = int(row_idx * cell_height)
            y2 = int((row_idx + 1) * cell_height)
            x1 = int(col_idx * cell_width)
            x2 = int((col_idx + 1) * cell_width)

            if y2 <= y1 or x2 <= x1:
                cell = np.zeros((96, 96), dtype=np.uint8)
            else:
                cell = crop_gray[y1:y2, x1:x2]
            all_gray_cells.append(cell)

    probs = classifier.predict_probabilities(all_gray_cells)

    columns = []
    prediction = ""
    for col_idx in range(num_cols):
        col_scored = []
        for row_idx in range(GRID_ROWS):
            prob = probs[col_idx * GRID_ROWS + row_idx]
            col_scored.append({
                "digit": row_idx,
                "score": float(prob),
                "count": 0,
                "core_count": 0,
                "fill_ratio": float(prob),
            })
        
        # Sort desc to find the top prediction
        col_scored.sort(key=lambda item: item["score"], reverse=True)
        top1 = col_scored[0]
        if top1["score"] >= threshold:
            chosen_digit = str(top1["digit"])
        else:
            chosen_digit = "?"

        prediction += chosen_digit
        columns.append({
            "col": col_idx + 1,
            "chosen_digit": chosen_digit,
            "scored": col_scored,
        })

    return {
        "prediction": prediction,
        "normalized_gray": crop_gray,
        "normalized_thresh": crop_thresh,
        "columns": columns,
    }


def analyze_id_and_code_image(image, num_cols, use_classifier=True):
    if image is None:
        return {
            "prediction": "",
            "normalized_gray": None,
            "normalized_thresh": None,
            "columns": [],
        }

    if use_classifier:
        classifier = get_id_classifier()
        if classifier is not None:
            return analyze_id_and_code_image_with_classifier(image, num_cols, classifier)

    crop_gray, crop_thresh = normalize_code_grid(image)
    if crop_gray is None or crop_thresh is None:
        return {
            "prediction": "",
            "normalized_gray": None,
            "normalized_thresh": None,
            "columns": [],
        }

    grid_stats = compute_digit_cell_stats(crop_thresh, num_cols)
    prediction = ""
    columns = []
    for col_idx, col_stats in enumerate(grid_stats, start=1):
        chosen_digit, scored = choose_digit_from_column(col_stats, num_cols)
        prediction += chosen_digit
        columns.append(
            {
                "col": col_idx,
                "chosen_digit": chosen_digit,
                "scored": scored,
            }
        )

    return {
        "prediction": prediction,
        "normalized_gray": crop_gray,
        "normalized_thresh": crop_thresh,
        "columns": columns,
    }


def render_id_code_debug_image(normalized_gray, analysis, num_cols):
    if normalized_gray is None:
        return None

    canvas = cv2.cvtColor(normalized_gray, cv2.COLOR_GRAY2BGR)
    h, w = canvas.shape[:2]
    cell_width = w / num_cols
    cell_height = h / GRID_ROWS

    for col in analysis["columns"]:
        chosen_digit = col["chosen_digit"]
        chosen_idx = int(chosen_digit) if chosen_digit.isdigit() else None
        scored_by_digit = {item["digit"]: item for item in col["scored"]}

        for row_idx in range(GRID_ROWS):
            x1 = int((col["col"] - 1) * cell_width)
            x2 = int(col["col"] * cell_width)
            y1 = int(row_idx * cell_height)
            y2 = int((row_idx + 1) * cell_height)

            color = (0, 255, 0)
            thickness = 1
            if chosen_idx == row_idx:
                color = (0, 0, 255)
                thickness = 2

            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)

            item = scored_by_digit[row_idx]
            score_text = f"{item['score']:.2f}"
            cv2.putText(
                canvas,
                score_text,
                (x1 + 2, min(y2 - 4, y1 + 14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 0, 0),
                1,
                cv2.LINE_AA,
            )

        header = f"C{col['col']}={chosen_digit}"
        cv2.putText(
            canvas,
            header,
            (int((col["col"] - 1) * cell_width) + 2, 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )

    return canvas


def extract_id_and_code_image(image, num_cols, use_classifier=True):
    return analyze_id_and_code_image(image, num_cols, use_classifier=use_classifier)["prediction"]


def extract_id_and_code(image_path, num_cols, use_classifier=True):
    image = cv2.imread(image_path)
    if image is None:
        print(f"Could not read {image_path}")
        return ""
    return extract_id_and_code_image(image, num_cols, use_classifier=use_classifier)


if __name__ == "__main__":
    ma_de = extract_id_and_code("d:/OCR/crops/ma_de.png", 3)
    mssv = extract_id_and_code("d:/OCR/crops/mssv.png", 8)

    print("Ma de du doan:", ma_de)
    print("MSSV du doan:", mssv)
