import sys
from pathlib import Path
import cv2
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.exam_pipeline import run_exam_pipeline

def test():
    img_path = r"d:\OCR\refined_answer_sheet.png"
    print(f"Loading test image: {img_path}")
    image = cv2.imread(img_path)
    if image is None:
        # Fallback to resultImage.jpg if refined_answer_sheet.png is not found or not loadable
        img_path = r"d:\OCR\resultImage.jpg"
        print(f"Fallback to test image: {img_path}")
        image = cv2.imread(img_path)
        
    if image is None:
        print("Error: No test image found!")
        return

    print("Running exam pipeline with debug_artifacts=True...")
    res = run_exam_pipeline(image, correct_answers="1A,2B", debug_artifacts=True, use_classifier=True)
    
    print("\nResult Keys:", list(res.keys()))
    print("Success:", res.get("success"))
    print("Message:", res.get("message"))
    print("Student Info:", str(res.get("student_info")).encode('ascii', errors='backslashreplace').decode('ascii'))
    print("Preprocess Images:")
    print(json.dumps(res.get("preprocess_images"), indent=2))
    
    # Check if files actually exist on disk
    preproc_imgs = res.get("preprocess_images")
    if preproc_imgs:
        print("\nVerifying files on disk:")
        for name, url in preproc_imgs.items():
            if url:
                # Url format: /results/<request_id>/preprocess/<file_name>?t=...
                # Extract relative path: results/<request_id>/preprocess/<file_name>
                clean_path = url.split("?")[0].lstrip("/")
                disk_path = Path("d:/OCR") / clean_path
                exists = disk_path.exists()
                print(f" - {name}: {disk_path} -> Exists: {exists}")
                if exists:
                    # Check size is not 0
                    print(f"   Size: {disk_path.stat().st_size} bytes")

if __name__ == "__main__":
    test()
