import nbformat as nbf

notebook_path = r'd:\OCR\viet_Tay.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = nbf.read(f, as_version=4)

# Define the imports cell
imports_code = """import vietocr
from vietocr.tool.predictor import Predictor
from PIL import Image
import matplotlib.pyplot as plt
from vietocr.tool.config import Cfg
import cv2
import numpy as np
from skimage import io, color, filters
"""

# Define the binarization cell (K-means + Sauvola)
binarization_code = """# 1. K-means clustering (Loại bỏ background y hệt imgtxtenh)
# Phương pháp này phân cụm pixel thành 2 nhóm: Chữ (đen) và Nền (trắng)
def kmeans_binarize(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Chuyển dữ liệu về float32 cho K-means
    pixel_values = gray.reshape((-1, 1))
    pixel_values = np.float32(pixel_values)
    
    # Chạy K-means (K=2)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    k = 2
    _, labels, centers = cv2.kmeans(pixel_values, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # Xác định cụm nào là nền (sáng hơn)
    centers = np.uint8(centers)
    if centers[0] > centers[1]:
        bg_label, fg_label = 0, 1
    else:
        bg_label, fg_label = 1, 0
        
    # Tạo ảnh kết quả: Nền=255, Chữ=0
    res = np.zeros_like(labels, dtype=np.uint8)
    res[labels == bg_label] = 255
    res[labels == fg_label] = 0
    
    return res.reshape(gray.shape)

# Thực hiện làm sạch ảnh
input_file = 'huy1.png'
cleaned_img_np = kmeans_binarize(input_file)

if cleaned_img_np is not None:
    # CHUYỂN ĐỔI SANG PIL IMAGE ĐỂ VIETOCR XỬ LÝ
    cleaned_img_pil = Image.fromarray(cleaned_img_np).convert('RGB')
    cleaned_img_pil.save('output.png')

    # Hiển thị kết quả so sánh
    plt.figure(figsize=(10, 5))
    plt.imshow(cleaned_img_np, cmap='gray')
    plt.title("K-means Cleaned Image (imgtxtenh style)")
    plt.show()
else:
    print(f"Error: Could not read {input_file}")
"""

# Define the config cell
config_code = """config = Cfg.load_config_from_name('vgg_seq2seq')
config['weights'] = './seq2seqocr.pth'
config['cnn']['pretrained']=False
config['device'] = 'cpu'

detector = Predictor(config)
"""

# Define the prediction cell
prediction_code = """# Dự đoán kết quả OCR từ ảnh đã được làm sạch
if 'cleaned_img_pil' in locals():
    s = detector.predict(cleaned_img_pil)
    print("Kết quả OCR:", s)
    
    # Kiểm tra xem detector.predict(cleaned_img_pil) có lỗi không
    # Nếu lỗi 'numpy.ndarray' object has no attribute 'convert' thì do ta truyền ndarray vào
    # Nhưng ở đây ta đã chuyển cleaned_img_pil sang PIL Image rồi.
else:
    print("Vui lòng chạy cell binarization trước.")
"""

# Rebuild the notebook structure
nb.cells = [
    nbf.v4.new_code_cell(imports_code),
    nbf.v4.new_code_cell(binarization_code),
    nbf.v4.new_code_cell(config_code),
    nbf.v4.new_code_cell(prediction_code)
]

with open(notebook_path, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print("Notebook rebuilt successfully with fixes.")
