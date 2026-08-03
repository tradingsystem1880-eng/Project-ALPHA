"""FastAPI application factory + entry point for the ALPHA Workstation.

A thin JSON+SSE backend over the run store that serves the built single-page workstation
(``static/app``). Every action subprocesses the ``alpha`` CLI and reads its byte-stable artifacts —
the engine never runs in this process. Reads/writes go through ``AlphaSettings().data_dir`` so the
web app, its subprocesses, and the CLI share one store. Binds loopback only (local single-user);
the port comes from ``ALPHA_WEB_PORT`` (preferred) or ``PORT``, defaulting to 8800 — an invalid
value fails loud with :class:`alpha_core.AlphaError`.

Routers include runs/jobs/catalog, candles, provider/system readiness, durable paper monitoring,
and CLI-backed v3 project/evidence/AgentBrief projections.
The SPA is served at ``/`` (and ``/app``); its assets ride the ``/static`` mount.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from alpha_core import AlphaError
from alpha_web.api import activity as activity_api
from alpha_web.api import candles as candles_api
from alpha_web.api import catalog as catalog_api
from alpha_web.api import control as control_api
from alpha_web.api import development as development_api
from alpha_web.api import jobs as jobs_api
from alpha_web.api import ml as ml_api
from alpha_web.api import options as options_api
from alpha_web.api import paper as paper_api
from alpha_web.api import research as research_api
from alpha_web.api import risk as risk_api
from alpha_web.api import runs as runs_api
from alpha_web.api import screener as screener_api
from alpha_web.api import v3 as v3_api
from alpha_web.api import workspaces as workspaces_api

_PKG = Path(__file__).resolve().parent
_APP_INDEX = _PKG / "static" / "app" / "index.html"  # built SPA entry (Vite → static/app)


def create_app() -> FastAPI:
    """Build the FastAPI app (factory so tests can construct a fresh instance)."""
    app = FastAPI(title="Project ALPHA — Workstation")
    app.add_middleware(GZipMiddleware, minimum_size=1_000, compresslevel=5)
    app.mount("/static", StaticFiles(directory=str(_PKG / "static")), name="static")

    app.include_router(runs_api.router)
    app.include_router(jobs_api.router)
    app.include_router(activity_api.router)
    app.include_router(catalog_api.router)
    app.include_router(control_api.router)
    app.include_router(development_api.router)
    app.include_router(ml_api.router)
    app.include_router(candles_api.router)
    app.include_router(workspaces_api.router)
    app.include_router(options_api.router)
    app.include_router(paper_api.router)
    app.include_router(risk_api.router)
    app.include_router(screener_api.router)
    app.include_router(research_api.router)
    app.include_router(v3_api.router)

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


def _resolve_port() -> int:
    """Resolve the serve port from ``ALPHA_WEB_PORT`` (preferred) then ``PORT``; default 8800.

    A set-but-invalid value (non-integer or outside [1, 65535]) raises
    :class:`alpha_core.AlphaError` naming the variable and value — never a silent fallback.
    """
    for name in ("ALPHA_WEB_PORT", "PORT"):
        raw = os.environ.get(name)
        if raw is None:
            continue
        try:
            port = int(raw)
        except ValueError as exc:
            raise AlphaError(f"invalid {name}={raw!r}: expected an integer in [1, 65535]") from exc
        if not 1 <= port <= 65535:
            raise AlphaError(f"invalid {name}={raw!r}: expected an integer in [1, 65535]")
        return port
    return 8800


def main() -> None:
    """Entry point: serve the workstation on http://127.0.0.1:<port> (loopback only).

    The port comes from ``ALPHA_WEB_PORT`` (preferred) or ``PORT``, defaulting to 8800; the
    host is always ``127.0.0.1``. Invalid port values fail loud (:class:`alpha_core.AlphaError`).
    """
    import uvicorn

    port = _resolve_port()  # fail loud before the app is even constructed
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
