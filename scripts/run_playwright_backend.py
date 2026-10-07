"""Run the real Workstation backend against an isolated disposable store for Playwright."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import uvicorn


def main() -> None:
    port = int(os.environ.get("ALPHA_PLAYWRIGHT_PORT", "8802"))
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid ALPHA_PLAYWRIGHT_PORT")
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
        # Labelled synthetic bars for actual offline browser-to-CLI chart/test journeys.
        # Never seed the owner store or the configured external bulk volume.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tests.fixtures.cli_fixtures import seed_store

        seed_store(Path(data_dir), symbol="SPY", n=400)
        seed_store(Path(data_dir), symbol="BTC/USDT", n=400)
        # Do not inherit the owner's .env file through cwd in either server or CLI children.
        os.chdir(data_dir)
        uvicorn.run(
            "alpha_web.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
