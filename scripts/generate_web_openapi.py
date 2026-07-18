"""Generate the committed deterministic OpenAPI contract for the workstation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from alpha_web.app import create_app


def main() -> None:
    output = Path(__file__).parents[1] / "apps" / "alpha-web" / "frontend" / "openapi.json"
    rendered = json.dumps(create_app().openapi(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if "--check" in sys.argv:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("committed OpenAPI is stale; run scripts/generate_web_openapi.py")
        return
    output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
