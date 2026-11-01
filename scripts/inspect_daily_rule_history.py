"""Explicit-root metadata inspection; never initialize, migrate or authorize a store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alpha_cli.control_store import ControlStore
from alpha_core import DataError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, required=True, help="existing authoritative data root"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        history = ControlStore(args.data_dir).daily_rule_history(
            limit=args.limit, offset=args.offset
        )
    except DataError as exc:
        parser.exit(2, f"History inspection blocked: {exc}\n")
    print(json.dumps(history, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
