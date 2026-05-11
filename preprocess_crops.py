import cv2
import numpy as np
import os
from detect_paper import four_point_transform

def improve_text_crop(img_path, output_path):
    # Load original image
    img = cv2.imread(img_path)
    if img is None:
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Binary threshold to find the box
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    
    # 1. Find the largest rectangle (the box)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Find the largest contour by area
        largest_cnt = max(contours, key=cv2.contourArea)
        
        peri = cv2.arcLength(largest_cnt, True)
        approx = cv2.approxPolyDP(largest_cnt, 0.02 * peri, True)
        
        if len(approx) == 4:
            warped = four_point_transform(img, approx.reshape(4, 2))
        else:
            rect = cv2.minAreaRect(largest_cnt)
            box = cv2.boxPoints(rect)
            box = np.int32(box)
            warped = four_point_transform(img, box.reshape(4, 2))
            
        # 2. Crop slightly inside the detected box to remove boundaries
        margin = 10
        #extra_top = 5
        h, w = warped.shape[:2]
        
        iy = margin
        ih = h - 2*margin
        ix = margin
        iw = w - 2*margin
        
        if iw > 0 and ih > 0:
            crop = warped[iy:iy+ih, ix:ix+iw]
            
            # 3. Enhance look: background cleanup
            # convert to LAB to equalize luminance
            lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            # Clip L channel to remove light grays (make background white)
            l = cv2.normalize(l, None, 0, 255, cv2.NORM_MINMAX)
            # Simple contrast stretch
            l = cv2.addWeighted(l, 1.2, l, 0, -30) # Adjust alpha/beta
            
            final_lab = cv2.merge((l, a, b))
            result = cv2.cvtColor(final_lab, cv2.COLOR_LAB2BGR)
            
            cv2.imwrite(output_path, result)
            print(f"Saved refined text crop to {output_path}")
            return

    # If no box found, just save the original (or simple cleaning)
    cv2.imwrite(output_path, img)

if __name__ == "__main__":
    fields = ['ho_va_ten', 'lop', 'mon']
    for field in fields:
        input_p = f'D:\\OCR\\crops\\{field}.png'
        if os.path.exists(input_p):
            improve_text_crop(input_p, f'D:\\OCR\\crops\\{field}_refined.png')
