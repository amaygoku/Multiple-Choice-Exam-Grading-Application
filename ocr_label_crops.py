import os
import cv2
import re
from pathlib import Path
from ocr import ocr_read_name_image

def sanitize_label(text):
    if not text:
        return "unknown"
    # Convert to lowercase and strip whitespace
    text = text.lower().strip()
    # Replace spaces with underscores
    text = text.replace(" ", "_")
    # Remove characters that are invalid in Windows filenames: \ / : * ? " < > |
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    if not text:
        return "unknown"
    return text

def main():
    # Source directory containing the cropped word images
    src_dir = Path("d:/OCR/detect_text/cropped_words")
    
    # Destination directory to save the OCR-labeled images
    dst_dir = Path("d:/OCR/detect_text/ocr_labeled")
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    img_extensions = ['.png', '.jpg', '.jpeg']
    
    print(f"Scanning {src_dir} for word crops...")
    img_paths = sorted([p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in img_extensions])
    print(f"Found {len(img_paths)} images.")
    
    # Dictionary to keep track of counters for each label
    label_counters = {}
    
    processed_count = 0
    saved_count = 0
    
    for idx, img_path in enumerate(img_paths, start=1):
        if idx % 100 == 0 or idx == len(img_paths):
            print(f"Processing image {idx}/{len(img_paths)}...")
            
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Warning: Could not read {img_path.name}")
            continue
            
        # Use our OCR function to read the image
        predicted_text = ocr_read_name_image(img)
        
        # Sanitize text for filename use
        label = sanitize_label(predicted_text)
        
        # Get next count for this label
        count = label_counters.get(label, 0) + 1
        label_counters[label] = count
        
        # Create output name: label_number.jpg (e.g. huy_1.jpg)
        new_filename = f"{label}_{count}.jpg"
        dst_path = dst_dir / new_filename
        
        # Save image as .jpg
        cv2.imwrite(str(dst_path), img)
        saved_count += 1
        processed_count += 1
        
    print("\nOCR labeling completed!")
    print(f"Successfully processed {processed_count} images.")
    print(f"Saved {saved_count} labeled images to {dst_dir}")

if __name__ == "__main__":
    main()
