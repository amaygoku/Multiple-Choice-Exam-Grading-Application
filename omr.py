import cv2
import numpy as np

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
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def process_omr(image_path):
    print(f"\nProcessing {image_path}...")
    image = cv2.imread(image_path)
    if image is None:
        print("Could not read image.")
        return

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("No contours found.")
        return

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    docCnt = None

    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        if len(approx) == 4:
            docCnt = approx
            break

    if docCnt is None:
        print("Could not find a 4-point bounding box. Using bounding rect of largest contour.")
        x, y, w, h = cv2.boundingRect(contours[0])
        docCnt = np.array([[[x, y]], [[x+w, y]], [[x+w, y+h]], [[x, y+h]]])

    # Perspective Transform
    warped_color = four_point_transform(image, docCnt.reshape(4, 2))
    warped = four_point_transform(gray, docCnt.reshape(4, 2))

    # Preprocessing (Binarization)
    thresh = cv2.threshold(warped, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    cv2.imwrite(image_path.replace(".png", "_thresh.png"), thresh)

    # Find Contours
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    questionCnts = []
    
    output = warped_color.copy()
    
    import statistics
    for c in cnts:
        (x, y, w, h) = cv2.boundingRect(c)
        ar = w / float(h)
        # Filter bubbles by shape and size
        if 13 <= w <= 45 and 13 <= h <= 45 and 0.7 <= ar <= 1.3:
            questionCnts.append(c)
            cv2.rectangle(output, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
    cv2.imwrite(image_path.replace(".png", "_debug.png"), output)
    print(f"Found {len(questionCnts)} potential bubbles.")
    
    if not questionCnts:
        return
        
    # Sort bubbles from top to bottom
    questionCnts = sorted(questionCnts, key=lambda c: cv2.boundingRect(c)[1])
    
    # We should cluster Y coordinates to find rows
    # A simple hierarchical clustering logic:
    rows = []
    current_row = [questionCnts[0]]
    # use the median height as heuristic
    h_heur = statistics.median([cv2.boundingRect(c)[3] for c in questionCnts])
    
    for c in questionCnts[1:]:
        y = cv2.boundingRect(c)[1]
        last_y = cv2.boundingRect(current_row[-1])[1]
        # if the y distance is small, add to current row
        if abs(y - last_y) < h_heur * 0.8: 
            current_row.append(c)
        else:
            rows.append(current_row)
            current_row = [c]
    rows.append(current_row)
    
    print(f"Detected {len(rows)} rows.")
    
    answers = []
    # Sort column
    for i, row in enumerate(rows):
        row = sorted(row, key=lambda c: cv2.boundingRect(c)[0])
        
        bubbled = None
        max_pixels = -1
        
        for j, c in enumerate(row):
            mask = np.zeros(thresh.shape, dtype="uint8")
            cv2.drawContours(mask, [c], -1, 255, -1)
            
            mask = cv2.bitwise_and(thresh, thresh, mask=mask)
            total = cv2.countNonZero(mask)
            
            if total > max_pixels:
                max_pixels = total
                bubbled = j
                
        choices = ['A', 'B', 'C', 'D', 'E']
        choice = choices[bubbled] if bubbled is not None and bubbled < len(choices) else '?'
        
        # We can draw the bubbled choice in red
        if bubbled is not None and bubbled < len(row):
            bc = row[bubbled]
            (bx, by, bw, bh) = cv2.boundingRect(bc)
            cv2.circle(output, (bx + bw//2, by + bh//2), bw//2, (0, 0, 255), 2)
            cv2.putText(output, f"{i+1}{choice}", (bx - 30, by + bh//2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            
        print(f"Question {i + 1} (len {len(row)}): Choice {choice}")
        answers.append(choice)
        
    cv2.imwrite(image_path.replace(".png", "_result.png"), output)

if __name__ == "__main__":
    for f in ["answer_1.png", "answer_2.png", "answer_3.png"]:
        process_omr(f"d:/OCR/crops/{f}")
