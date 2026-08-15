"""FastAPI application entry point."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import children, learning, parent
from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
settings = get_settings()

# adaptive-platform/backend/app/main.py -> adaptive-platform/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"

# Photos and audio are shipped with the live game and shared by both apps.
# Override with ASSETS_ROOT if you ever move or duplicate them.
ASSETS_ROOT = Path(
    os.getenv("ASSETS_ROOT", PROJECT_ROOT.parent / "live-game")
).resolve()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv("SEED_ON_START", "1") == "1":
        from app.seed.seed import seed_all

        with SessionLocal() as db:
            result = seed_all(db)
            db.commit()
            logging.getLogger("adaptive").info("seed: %s", result)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Adaptive learning backend. The client asks for the next question; "
        "the engine decides what it should be."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(children.router, prefix="/api")
app.include_router(learning.router, prefix="/api")
app.include_router(parent.router, prefix="/api")

for folder in ("images", "audio"):
    path = ASSETS_ROOT / folder
    if path.is_dir():
        app.mount(f"/media/{folder}", StaticFiles(directory=path), name=folder)
    else:
        logging.getLogger("adaptive").warning(
            "assets missing: %s — set ASSETS_ROOT to the folder holding images/ and audio/", path
        )

if WEB_ROOT.is_dir():
    app.mount("/app", StaticFiles(directory=WEB_ROOT, html=True), name="web")


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
