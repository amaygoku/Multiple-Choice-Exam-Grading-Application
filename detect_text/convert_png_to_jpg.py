import os
from PIL import Image

def convert_png_to_jpg(folder_path):
    # Tạo thư mục đầu ra để tránh ghi đè hoặc làm loạn thư mục gốc
    output_folder = os.path.join(folder_path, "jpg_converted")
    os.makedirs(output_folder, exist_ok=True)
    
    # Lấy danh sách các file png
    png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]
    
    if not png_files:
        print("Không tìm thấy file PNG nào trong thư mục!")
        return

    print(f"Đang chuyển đổi {len(png_files)} ảnh PNG sang JPG...")
    
    success_count = 0
    for file_name in png_files:
        src_path = os.path.join(folder_path, file_name)
        target_name = os.path.splitext(file_name)[0] + ".jpg"
        target_path = os.path.join(output_folder, target_name)
        
        try:
            with Image.open(src_path) as img:
                # Xử lý ảnh PNG trong suốt (Alpha channel RGBA hoặc LA)
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    # Tạo nền trắng với cùng kích thước
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    # Dán ảnh gốc đè lên nền trắng (sử dụng kênh alpha làm mặt nạ mask)
                    if img.mode == 'RGBA':
                        background.paste(img, (0, 0), img)
                    else:
                        background.paste(img.convert('RGBA'), (0, 0), img.convert('RGBA'))
                    # Lưu lại dưới dạng JPG
                    background.save(target_path, "JPEG", quality=95)
                else:
                    # Ảnh không trong suốt, convert sang RGB rồi lưu trực tiếp
                    rgb_img = img.convert("RGB")
                    rgb_img.save(target_path, "JPEG", quality=95)
                    
            success_count += 1
        except Exception as e:
            print(f"Lỗi khi chuyển đổi file {file_name}: {e}")
            
    print(f"\nHoàn thành! Đã chuyển đổi thành công {success_count}/{len(png_files)} ảnh.")
    print(f"Ảnh JPG được lưu tại: {output_folder}")

if __name__ == "__main__":
    # Nhập đường dẫn thư mục chứa ảnh PNG
    folder = input("Nhập đường dẫn thư mục ảnh PNG: ").strip()
    # Loại bỏ dấu ngoặc kép nếu người dùng kéo thả thư mục vào terminal
    folder = folder.replace('"', '').replace("'", "")
    
    if os.path.isdir(folder):
        convert_png_to_jpg(folder)
    else:
        print("Đường dẫn thư mục không hợp lệ!")
