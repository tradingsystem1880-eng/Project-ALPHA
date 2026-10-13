"""Run the real Workstation backend against an isolated disposable store for Playwright."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

import uvicorn


def playwright_port() -> int:
    raw = os.environ.get("ALPHA_PLAYWRIGHT_PORT", "8802")
    if not re.fullmatch(r"[0-9]{4,5}", raw) or not 1024 <= int(raw) <= 65535 or int(raw) == 8801:
        raise ValueError("ALPHA_PLAYWRIGHT_PORT must be 1024..65535, excluding owner port 8801")
    return int(raw)


def main() -> None:
    port = playwright_port()
    with tempfile.TemporaryDirectory(prefix="alpha-playwright-real-") as data_dir:
        os.environ["ALPHA_DATA_DIR"] = data_dir
        os.environ["ALPHA_BULK_DATA_DIR"] = str(Path(data_dir) / "bulk")
        os.environ["ALPHA_WEB_PORT"] = str(port)
        os.environ["ALPHA_PAPER_ENABLED"] = "false"
        os.environ["ALPHA_IBKR_PAPER_ENABLED"] = "false"
        for name in (
            "ALPHA_TIINGO_API_KEY",
            "QUANTPAD_API_KEY",
            "TWS_USERNAME",
            "TWS_PASSWORD",
            "ALPHA_IBKR_PAPER_ACCOUNT",
            "ALPHA_IBKR_GATEWAY_IMAGE",
        ):
            os.environ.pop(name, None)
        # Labelled synthetic bars preserve current real browser-to-CLI chart journeys.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tests.fixtures.cli_fixtures import seed_store

        seed_store(Path(data_dir), symbol="SPY", n=400)
        seed_store(Path(data_dir), symbol="BTC/USDT", n=400)
        original_cwd = Path.cwd()
        try:
            # App construction and children must not load the owner's .env through cwd.
            os.chdir(data_dir)
            from playwright_investigation_fixture import install

            from alpha_web.app import create_app

            application = create_app()
            install(application, Path(data_dir))
            uvicorn.run(application, host="127.0.0.1", port=port, log_level="warning")
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    main()
