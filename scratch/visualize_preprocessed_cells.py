import os
import sys
from pathlib import Path
import cv2
import numpy as np

# Add parent directory to path to import local modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omr_pipeline import extract_answer_grid_data, DEFAULT_OMR_CONFIG

def main():
    image_path = r"D:\OCR\results\96f7e6712fda4574a9e9ca59bbcbbf74\omr\answer_3_result.png"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} does not exist!")
        return

    # Load image
    img = cv2.imread(image_path)
    print(f"Loaded image {image_path} with shape {img.shape}")

    # Extract cells using the pipeline logic
    grid = extract_answer_grid_data(img, config=DEFAULT_OMR_CONFIG)
    if grid is None:
        print("Error: Could not extract answer grid data!")
        return

    cells = grid["cells"]  # list of 15 rows, each containing 4 columns
    num_rows = len(cells)
    num_cols = len(cells[0])
    cell_size = 96
    margin = 4
    
    # We will create a grid image with row numbers and column letters
    # Left column for question number labels (width: 100px)
    # Top row for choices labels A, B, C, D (height: 50px)
    label_w = 100
    label_h = 50
    
    grid_w = label_w + num_cols * (cell_size + margin)
    grid_h = label_h + num_rows * (cell_size + margin)
    
    # Background canvas: Dark gray
    canvas = np.ones((grid_h, grid_w, 3), dtype=np.uint8) * 40

    # Draw Column Headers: A, B, C, D
    choices = ["A", "B", "C", "D"]
    for col_idx in range(num_cols):
        x1 = label_w + col_idx * (cell_size + margin)
        x2 = x1 + cell_size
        cv2.putText(
            canvas,
            choices[col_idx],
            (x1 + cell_size // 2 - 10, label_h // 2 + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

    # Draw cells and Row Headers (Câu 1 to Câu 15)
    for row_idx in range(num_rows):
        y1 = label_h + row_idx * (cell_size + margin)
        y2 = y1 + cell_size
        
        # Draw row label
        cv2.putText(
            canvas,
            f"Cau {row_idx + 1}",
            (15, y1 + cell_size // 2 + 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )
        
        for col_idx in range(num_cols):
            x1 = label_w + col_idx * (cell_size + margin)
            x2 = x1 + cell_size
            
            cell_info = cells[row_idx][col_idx]
            gray_cell = cell_info["gray"]
            
            if gray_cell is None or gray_cell.size == 0:
                # Empty placeholder
                preprocessed = np.zeros((cell_size, cell_size), dtype=np.uint8)
            else:
                # Preprocess: resize to 96x96
                preprocessed = cv2.resize(gray_cell, (cell_size, cell_size), interpolation=cv2.INTER_LINEAR)
            
            # Convert to color to insert into canvas
            preprocessed_color = cv2.cvtColor(preprocessed, cv2.COLOR_GRAY2BGR)
            
            # Put in canvas
            canvas[y1:y2, x1:x2] = preprocessed_color
            
            # Draw cell border
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (100, 100, 100), 1)

    output_dir = Path("d:/OCR/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "preprocessed_cells_grid.png"
    
    cv2.imwrite(str(output_path), canvas)
    print(f"\nSaved preprocessed cells grid to: {output_path}")
    print(f"Grid size: {grid_w}x{grid_h} pixels")

if __name__ == "__main__":
    main()
