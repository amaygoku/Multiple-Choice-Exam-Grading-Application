from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.core.database import Base, engine, ensure_sqlite_schema
from backend.core.config import RESULTS_DIR, STATIC_DIR, ensure_runtime_dirs
from backend.routers.academic import academic_router
from backend.routers.exams import api_router, legacy_router
from backend import models  # noqa: F401


def create_app() -> FastAPI:
    ensure_runtime_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()

    app = FastAPI(
        title="OMR Grading Backend",
        description="Backend API for OCR/OMR answer sheet grading.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
    app.mount("/static_results", StaticFiles(directory=str(RESULTS_DIR)), name="static_results")

    @app.get("/", response_class=HTMLResponse)
    async def read_index():
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    app.include_router(legacy_router)
    app.include_router(api_router)
    app.include_router(academic_router)
    return app


app = create_app()
