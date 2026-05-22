import os
import sys
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from answer_classifier_omr import TorchAnswerCellClassifier, decode_answer_probabilities
from extract_code import get_id_classifier, normalize_code_grid
from omr_pipeline import extract_answer_grid_data, DEFAULT_OMR_CONFIG, get_answer_classifier

def inspect_answer_crop(crop_path, classifier, out_dir):
    img = cv2.imread(str(crop_path))
    if img is None:
        return
    grid = extract_answer_grid_data(img, config=DEFAULT_OMR_CONFIG)
    if grid is None:
        return

    all_gray_cells = []
    index_map = []
    for row_idx, row_cells in enumerate(grid["cells"]):
        for col_idx, cell_info in enumerate(row_cells):
            all_gray_cells.append(cell_info["gray"])
            index_map.append((row_idx, col_idx))

    probs = classifier.predict_probabilities(all_gray_cells)
    
    for idx, (row_idx, col_idx) in enumerate(index_map):
        prob = probs[idx]
        cell_img = all_gray_cells[idx]
        if cell_img is None or cell_img.size == 0:
            continue
        
        # Save cell crops that have high/low confidence or are interesting
        # We can name them with their probability
        prob_str = f"{prob:.2f}"
        if prob_str in ["0.00", "1.00", "0.01", "0.99"]:
            name = f"ans_{crop_path.parent.parent.name}_{crop_path.stem}_row{row_idx+1}_col{col_idx+1}_p{prob_str}.png"
            cv2.imwrite(str(out_dir / name), cell_img)
            print(f"Saved {name} with shape {cell_img.shape}")

def inspect_id_code_crop(crop_path, classifier, num_cols, out_dir):
    img = cv2.imread(str(crop_path))
    if img is None:
        return
    crop_gray, crop_thresh = normalize_code_grid(img)
    if crop_gray is None or crop_thresh is None:
        return

    cell_width = crop_gray.shape[1] / num_cols
    cell_height = crop_gray.shape[0] / 10

    all_gray_cells = []
    index_map = []
    for col_idx in range(num_cols):
        for row_idx in range(10):
            y1 = int(row_idx * cell_height)
            y2 = int((row_idx + 1) * cell_height)
            x1 = int(col_idx * cell_width)
            x2 = int((col_idx + 1) * cell_width)

            if y2 <= y1 or x2 <= x1:
                cell = np.zeros((96, 96), dtype=np.uint8)
            else:
                cell = crop_gray[y1:y2, x1:x2]
            all_gray_cells.append(cell)
            index_map.append((row_idx, col_idx))

    probs = classifier.predict_probabilities(all_gray_cells)
    for idx, (row_idx, col_idx) in enumerate(index_map):
        prob = probs[idx]
        cell_img = all_gray_cells[idx]
        prob_str = f"{prob:.2f}"
        if prob_str in ["0.00", "1.00", "0.01", "0.99"]:
            name = f"idcode_{crop_path.parent.parent.name}_{crop_path.stem}_row{row_idx}_col{col_idx+1}_p{prob_str}.png"
            cv2.imwrite(str(out_dir / name), cell_img)
            print(f"Saved {name} with shape {cell_img.shape}")

def main():
    ans_classifier = get_answer_classifier()
    id_classifier = get_id_classifier()
    
    if ans_classifier is None or id_classifier is None:
        print("Error: Could not load classifiers!")
        return

    out_dir = Path("d:/OCR/scratch/inspected_cells")
    out_dir.mkdir(parents=True, exist_ok=True)

    results_dir = Path("d:/OCR/results")
    for subdir in results_dir.iterdir():
        if not subdir.is_dir() or subdir.name in ["crops", "inspected_cells"]:
            continue
        
        crops_dir = subdir / "crops"
        if not crops_dir.exists():
            continue
        
        print(f"Processing subdir: {subdir.name}")
        for crop_file in ["answer_1.png", "answer_2.png", "answer_3.png"]:
            p = crops_dir / crop_file
            if p.exists():
                inspect_answer_crop(p, ans_classifier, out_dir)
                
        p_ma_de = crops_dir / "ma_de.png"
        if p_ma_de.exists():
            inspect_id_code_crop(p_ma_de, id_classifier, 3, out_dir)
            
        p_mssv = crops_dir / "mssv.png"
        if p_mssv.exists():
            inspect_id_code_crop(p_mssv, id_classifier, 8, out_dir)

if __name__ == "__main__":
    main()
