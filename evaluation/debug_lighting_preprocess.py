import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detect_paper import align_document_image
from omr_pipeline import DEFAULT_OMR_CONFIG, normalize_paper_lighting, threshold_omr_image


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Export OMR preprocessing debug images.")
    parser.add_argument("--input", required=True, help="Path to raw input image")
    parser.add_argument("--output-dir", default="data/preprocess_debug", help="Directory to save debug images")
    parser.add_argument("--align", action="store_true", help="Align paper before preprocessing")
    parser.add_argument("--sigma", type=float, default=25.0, help="Lighting normalization sigma")
    parser.add_argument("--gain", type=float, default=180.0, help="Lighting normalization gain")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output_dir) / input_path.stem
    ensure_dir(out_dir)

    image = cv2.imread(str(input_path))
    if image is None:
        raise ValueError(f"Cannot read image: {input_path}")

    if args.align:
        aligned = align_document_image(image)
        if aligned is not None:
            image = aligned
            cv2.imwrite(str(out_dir / "00_aligned.png"), image)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(str(out_dir / "01_gray.png"), gray)

    config = DEFAULT_OMR_CONFIG
    config.lighting_sigma = args.sigma
    config.lighting_gain = args.gain
    norm = normalize_paper_lighting(gray, config)
    cv2.imwrite(str(out_dir / "02_lighting_normalized.png"), norm)

    thresh_raw = threshold_omr_image(gray, config)
    cv2.imwrite(str(out_dir / "03_threshold_raw.png"), thresh_raw)

    thresh_norm = threshold_omr_image(norm, config)
    cv2.imwrite(str(out_dir / "04_threshold_normalized.png"), thresh_norm)

    edges = cv2.Canny(norm, 50, 150)
    cv2.imwrite(str(out_dir / "05_edges_normalized.png"), edges)

    print(f"Saved preprocessing debug images to: {out_dir}")


if __name__ == "__main__":
    main()
