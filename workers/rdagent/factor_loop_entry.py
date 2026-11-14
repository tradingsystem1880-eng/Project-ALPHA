"""Isolated entry into the pinned upstream factor loop, using external class settings."""

from __future__ import annotations

import sys
from pathlib import Path

# -I removes the script directory: add only ALPHA's worker scripts, never the source root.
WORKER = Path(__file__).resolve().parent
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from source_pin import verify_source  # noqa: E402
from stock_fixture_entry import SourceFinder  # noqa: E402


def install_source(source: Path) -> str:
    identity = verify_source(source)
    sys.meta_path.insert(0, SourceFinder(source))
    return identity


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in {"1", "2", "3"}:
        raise ValueError("usage: factor_loop_entry.py <source> <loop_n: 1..3>")
    install_source(Path(sys.argv[1]))
    from rdagent.app.qlib_rd_loop.factor import main as factor_main

    factor_main(loop_n=int(sys.argv[2]))


if __name__ == "__main__":
    main()
