"""Validate weekly measurements; below-floor results remain report-only."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def validate_report(payload: object, module: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Mutation report must be an object")
    modules = payload.get("modules")
    if not isinstance(modules, dict) or set(modules) != {module}:
        raise ValueError(f"Mutation report must contain exactly {module}")
    entry = modules[module]
    if not isinstance(entry, dict) or entry.get("status") not in {"pass", "fail"}:
        raise ValueError("Mutation measurements unavailable or status invalid")
    for name, value in [("min_kill", payload.get("min_kill"))] + [
        (name, entry.get(name)) for name in ("kill_rate", "required", "seconds")
    ]:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
            or (name != "seconds" and value > 1)
        ):
            raise ValueError(f"Invalid mutation measurement: {name}")
    for name in ("killed", "survived", "total", "no_tests", "timeout"):
        value = entry.get(name)
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid mutation count: {name}")
    extra = ("skipped", "suspicious", "segfault", "check_was_interrupted_by_user")
    for name in extra:
        value = entry.get(name, 0)
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid mutation count: {name}")
    measured = sum(entry[name] for name in ("killed", "survived", "no_tests", "timeout"))
    measured += sum(entry.get(name, 0) for name in extra)
    if measured != entry["total"] or entry.get("check_was_interrupted_by_user", 0):
        raise ValueError("Mutation counts unfinished or inconsistent with total")
    denominator = entry["total"] - entry.get("skipped", 0)
    rate = entry["killed"] / denominator if denominator > 0 else 0.0
    if abs(round(rate, 4) - entry["kill_rate"]) > 0.00001 or payload["min_kill"] != 0.90:
        raise ValueError("Mutation score inconsistent with conservative counts or minimum")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_mutation_report.py REPORT.json MODULE")
    validate_report(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])


if __name__ == "__main__":
    main()
