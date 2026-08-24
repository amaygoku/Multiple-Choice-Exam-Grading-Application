import os
import csv
import sys
import torch
from torch.autograd import Variable
from PIL import Image

# Ensure UTF-8 output encoding for Vietnamese characters in console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Dynamic path resolution to allow running this script from any directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import utils
import dataset
import models.crnn as crnn
import params

def main():
    # Paths relative to the script directory
    model_path = os.path.join(SCRIPT_DIR, 'models', 'best.pth')
    cropped_words_dir = os.path.join(SCRIPT_DIR, '..', 'crop_word')
    csv_output_path = os.path.join(cropped_words_dir, 'labels.csv')
    
    # Check if files and directories exist
    if not os.path.exists(model_path):
        print(f"Error: Model weights not found at {model_path}!")
        return
    if not os.path.exists(cropped_words_dir):
        print(f"Error: cropped_words directory not found at {cropped_words_dir}!")
        return

    # Select CPU or CUDA device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    print(f"Loading weights from: {model_path}")

    # Initialize model
    nclass = len(params.alphabet) + 1
    model = crnn.CRNN(params.imgH, params.nc, nclass, params.nh)
    model = model.to(device)

    if params.multi_gpu:
        model = torch.nn.DataParallel(model)
        
    # Load state dict
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    # Helpers
    converter = utils.strLabelConverter(params.alphabet)
    transformer = dataset.resizeNormalize((100, 32))

    # Scan for images
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    image_files = sorted([f for f in os.listdir(cropped_words_dir) if f.lower().endswith(valid_extensions)])
    
    print(f"Found {len(image_files)} images in {cropped_words_dir}")
    
    predictions = {}
    
    # Backup existing labels.csv if it exists
    if os.path.exists(csv_output_path):
        backup_path = csv_output_path + ".bak"
        print(f"Existing labels.csv found. Backing up to {backup_path}")
        try:
            import shutil
            shutil.copy2(csv_output_path, backup_path)
        except Exception as e:
            print(f"Warning: Could not backup labels.csv: {e}")
    
    # Batch Predict
    print("\nRunning inference...")
    for idx, filename in enumerate(image_files):
        img_path = os.path.join(cropped_words_dir, filename)
        try:
            image = Image.open(img_path).convert('L')
            image = transformer(image)
            image = image.to(device)
            image = image.view(1, *image.size())
            image = Variable(image)

            with torch.no_grad():
                preds = model(image)

            _, preds = preds.max(2)
            preds = preds.transpose(1, 0).contiguous().view(-1)

            preds_size = Variable(torch.LongTensor([preds.size(0)]))
            sim_pred = converter.decode(preds.data, preds_size.data, raw=False)
            
            predictions[filename] = sim_pred
            
            if (idx + 1) % 100 == 0 or (idx + 1) == len(image_files):
                print(f"Processed {idx + 1}/{len(image_files)}: {filename} => {sim_pred}")
        except Exception as e:
            print(f"Error predicting {filename}: {e}")

    # Save to labels.csv
    try:
        with open(csv_output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["image_name", "label"])
            for img_name in sorted(predictions.keys()):
                writer.writerow([img_name, predictions[img_name]])
        print(f"\nSuccessfully saved predictions to: {csv_output_path}")
    except Exception as e:
        print(f"Error saving CSV: {e}")

if __name__ == '__main__':
    main()
