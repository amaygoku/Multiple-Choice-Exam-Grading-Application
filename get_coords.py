import cv2
import numpy as np
import os

def get_boxes(img_path):
    if not os.path.exists(img_path):
        print(f"File {img_path} not found")
        return
    img = cv2.imread(img_path)
    if img is None:
        print(f"Could not read {img_path}")
        return
    
    h_img, w_img = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    rects = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # Look for Rectangles
        if len(approx) == 4 and w > 20 and h > 10:
            rects.append({'x': x, 'y': y, 'w': w, 'h': h, 
                          'xn': x/w_img, 'yn': y/h_img, 'wn': w/w_img, 'hn': h/h_img})

    # Sort by Y then X
    rects.sort(key=lambda b: (b['y'] // 10, b['x']))
    
    print(f"Image Size: {w_img}x{h_img}")
    for i, r in enumerate(rects):
        print(f"Index {i}: x={r['x']}, y={r['y']}, w={r['w']}, h={r['h']} | Normalized: x={r['xn']:.4f}, y={r['yn']:.4f}, w={r['wn']:.4f}, h={r['hn']:.4f}")

if __name__ == '__main__':
    get_boxes('paper1.jpg')
