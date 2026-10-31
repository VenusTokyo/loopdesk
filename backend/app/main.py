"""LoopDesk backend.

One process serves the API, the widget bundle, the demo app and the admin
page. Fewer moving parts means a deploy that is hard to get wrong on the day.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, settings
from .db import init_db
from .routes import admin, demo, public, webhooks

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("loopdesk")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info(
        "LoopDesk up - provider=%s storage=%s github=%s db=%s",
        settings.llm_provider,
        settings.storage_backend,
        "live" if settings.github_enabled else "dry-run",
        settings.database_url.split("://")[0],
    )
    yield


app = FastAPI(
    title="LoopDesk",
    version="0.1.0",
    description="Screenshot to solution, closed loop.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
app.include_router(demo.router)


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "provider": settings.llm_provider,
        "github": "live" if settings.github_enabled else "dry-run",
        "storage": settings.storage_backend,
    }


@app.get("/widget.js")
def widget_js() -> FileResponse:
    return FileResponse(
        REPO_ROOT / "widget" / "dist" / "widget.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/")
def root() -> FileResponse:
    """The landing page. The demo app lives at /demo/."""
    return FileResponse(REPO_ROOT / "landing" / "index.html", media_type="text/html")


_screenshots = settings.data_dir / "screenshots"
_screenshots.mkdir(parents=True, exist_ok=True)

app.mount("/files", StaticFiles(directory=_screenshots), name="files")
app.mount("/landing", StaticFiles(directory=REPO_ROOT / "landing"), name="landing")
app.mount("/admin", StaticFiles(directory=REPO_ROOT / "admin", html=True), name="admin")
app.mount("/demo", StaticFiles(directory=REPO_ROOT / "demo-app", html=True), name="demo")
