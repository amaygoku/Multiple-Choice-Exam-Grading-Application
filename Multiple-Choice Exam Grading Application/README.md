# Multiple-Choice Exam Grading Application - Base Code Package

This package contains the base source code of the graduation thesis project.
It is prepared for source-code submission only, so runtime data, trained model
weights, local databases, evaluation outputs, and development environment files
are intentionally excluded.

## Included folders

- `backend/`: FastAPI backend, academic-data APIs, OCR/OMR processing pipeline,
  grading logic, and database models.
- `zipgrade-web/`: React + TypeScript frontend for class management, scanning,
  review, editing, analytics, and result viewing.
- `detect_text/`: OCR-related source code, including the YOLO + CRNN pipeline
  wrapper and the CRNN source folder used by the project.
- `static/`: legacy static assets mounted by the backend.

## Excluded items

The following items are not included in this base-code package:

- local virtual environments such as `.venv/`
- frontend build output such as `dist/`
- `node_modules/`
- `__pycache__/`
- local database files such as `backend.db`
- runtime output folders such as `results/`
- datasets, evaluation folders, debug images, and demo artifacts
- trained model weights used during local experiments

## Recommended environment

- Python 3.10 or newer
- Node.js 18 or newer
- npm

## Backend setup

Open a terminal in the package root and create a Python virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
```

For the OCR pipeline, the project may additionally require packages that are not
listed in `backend/requirements.txt` but are used by the OCR runtime, such as:

```powershell
pip install torch ultralytics pillow
```

Then start the backend:

```powershell
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Backend notes

- By default, the backend falls back to a local SQLite database file named
  `backend.db` in the package root if no `DATABASE_URL` environment variable is
  provided.
- The file `backend/.env.example` shows an example deployment configuration for
  PostgreSQL and S3 storage, but it is not required for a simple local run.

## Frontend setup

Open another terminal in the package root:

```powershell
cd zipgrade-web
npm install
npm run dev
```

The frontend uses Vite and runs on port `3000` by default.

### Frontend notes

- The frontend proxies `/api`, `/results`, `/static`, and `/static_results` to
  `https://127.0.0.1:8000` by default through `vite.config.ts`.
- If needed, this target can be changed with `VITE_BACKEND_PROXY_TARGET`.
- Some environment values in `zipgrade-web/.env.example` come from an earlier
  template and are not required for the main grading workflow.

## OCR runtime note

The OCR module in this project uses a YOLO + CRNN pipeline. In the original
development environment, the OCR runtime expected trained weights to be present.
Since this base-code package does not include experiment weights, OCR-related
functions may require the recipient to provide or reconfigure the model files
before full end-to-end recognition can run successfully.

In particular, the default YOLO weight path is defined inside:

- `detect_text/yolo_crnn_pipeline.py`

and should be updated if the project is run on another machine.

## Suggested submission format

You can compress this entire folder into a single `.zip` file and submit it as
the base code of the project.
