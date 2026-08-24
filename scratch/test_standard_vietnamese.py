import os
import sys
import torch

sys.path.insert(0, os.getcwd())
import models.crnn as crnn

# Common Vietnamese CRNN alphabet
alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
print('Alphabet length:', len(alphabet))

nclass = len(alphabet) + 1
model = crnn.CRNN(32, 1, nclass, 256)
sd = torch.load('models/best.pth', map_location='cpu')
try:
    model.load_state_dict(sd)
    print('SUCCESS! Model loaded successfully!')
except Exception as e:
    print('FAILED:', e)
