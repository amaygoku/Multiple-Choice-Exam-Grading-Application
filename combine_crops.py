import os
import shutil
from pathlib import Path

def main():
    src_dir = Path("d:/OCR/ten_tv_v2_processed")
    dst_dir = Path("d:/OCR/ten_tv_v2_processed_combined")
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Scanning {src_dir} for cropped images...")
    
    count = 0
    # Loop over items in src_dir
    for item in src_dir.iterdir():
        if item.is_dir():
            # This is a folder for a sheet, e.g. "2066e537b31e32406b0f"
            subdir_name = item.name
            for file in item.iterdir():
                if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg'] and 'visualized' not in file.name:
                    new_filename = f"{subdir_name}_{file.name}"
                    dst_path = dst_dir / new_filename
                    shutil.copy2(file, dst_path)
                    count += 1
                    
    print(f"Successfully combined {count} cropped images into {dst_dir}")

if __name__ == "__main__":
    main()
