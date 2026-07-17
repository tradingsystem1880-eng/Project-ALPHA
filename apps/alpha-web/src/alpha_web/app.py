"""FastAPI application factory + entry point for the ALPHA Workstation.

A thin JSON+SSE backend over the run store that serves the built single-page workstation
(``static/app``). Every action subprocesses the ``alpha`` CLI and reads its byte-stable artifacts —
the engine never runs in this process. Reads/writes go through ``AlphaSettings().data_dir`` so the
web app, its subprocesses, and the CLI share one store. Binds loopback only (local single-user).

Routers: ``/api/runs`` · ``/api/jobs`` · ``/api/{strategies,commands,symbols}`` · ``/api/candles``
· ``/api/apps``. The SPA is served at ``/`` (and ``/app``); its assets ride the ``/static`` mount.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from alpha_web.api import candles as candles_api
from alpha_web.api import catalog as catalog_api
from alpha_web.api import jobs as jobs_api
from alpha_web.api import manifest as manifest_api
from alpha_web.api import options as options_api
from alpha_web.api import research as research_api
from alpha_web.api import risk as risk_api
from alpha_web.api import runs as runs_api
from alpha_web.api import screener as screener_api
from alpha_web.api import workspaces as workspaces_api

_PKG = Path(__file__).resolve().parent
_APP_INDEX = _PKG / "static" / "app" / "index.html"  # built SPA entry (Vite → static/app)


def create_app() -> FastAPI:
    """Build the FastAPI app (factory so tests can construct a fresh instance)."""
    app = FastAPI(title="Project ALPHA — Workstation")
    app.mount("/static", StaticFiles(directory=str(_PKG / "static")), name="static")

    app.include_router(runs_api.router)
    app.include_router(jobs_api.router)
    app.include_router(catalog_api.router)
    app.include_router(candles_api.router)
    app.include_router(manifest_api.router)
    app.include_router(workspaces_api.router)
    app.include_router(options_api.router)
    app.include_router(risk_api.router)
    app.include_router(screener_api.router)
    app.include_router(research_api.router)

    def _spa() -> FileResponse:
        if not _APP_INDEX.exists():
            raise HTTPException(
                status_code=503,
                detail="workstation SPA not built; run `npm run build` in apps/alpha-web/frontend",
            )
        return FileResponse(_APP_INDEX, media_type="text/html")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        """Serve the built single-page workstation."""
        return _spa()

    @app.get("/app")
    def workstation() -> FileResponse:
        """Alias for the workstation (same SPA as ``/``)."""
        return _spa()

    return app


def main() -> None:
    """Entry point: serve the workstation on http://127.0.0.1:8800 (loopback only)."""
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8800)


if __name__ == "__main__":
    main()
