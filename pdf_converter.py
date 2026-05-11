import fitz  # PyMuPDF
import os

def pdf_to_image(pdf_path, output_image):
    doc = fitz.open(pdf_path)
    page = doc[0]  # First page
    pix = page.get_pixmap(dpi=300)
    pix.save(output_image)
    doc.close()
    print(f"Saved {pdf_path} page 1 to {output_image}")

if __name__ == "__main__":
    pdf_to_image(r'D:\OCR\Answer_sheet_A4.pdf', r'D:\OCR\answer_sheet_page1.png')
