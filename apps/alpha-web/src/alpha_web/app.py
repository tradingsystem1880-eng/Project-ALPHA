"""FastAPI application factory + entry point for the ALPHA web IDE.

Server-rendered (Jinja) pages over the run store: a run browser, run detail (manifest + inline
equity SVG + embedded tear sheet), and — added in the launcher slice — a new-run form, a live SSE
run console, and a command console. Reads/writes go through ``AlphaSettings().data_dir`` so the web
app, its subprocesses, and the CLI share one store. Binds loopback only (local single-user).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from alpha_core.config import AlphaSettings
from alpha_web import _charts, _invoke, _runs
from alpha_web.api import catalog as catalog_api
from alpha_web.api import jobs as jobs_api
from alpha_web.api import runs as runs_api

_PKG = Path(__file__).resolve().parent


def _data_dir() -> Path:
    return AlphaSettings().data_dir


def _fmt(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return str(value)
    return f"{value:.4f}"


def _summarize(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten a manifest's headline scalars + metric blocks into display rows."""
    rows: list[tuple[str, str]] = []
    for key in (
        "command",
        "symbol",
        "source",
        "firm",
        "passed",
        "best_sharpe",
        "n_paths",
        "horizon_days",
    ):
        value = manifest.get(key)
        if value is not None:
            rows.append((key, _fmt(value)))
    verdict = manifest.get("verdict")
    if isinstance(verdict, dict):
        grades = " / ".join(
            f"{k} {verdict.get(k)}" for k in ("edge", "robustness", "risk", "sample")
        )
        rows.append(("verdict", f"{verdict.get('overall')} ({grades})"))
    for block in ("metrics", "oos_metrics"):
        values = manifest.get(block)
        if isinstance(values, dict):
            rows.extend((f"{block}.{k}", _fmt(v)) for k, v in sorted(values.items()))
    return rows


def create_app() -> FastAPI:
    """Build the FastAPI app (factory so tests can construct a fresh instance)."""
    app = FastAPI(title="Project ALPHA — Workstation")
    templates = Jinja2Templates(directory=str(_PKG / "templates"))
    app.mount("/static", StaticFiles(directory=str(_PKG / "static")), name="static")

    app.include_router(runs_api.router)
    app.include_router(jobs_api.router)
    app.include_router(catalog_api.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index(request: Request) -> Response:
        runs = _runs.list_runs(data_dir=_data_dir())
        return templates.TemplateResponse(request, "index.html", {"runs": runs})

    @app.get("/runs/{run_id}")
    def run_detail(request: Request, run_id: str) -> Response:
        try:
            manifest = _runs.get_run(run_id, data_dir=_data_dir())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        values = _runs.equity_values(run_id, data_dir=_data_dir())
        forecast = (
            _runs.forecast_series(run_id, data_dir=_data_dir())
            if manifest.get("command") == "forecast_run"
            else None
        )
        return templates.TemplateResponse(
            request,
            "run_detail.html",
            {
                "run_id": run_id,
                "manifest": manifest,
                "label": manifest.get("symbol") or manifest.get("source"),
                "summary": _summarize(manifest),
                "equity_svg": _charts.equity_svg(values) if values else None,
                "forecast_svg": (
                    _charts.forecast_svg(
                        forecast["history"],
                        forecast["forecast"],
                        p10=forecast["p10"],
                        p90=forecast["p90"],
                    )
                    if forecast
                    else None
                ),
                "leakage_warning": manifest.get("leakage_warning"),
                "has_tearsheet": _runs.tearsheet_file(run_id, data_dir=_data_dir()) is not None,
            },
        )

    @app.get("/runs/{run_id}/tearsheet")
    def tearsheet(run_id: str) -> FileResponse:
        path = _runs.tearsheet_file(run_id, data_dir=_data_dir())
        if path is None:
            raise HTTPException(status_code=404, detail="no tear sheet for this run")
        return FileResponse(path, media_type="text/html")

    @app.get("/new")
    def new_run(request: Request) -> Response:
        commands = [*_invoke.RUN_TYPE, "data pull"]
        return templates.TemplateResponse(request, "new.html", {"commands": commands})

    @app.get("/console")
    def console(request: Request) -> Response:
        return templates.TemplateResponse(request, "console.html", {})

    @app.post("/runs")
    def launch_run(command: str = Form(...), args: str = Form("")) -> JSONResponse:
        argv = command.split() + shlex.split(args)
        job = _invoke.launch(argv, data_dir=_data_dir(), run_type=_invoke.RUN_TYPE.get(command))
        return JSONResponse({"job_id": job.job_id})

    @app.post("/console/run")
    def console_run(args: str = Form("")) -> JSONResponse:
        job = _invoke.launch(shlex.split(args), data_dir=_data_dir(), run_type=None)
        return JSONResponse({"job_id": job.job_id})

    @app.get("/jobs/{job_id}/stream")
    async def job_stream(job_id: str) -> EventSourceResponse:
        job = _invoke.JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        return EventSourceResponse(_invoke.event_stream(job))

    return app


def main() -> None:
    """Entry point: serve the web IDE on http://127.0.0.1:8800 (loopback only)."""
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8800)


if __name__ == "__main__":
    main()
