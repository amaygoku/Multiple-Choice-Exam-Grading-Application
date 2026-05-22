Evaluation workflow for OMR tuning

1. Generate bootstrap labels from current pipeline:
   D:\OCR\.venv\Scripts\python.exe evaluation\bootstrap_labels.py

2. Open `data/ground_truth_review.csv` and fill:
   - `true_mssv`
   - `true_ma_de`
   - `true_answers`

3. Evaluate the current pipeline:
   D:\OCR\.venv\Scripts\python.exe evaluation\evaluate_omr.py

4. Tune OMR thresholds against reviewed labels:
   D:\OCR\.venv\Scripts\python.exe evaluation\tune_omr.py

Files produced:
- `data/bootstrap_predictions.jsonl`: raw predictions from the current pipeline
- `data/ground_truth_review.csv`: editable review sheet
- `data/eval_artifacts/<image_stem>/`: aligned page, crops, OMR debug images
- `data/eval_report.json`: summary metrics
- `data/tuning_report.json`: parameter search results
