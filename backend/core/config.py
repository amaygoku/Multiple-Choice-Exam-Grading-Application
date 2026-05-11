from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
RESULTS_DIR = BASE_DIR / "results"
CROPS_DIR = RESULTS_DIR / "crops"


def ensure_runtime_dirs() -> None:
    """Create directories required at runtime."""
    STATIC_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    CROPS_DIR.mkdir(exist_ok=True)
