from pathlib import Path

import cv2
import numpy as np

from omr_pipeline import DEFAULT_OMR_CONFIG, extract_answer_grid_data


CHOICES = ["A", "B", "C", "D"]


class TorchAnswerCellClassifier:
    def __init__(self, weight_path, image_size=96, threshold=0.75, device=None, circle_only=None):
        self.weight_path = str(weight_path)
        self.image_size = int(image_size)
        self.threshold = float(threshold)
        if circle_only is None:
            self.circle_only = "circle_only" in self.weight_path.lower()
        else:
            self.circle_only = bool(circle_only)

        import torch
        import torch.nn as nn
        from torchvision import models

        self.torch = torch
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        model = models.mobilenet_v3_small(weights=None)
        in_features = model.classifier[0].in_features
        model.classifier = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(512, 1),
        )

        state_dict = torch.load(self.weight_path, map_location=self.device)
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()
        self.model = model

        self.mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 3, 1, 1).to(self.device)
        self.std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 3, 1, 1).to(self.device)

    def _preprocess_batch(self, gray_cells):
        # Match val/test transform used in training:
        # Grayscale(3) -> Resize -> ToTensor -> Normalize(ImageNet).
        batch = []
        for cell in gray_cells:
            if cell is None or cell.size == 0:
                cell = np.zeros((self.image_size, self.image_size), dtype=np.uint8)
            else:
                if self.circle_only:
                    circle, _ = detect_circle(cell)
                    if circle is not None:
                        cell = crop_and_mask(cell, circle, pad_ratio=0.15, pad_px=2)
                cell = cv2.resize(cell, (self.image_size, self.image_size), interpolation=cv2.INTER_LINEAR)
            rgb = cv2.cvtColor(cell, cv2.COLOR_GRAY2RGB).astype(np.float32) / 255.0
            rgb = np.transpose(rgb, (2, 0, 1))
            batch.append(rgb)

        batch = np.stack(batch, axis=0)
        tensor = self.torch.from_numpy(batch).to(self.device)
        tensor = (tensor - self.mean) / self.std
        return tensor

    def predict_probabilities(self, gray_cells):
        if not gray_cells:
            return []
        with self.torch.no_grad():
            inputs = self._preprocess_batch(gray_cells)
            logits = self.model(inputs)
            probs = self.torch.sigmoid(logits).view(-1).detach().cpu().numpy().tolist()
        return probs


def decode_answer_probabilities(row_probs, threshold=0.75, second_ratio=0.55, third_ratio=0.55, extra_margin=0.015):
    ranked = sorted(enumerate(row_probs), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < threshold:
        return "", ranked

    picked = [ranked[0][0]]
    top_prob = ranked[0][1]
    for rank, ratio in ((1, second_ratio), (2, third_ratio)):
        if rank >= len(ranked):
            break
        idx, prob = ranked[rank]
        if prob < threshold:
            continue
        if prob + extra_margin < top_prob * ratio:
            continue
        picked.append(idx)

    picked.sort()
    return "".join(CHOICES[idx] for idx in picked), ranked


def process_answer_crop_with_classifier(image, classifier, config=None, threshold=None, preproc_debug=None):
    config = config or DEFAULT_OMR_CONFIG
    grid = extract_answer_grid_data(image, config=config, preproc_debug=preproc_debug)
    if grid is None:
        return [], None, []

    output = grid["output_bgr"].copy()
    all_gray_cells = []
    index_map = []
    for row_idx, row_cells in enumerate(grid["cells"]):
        for col_idx, cell_info in enumerate(row_cells):
            all_gray_cells.append(cell_info["gray"])
            index_map.append((row_idx, col_idx))

    probs = classifier.predict_probabilities(all_gray_cells)
    prob_grid = [[0.0 for _ in range(config.num_choices)] for _ in range(config.num_rows)]
    for prob, (row_idx, col_idx) in zip(probs, index_map):
        prob_grid[row_idx][col_idx] = float(prob)

    top = grid["top"]
    left = grid["left"]
    answers = []
    details = []
    score_threshold = classifier.threshold if threshold is None else threshold
    for row_idx, row_cells in enumerate(grid["cells"]):
        row_probs = prob_grid[row_idx]
        answer, ranked = decode_answer_probabilities(
            row_probs,
            threshold=score_threshold,
            second_ratio=config.second_ratio_threshold,
            third_ratio=config.third_ratio_threshold,
            extra_margin=config.extra_margin_threshold,
        )
        answers.append(answer)
        details.append({"row": row_idx + 1, "probs": row_probs, "ranked": ranked, "answer": answer})

        for col_idx, cell_info in enumerate(row_cells):
            x1, y1, x2, y2 = cell_info["bbox"]
            color = (0, 255, 0)
            if CHOICES[col_idx] in answer:
                color = (0, 0, 255)
            cv2.rectangle(output, (left + x1, top + y1), (left + x2, top + y2), color, 2)
            cv2.putText(
                output,
                f"{row_probs[col_idx]:.2f}",
                (left + x1 + 2, top + min(y2 - 4, y1 + 14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 0, 0),
                1,
                cv2.LINE_AA,
            )

    return answers, output, details


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
