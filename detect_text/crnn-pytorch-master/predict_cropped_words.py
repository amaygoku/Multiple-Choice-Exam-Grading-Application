import os
import csv
import sys
import torch
from torch.autograd import Variable
from PIL import Image
import utils
import dataset
import models.crnn as crnn
import params

# Ensure UTF-8 output encoding for Vietnamese characters in console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    # Paths
    model_path = os.path.join('models', 'last.pth')
    cropped_words_dir = os.path.join('..', 'crop_words')
    csv_output_path = os.path.join(cropped_words_dir, 'labels.csv')
    
    # Check if directories exist
    if not os.path.exists(model_path):
        print(f"Error: Model file {model_path} not found!")
        return
    if not os.path.exists(cropped_words_dir):
        print(f"Error: cropped_words directory {cropped_words_dir} not found!")
        return

    # Check CUDA
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # net init
    nclass = len(params.alphabet) + 1
    model = crnn.CRNN(params.imgH, params.nc, nclass, params.nh)
    model = model.to(device)

    # load model
    print(f'Loading pretrained model from {model_path}')
    if params.multi_gpu:
        model = torch.nn.DataParallel(model)
        
    # load state dict with map_location
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    converter = utils.strLabelConverter(params.alphabet)
    transformer = dataset.resizeNormalize((100, 32))

    # Scan directory for images
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    image_files = sorted([f for f in os.listdir(cropped_words_dir) if f.lower().endswith(valid_extensions)])
    
    print(f"Found {len(image_files)} images in {cropped_words_dir}")
    
    predictions = {}
    
    # Backup existing labels.csv if it exists
    if os.path.exists(csv_output_path):
        backup_path = csv_output_path + ".bak"
        print(f"Existing {csv_output_path} found. Backing up to {backup_path}")
        try:
            import shutil
            shutil.copy2(csv_output_path, backup_path)
        except Exception as e:
            print(f"Warning: Could not backup labels.csv: {e}")
    
    # Process images
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
                print(f"Predicted {idx + 1}/{len(image_files)}: {filename} => {sim_pred}")
        except Exception as e:
            print(f"Error predicting {filename}: {e}")

    # Save to labels.csv
    try:
        with open(csv_output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["image_name", "label"])
            for img_name in sorted(predictions.keys()):
                writer.writerow([img_name, predictions[img_name]])
        print(f"Successfully saved predictions to {csv_output_path}")
    except Exception as e:
        print(f"Error saving CSV: {e}")

if __name__ == '__main__':
    main()
