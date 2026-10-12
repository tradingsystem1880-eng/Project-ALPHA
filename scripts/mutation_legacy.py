"""Export completed pinned mutmut 2 measurements for module-level-only source."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def export_stats(cache: Path, module: str) -> dict[str, Any]:
    # The backend is pinned to 2.5.1; use its read-only cache schema and fail on drift.
    with sqlite3.connect(cache.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT SourceFile.filename, Mutant.status, Mutant.tested_against_hash "
            "FROM Mutant JOIN Line ON Mutant.line = Line.id "
            "JOIN SourceFile ON Line.sourcefile = SourceFile.id"
        ).fetchall()
    if not rows:
        raise ValueError("No actual module-level mutants measured")
    statuses = {
        "ok_killed": "killed",
        "bad_survived": "survived",
        "bad_timeout": "timeout",
        "ok_suspicious": "suspicious",
        "skipped": "skipped",
    }
    stats = dict.fromkeys(("killed", "survived", "timeout", "suspicious", "skipped", "no_tests"), 0)
    for filename, status, tested in rows:
        if filename != module or status not in statuses or not tested or tested == "NO TESTS FOUND":
            raise ValueError("Wrong module or unfinished legacy mutation")
        stats[statuses[status]] += 1
    return {**stats, "total": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    args = parser.parse_args()
    stats = export_stats(Path(".mutmut-cache"), args.module)
    target = Path("mutants/mutmut-cicd-stats.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
