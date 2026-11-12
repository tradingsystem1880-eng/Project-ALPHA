"""Serve an isolated compiled SPA and unchanged risk API over synthetic runs only.

Test composition, not a production entry point or a model/research executor.
The caller builds C04_RISK_LIVE_ROOT/spa first; tracked static assets are untouched.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main() -> None:
    root = Path(os.environ["C04_RISK_LIVE_ROOT"]).resolve()
    build = root / "spa"
    if not (build / "index.html").is_file():
        raise RuntimeError("build the isolated SPA before starting live acceptance")
    repository = Path(__file__).resolve().parents[1]
    source_roots = sorted([*repository.glob("packages/*/src"), *repository.glob("apps/*/src")])
    sys.path[:0] = [str(path) for path in source_roots]
    os.environ["PYTHONPATH"] = os.pathsep.join(str(path) for path in source_roots)
    # No owner .env, store or ALPHA runtime context crosses into this test server.
    for name in tuple(os.environ):
        if name.startswith("ALPHA_"):
            os.environ.pop(name)
    with tempfile.TemporaryDirectory(prefix="synthetic-store-", dir=root) as temporary:
        data = Path(temporary)
        os.environ["ALPHA_DATA_DIR"] = str(data)
        os.environ["ALPHA_BULK_DATA_DIR"] = str(data / "bulk")
        os.environ["ALPHA_PAPER_ENABLED"] = "false"
        os.environ["ALPHA_IBKR_PAPER_ENABLED"] = "false"
        os.chdir(data)

        import polars as pl
        import uvicorn
        from starlette.applications import Starlette
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import FileResponse, JSONResponse, Response
        from starlette.routing import Mount, Route
        from starlette.staticfiles import StaticFiles

        from alpha_cli import _artifacts, _runner
        from alpha_web.app import create_app

        records = {}
        for case, wealth in {
            "later_valuations": (900.0, 950.0, 1000.0),
            "first_loss": (1000.0, 900.0, 1000.0),
            "malformed_source": (float("nan"), 950.0, 1000.0),
            "disordered_clocks": (950.0, 900.0, 1000.0),
        }.items():
            timestamps = [datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3)]
            if case == "disordered_clocks":
                timestamps = [timestamps[1], timestamps[0], timestamps[2]]
            frame = pl.DataFrame(
                {
                    "ts": timestamps,
                    "equity": wealth,
                },
                schema={"ts": pl.Datetime("us", "UTC"), "equity": pl.Float64()},
            )
            buffer = io.BytesIO()
            frame.write_parquet(buffer)
            encoded = buffer.getvalue()
            digest = hashlib.sha256(encoded).hexdigest()
            identity = _runner.run_identity_for(
                {"command": "SYNTHETIC_C04_NO_FIT", "case": case}, source_fingerprint=digest
            )
            directory = data / "runs" / identity.run_id
            directory.mkdir(parents=True)
            (directory / "equity_curve.parquet").write_bytes(encoded)
            _artifacts.write_manifest(
                directory,
                {
                    "run_id": identity.run_id,
                    "command": "SYNTHETIC_C04_NO_FIT",
                    "symbol": "SYNTHETIC-C04",
                    "data_origin": "artificial_fixture",
                    "status": "synthetic_unadmitted",
                    "case": case,
                    "metadata": {"starting_cash": 1000.0},
                    **identity.manifest_fields(),
                },
            )
            records[case] = {"run_id": identity.run_id, "equity_sha256": digest}
        (root / "synthetic-runs.json").write_text(json.dumps(records, indent=2) + "\n")
        (root / "server-context.json").write_text(
            json.dumps(
                {
                    "composition": "disposable compiled assets + unchanged create_app API",
                    "data_origin": "synthetic only; no fit/study/admission",
                    "cli_executable": shutil.which("alpha"),
                    "source_roots": [str(path) for path in source_roots],
                    "data_dir": str(data),
                    "allowed_api_reads": ["/api/risk/scenario", "/api/runs", "/api/runs/*"],
                },
                indent=2,
            )
            + "\n"
        )

        async def index(request: Request) -> Response:
            del request
            return FileResponse(build / "index.html", media_type="text/html")

        # Static routing only: all risk/run requests reach the real production app.
        application = Starlette(
            routes=[
                Route("/", index),
                Route("/app", index),
                Mount("/static/app", StaticFiles(directory=build)),
                Mount("/", create_app()),
            ]
        )

        async def isolated_reads(request: Request, call_next: RequestResponseEndpoint) -> Response:
            allowed = request.method in {"GET", "HEAD"}
            if request.url.path.startswith("/api/"):
                allowed = allowed and (
                    request.url.path == "/api/risk/scenario"
                    or request.url.path == "/api/runs"
                    or request.url.path.startswith("/api/runs/")
                )
            if allowed:
                response = await call_next(request)
            else:
                response = JSONResponse(
                    {"detail": "Synthetic risk acceptance read boundary"}, status_code=403
                )
            with (root / "http-requests.jsonl").open("a") as log:
                log.write(
                    json.dumps(
                        {
                            "method": request.method,
                            "path": request.url.path,
                            "query": request.url.query,
                            "status": response.status_code,
                            "isolation_allowed": allowed,
                        }
                    )
                    + "\n"
                )
            return response

        application.add_middleware(BaseHTTPMiddleware, dispatch=isolated_reads)
        uvicorn.run(application, host="127.0.0.1", port=8857, log_level="warning")


if __name__ == "__main__":
    main()
