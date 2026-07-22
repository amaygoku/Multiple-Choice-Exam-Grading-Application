from __future__ import annotations

import cv2
import numpy as np


def fourCornersSort(pts):
    """Sort corners: top-left, top-right, bot-right, bot-left."""
    diff = np.diff(pts, axis=1)
    summ = pts.sum(axis=1)
    return np.array(
        [
            pts[np.argmin(summ)],
            pts[np.argmin(diff)],
            pts[np.argmax(summ)],
            pts[np.argmax(diff)],
        ]
    )


def contourOffset(cnt, offset):
    """Offset contour."""
    cnt += offset
    cnt[cnt < 0] = 0
    return cnt


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
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array(
        [
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1],
        ],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


def align_document_image(image):
    """Detects the paper document and returns an aligned image."""
    if image is None:
        return None

    orig_h, orig_w = image.shape[:2]
    ratio = orig_h / 800.0
    res_w = int(orig_w / ratio)
    img_resized = cv2.resize(image, (res_w, 800))

    img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    img_bilateral = cv2.bilateralFilter(img_gray, 5, 75, 75)
    img_thresh = cv2.adaptiveThreshold(
        img_bilateral, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 4
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    img_blurred = cv2.morphologyEx(img_thresh, cv2.MORPH_OPEN, kernel)
    img_bordered = cv2.copyMakeBorder(img_blurred, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    edges = cv2.Canny(img_bordered, 10, 450)

    closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, hierarchy = cv2.findContours(closed_edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    height, width = edges.shape
    MAX_COUNTOUR_AREA = (width - 10) * (height - 10)
    maxAreaFound = MAX_COUNTOUR_AREA * 0.1
    pageContour = np.array([[[5, 5]], [[5, height - 5]], [[width - 5, height - 5]], [[width - 5, 5]]])

    for cnt in contours:
        perimeter = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.03 * perimeter, True)
        if (
            len(approx) == 4
            and cv2.isContourConvex(approx)
            and maxAreaFound < cv2.contourArea(approx) < MAX_COUNTOUR_AREA
        ):
            maxAreaFound = cv2.contourArea(approx)
            pageContour = approx

    pageContour = pageContour.reshape(4, 2)
    pageContour = fourCornersSort(pageContour)
    pageContour = contourOffset(pageContour, (-5, -5))
    ratio = image.shape[0] / 800
    sPoints = pageContour.dot(ratio)

    height = max(np.linalg.norm(sPoints[0] - sPoints[3]), np.linalg.norm(sPoints[1] - sPoints[2]))
    width = max(np.linalg.norm(sPoints[0] - sPoints[1]), np.linalg.norm(sPoints[2] - sPoints[3]))

    tPoints = np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float32)
    if sPoints.dtype != np.float32:
        sPoints = sPoints.astype(np.float32)

    M = cv2.getPerspectiveTransform(sPoints, tPoints)
    final_image = cv2.warpPerspective(image, M, (int(width), int(height)))
    return final_image


def align_document(image_path, output_path):
    """Detects the paper document and aligns it using perspective transform."""
    image = cv2.imread(image_path)
    final_image = align_document_image(image)
    if final_image is None:
        return False

    cv2.imwrite(output_path, final_image)
    return True

