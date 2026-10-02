"""Run the real Workstation backend against an isolated disposable store for Playwright."""

from __future__ import annotations

import os
import re
import tempfile

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
        uvicorn.run(
            "alpha_web.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
