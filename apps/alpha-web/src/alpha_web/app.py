"""FastAPI application factory + entry point for the ALPHA web IDE.

Routes are added in vertical slices (run browser, run detail, launcher, console). The server binds
loopback only — local single-user, no auth.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the FastAPI app (factory so tests can construct a fresh instance)."""
    app = FastAPI(title="Project ALPHA — Web IDE")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


def main() -> None:
    """Entry point: serve the web IDE on http://127.0.0.1:8800 (loopback only)."""
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8800)


if __name__ == "__main__":
    main()
