"""Run the real Workstation backend against an isolated disposable store for Playwright."""

from __future__ import annotations

import os
import tempfile

import uvicorn


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="alpha-playwright-real-") as data_dir:
        os.environ["ALPHA_DATA_DIR"] = data_dir
        os.environ["ALPHA_WEB_PORT"] = "8802"
        os.environ["ALPHA_PAPER_ENABLED"] = "false"
        os.environ["ALPHA_IBKR_PAPER_ENABLED"] = "false"
        for name in (
            "ALPHA_TIINGO_API_KEY",
            "QUANTPAD_API_KEY",
            "ALPHA_FINNHUB_API_KEY",
            "TWS_USERNAME",
            "TWS_PASSWORD",
            "ALPHA_IBKR_PAPER_ACCOUNT",
            "ALPHA_IBKR_GATEWAY_IMAGE",
        ):
            os.environ.pop(name, None)
        uvicorn.run(
            "alpha_web.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=8802,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
