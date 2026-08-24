import os
import sys
import csv
import torch
from PIL import Image
from collections import Counter

# Add absolute path to crnn-pytorch-master to sys.path
sys.path.insert(0, os.path.abspath('detect_text/crnn-pytorch-master'))
import models.crnn as crnn
import dataset

# Initialize model with dummy 200-char alphabet to match shape
dummy_alphabet = 'a' * 200
nclass = len(dummy_alphabet) + 1
model = crnn.CRNN(32, 1, nclass, 256)
sd = torch.load('detect_text/crnn-pytorch-master/models/best.pth', map_location='cpu')
model.load_state_dict(sd)
model.eval()

transformer = dataset.resizeNormalize((100, 32))

# Load ground truth labels
gt_labels = {}
with open('detect_text/cropped_words/labels.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        if len(row) >= 2:
            gt_labels[row[0]] = row[1]

print(f"Loaded {len(gt_labels)} ground truth labels.")

# We will collect co-occurrences of predicted indices and GT characters.
# Since words can have multiple characters, we can align them.
# Simple alignment: if the predicted index sequence has same length as GT word, we map index_i to char_i.
mappings = {i: Counter() for i in range(1, 201)}

img_dir = 'detect_text/cropped_words'
count_exact_len = 0

for filename, gt_word in gt_labels.items():
    img_path = os.path.join(img_dir, filename)
    if not os.path.exists(img_path):
        continue
        
    try:
        image = Image.open(img_path).convert('L')
        image = transformer(image)
        image = image.view(1, *image.size())
        
        with torch.no_grad():
            preds = model(image)
            
        _, preds = preds.max(2)
        preds = preds.transpose(1, 0).contiguous().view(-1)
        
        # Decode CTC raw indices to collapsed indices (removing consecutive duplicates and blanks (0))
        collapsed = []
        prev = -1
        for p in preds.tolist():
            if p != 0 and p != prev:
                collapsed.append(p)
            prev = p
            
        if len(collapsed) == len(gt_word):
            count_exact_len += 1
            for idx, char in zip(collapsed, gt_word):
                mappings[idx][char] += 1
    except Exception as e:
        pass

print(f"Found {count_exact_len} images where predicted index length matches ground truth length exactly.")

# Reconstruct alphabet
reconstructed_mapping = {}
for idx in range(1, 201):
    counter = mappings[idx]
    if counter:
        most_common_char, count = counter.most_common(1)[0]
        reconstructed_mapping[idx] = (most_common_char, count)
    else:
        reconstructed_mapping[idx] = (None, 0)

# Save result to a file
with open('scratch/reconstructed_alphabet.txt', 'w', encoding='utf-8') as f:
    f.write("Index | Char | Confidence (Count) | All occurrences\n")
    f.write("-" * 50 + "\n")
    for idx in range(1, 201):
        char, count = reconstructed_mapping[idx]
        all_occ = dict(mappings[idx].most_common(5))
        f.write(f"{idx:5d} | {str(char):4s} | {count:16d} | {all_occ}\n")

print("Done writing reconstruction results!")
