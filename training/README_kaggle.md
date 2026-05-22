Kaggle dataset layout

Run:

```powershell
D:\anaconda\python.exe evaluation\export_kaggle_classification_dataset.py
```

This creates:

- `data/kaggle_datasets/answer_binary`
- `data/kaggle_datasets/id_binary`
- `data/kaggle_datasets/mssv_binary`
- `data/kaggle_datasets/ma_de_binary`

Each task uses:

```text
task_name/
  train/
    empty/
    filled/
  val/
    empty/
    filled/
  test/
    empty/
    filled/
  manifest.csv
```

Default balancing:

- `answer_binary`: keep all positives, sample negatives to `2:1`
- `id_binary`, `mssv_binary`, `ma_de_binary`: keep all positives, sample negatives to `3:1`

The split is by `image`, not by cell, to avoid leakage across train/val/test.

Kaggle MobileNet baseline

Upload one task folder as a Kaggle dataset, then run:

```python
!python /kaggle/input/your-code-repo/training/kaggle_train_mobilenet.py \
  --dataset-dir /kaggle/input/your-cell-dataset/answer_binary \
  --output-dir /kaggle/working/answer_mobilenet \
  --pretrained
```

Suggested first runs:

- `answer_binary`
- `id_binary`

YOLO classification

The same folder layout is compatible with Ultralytics classification. Example:

```python
from ultralytics import YOLO

model = YOLO("yolo11n-cls.pt")
model.train(
    data="/kaggle/input/your-cell-dataset/answer_binary",
    epochs=20,
    imgsz=96,
    batch=64,
    project="/kaggle/working",
    name="answer_yolo_cls",
)
```

If Kaggle cannot download pretrained weights, switch to a local weight file or use the MobileNet script without `--pretrained`.
