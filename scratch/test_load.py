import os
import sys
import torch

# Add current directory to path
sys.path.insert(0, os.getcwd())
import models.crnn as crnn

# VietOCR vocab string from config.yml
# In YAML, '' means a single '
vocab_str = 'aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆfFgGhHiIìÌỉỈĩĨíÍịỊjJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrRsStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxXyYỳỲỷỶỹỸýÝỵỴzZ0123456789!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '

# Take the first 200 characters
alphabet = vocab_str[:200]
print('Alphabet length:', len(alphabet))

nclass = len(alphabet) + 1
model = crnn.CRNN(32, 1, nclass, 256)
sd = torch.load('models/best.pth', map_location='cpu')
try:
    model.load_state_dict(sd)
    print('SUCCESS! Model loaded successfully!')
except Exception as e:
    print('FAILED:', e)
