"""Serve only the built frontend, after the application's API routes."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI) -> None:
    directory = os.environ.get("FRONTEND_DIST", "").strip()
    if not directory:
        return  # Local development keeps using the Vite server.
    path = Path(directory).resolve()
    if not (path / "index.html").is_file():
        raise RuntimeError("FRONTEND_DIST must point to a built frontend containing index.html")
    # HashRouter needs only index.html and its assets, never an API catch-all.
    # Mount the dist directory alone so source, .env and workbooks aren't served.
    app.mount("/", StaticFiles(directory=path, html=True), name="frontend")
