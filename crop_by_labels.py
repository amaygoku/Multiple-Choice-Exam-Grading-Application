import os
import cv2
from pathlib import Path

def main():
    # Source directory containing both images (.png) and YOLO labels (.txt)
    src_dir = Path("d:/OCR/detect_text/image")
    
    # Destination directory to save cropped words
    dst_dir = Path("d:/OCR/detect_text/cropped_words")
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    # Extensions
    img_extensions = ['.png', '.jpg', '.jpeg']
    
    print(f"Scanning {src_dir} for images...")
    img_paths = [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in img_extensions]
    print(f"Found {len(img_paths)} images.")
    
    processed_images = 0
    total_crops = 0
    
    for img_path in img_paths:
        # Corresponding label file
        txt_path = img_path.with_suffix('.txt')
        
        if not txt_path.exists():
            continue
            
        # Load image
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Warning: Could not read image {img_path.name}")
            continue
            
        h, w = img.shape[:2]
        
        # Read YOLO labels
        with open(txt_path, 'r') as f:
            lines = f.readlines()
            
        for box_idx, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) < 5:
                continue
                
            class_id = parts[0]
            try:
                x_center = float(parts[1])
                y_center = float(parts[2])
                box_w = float(parts[3])
                box_h = float(parts[4])
            except ValueError:
                continue
                
            # Convert normalized YOLO coordinates to pixel coordinates
            # YOLO format: class x_center y_center width height (all normalized 0.0 to 1.0)
            x1 = int((x_center - box_w / 2.0) * w)
            y1 = int((y_center - box_h / 2.0) * h)
            x2 = int((x_center + box_w / 2.0) * w)
            y2 = int((y_center + box_h / 2.0) * h)
            
            # Clip boundaries to image size
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)
            
            # Crop the bounding box
            if x2 > x1 and y2 > y1:
                crop = img[y1:y2, x1:x2]
                
                # Save crop file named: {img_name}_word_{box_idx:02d}.png
                crop_name = f"{img_path.stem}_word_{box_idx:02d}.png"
                cv2.imwrite(str(dst_dir / crop_name), crop)
                total_crops += 1
                
        processed_images += 1
        
    print(f"Successfully processed {processed_images} images.")
    print(f"Created {total_crops} cropped word images in {dst_dir}")

if __name__ == "__main__":
    main()
