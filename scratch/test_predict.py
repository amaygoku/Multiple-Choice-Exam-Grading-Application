import os
import sys
import torch
from PIL import Image

sys.path.insert(0, os.getcwd())
import models.crnn as crnn
import utils
import dataset

# Vocab
vocab_str = 'aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆfFgGhHiIìÌỉỈĩĨíÍịỊjJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrRsStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxXyYỳỲỷỶỹỸýÝỵỴzZ0123456789!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '
alphabet = vocab_str[:200]

nclass = len(alphabet) + 1
model = crnn.CRNN(32, 1, nclass, 256)
sd = torch.load('models/best.pth', map_location='cpu')
model.load_state_dict(sd)
model.eval()

converter = utils.strLabelConverter(alphabet)
transformer = dataset.resizeNormalize((100, 32))

# Test images and their ground truth labels
test_cases = [
    ("06751a1a402ac174983b_crop_01_word_00.png", "Lâm"),
    ("06751a1a402ac174983b_crop_01_word_01.png", "Tùng"),
    ("06751a1a402ac174983b_crop_01_word_02.png", "Nguyễn"),
    ("06751a1a402ac174983b_crop_02_word_00.png", "Trang"),
    ("06751a1a402ac174983b_crop_02_word_01.png", "Thị"),
]

out_f = open("../../scratch/test_predictions.txt", "w", encoding="utf-8")

for filename, gt in test_cases:
    img_path = os.path.join("..", "cropped_words", filename)
    if not os.path.exists(img_path):
        out_f.write(f"File not found: {img_path}\n")
        continue
    image = Image.open(img_path).convert('L')
    image = transformer(image)
    image = image.view(1, *image.size())
    
    with torch.no_grad():
        preds = model(image)
        
    _, preds = preds.max(2)
    preds = preds.transpose(1, 0).contiguous().view(-1)
    
    preds_size = torch.LongTensor([preds.size(0)])
    sim_pred = converter.decode(preds.data, preds_size.data, raw=False)
    
    out_f.write(f"File: {filename} | GT: {gt} | Pred: {sim_pred} | Match: {gt == sim_pred}\n")

out_f.close()
print("Done writing predictions!")
