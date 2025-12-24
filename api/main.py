from __future__ import annotations

import pathlib as pl
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import router as api_router
from .tiles import router as tiles_router

app = FastAPI(title="Deforestation Viewer API", version="0.1.0")

# Dev CORS (React dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(tiles_router)

# Optional: serve built React app if present at web/dist
BASE_DIR = pl.Path(__file__).resolve().parents[1]
dist = BASE_DIR / "web" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
