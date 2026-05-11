import cv2
import numpy as np
from PIL import Image

def kmeans_binarize(img_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not read {img_path}")
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Pre-process: optional blur to reduce noise
    # gray = cv2.GaussianBlur(gray, (3, 3), 0)
    
    pixel_values = gray.reshape((-1, 1))
    pixel_values = np.float32(pixel_values)
    
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    k = 2
    _, labels, centers = cv2.kmeans(pixel_values, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    centers = np.uint8(centers)
    if centers[0] > centers[1]:
        bg_label, fg_label = 0, 1
    else:
        bg_label, fg_label = 1, 0
        
    res = np.zeros_like(labels, dtype=np.uint8)
    res[labels == bg_label] = 255
    res[labels == fg_label] = 0
    
    return res.reshape(gray.shape)

# Process ho_va_ten_refined.png
img_path = 'crops/ho_va_ten_refined.png'
bin_img = kmeans_binarize(img_path)
if bin_img is not None:
    cv2.imwrite('debug_ho_va_ten_bin.png', bin_img)
    print("Saved binarized image to debug_ho_va_ten_bin.png")

# Process image5.png for comparison
img_path_5 = 'images/image5.png'
bin_img_5 = kmeans_binarize(img_path_5)
if bin_img_5 is not None:
    cv2.imwrite('debug_image5_bin.png', bin_img_5)
    print("Saved binarized image to debug_image5_bin.png")
