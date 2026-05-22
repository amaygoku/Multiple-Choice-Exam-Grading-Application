import torch
import torch.nn as nn
from torchvision import models

def check_model(path, name):
    print(f"=== Checking {name} at {path} ===")
    try:
        state_dict = torch.load(path, map_location='cpu')
        print("Keys count:", len(state_dict.keys()))
        
        model = models.mobilenet_v3_small(weights=None)
        # Using model.classifier[0].in_features which is 576
        in_features = model.classifier[0].in_features
        print("Using in_features:", in_features)
        model.classifier = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(512, 1),
        )
        
        missing, unexpected = model.load_state_dict(state_dict, strict=True)
        print("  Strict load: SUCCESS")
            
    except Exception as e:
        print("Failed to load weight file:", e)

check_model("d:/OCR/data/answer_model.pth", "Answer Model")
check_model("d:/OCR/data/id_model.pth", "ID Model")
