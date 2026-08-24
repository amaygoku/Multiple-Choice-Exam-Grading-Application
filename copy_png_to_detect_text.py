import shutil
from pathlib import Path

def main():
    src_dir = Path(r"D:\OCR\ten_tv_v2_processed_combined")
    dst_dir = Path(r"D:\OCR\detect_text\detect_text_data\images")
    
    # Create the destination directory if it doesn't exist
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Copying .png files from {src_dir} to {dst_dir}...")
    
    count = 0
    # Find all files with .png suffix and copy them
    for file in src_dir.glob("*.png"):
        shutil.copy2(file, dst_dir / file.name)
        count += 1
        
    print(f"Successfully copied {count} .png files to {dst_dir}")

if __name__ == "__main__":
    main()
