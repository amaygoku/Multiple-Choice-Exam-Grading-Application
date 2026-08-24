import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
RESULTS_DIR = BASE_DIR / "results"
CROPS_DIR = RESULTS_DIR / "crops"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'backend.db').as_posix()}")

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "").strip()
AWS_S3_REGION = os.getenv("AWS_S3_REGION", "").strip()
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "").strip() or None
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "").strip() or None
AWS_S3_PREFIX = os.getenv("AWS_S3_PREFIX", "ocr").strip().strip("/")
AWS_S3_PRESIGN_EXPIRES_SECONDS = int(os.getenv("AWS_S3_PRESIGN_EXPIRES_SECONDS", "604800"))


def ensure_runtime_dirs() -> None:
    """Create directories required at runtime."""
    STATIC_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    CROPS_DIR.mkdir(exist_ok=True)
