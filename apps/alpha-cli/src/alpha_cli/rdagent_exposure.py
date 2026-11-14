"""Append-only disclosures of RD-Agent idea-family exposures; no admission authority."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from alpha_cli.rdagent_factor_eval import LABEL, LOOP_UNIVERSE, _read_ledger, canonical, outside_git
from alpha_core import DataError

SCHEMA = "AlphaExposureEntryV1"
SEVERITY = {"none": 0, "unknown": 1, "suspected": 2, "known": 3}
ENTRY_FIELDS = {
    "schema",
    "entry_index",
    "family",
    "match",
    "instruments",
    "window",
    "statistic_released",
    "seen_by",
    "seen_on",
    "source",
    "status",
    "note",
    "label",
}


def exposure_log_path(ledger: Path) -> Path:
    return ledger.parent / "rdagent-exposure-log.jsonl"


def _log_path(ledger: Path) -> Path:
    outside_git(ledger)
    path = exposure_log_path(ledger)
    outside_git(path)
    # Also check an existing symlink's destination, rather than only its containing directory.
    outside_git(path.resolve())
    return path


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _texts(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(v) for v in value)


def _date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expected YYYY-MM-DD")
    return date.fromisoformat(value)


def _validate(row: Any, index: int) -> None:
    if not isinstance(row, dict) or set(row) != ENTRY_FIELDS:
        raise ValueError("invalid exposure entry fields")
    if (
        row["schema"] != SCHEMA
        or type(row["entry_index"]) is not int
        or row["entry_index"] != index
    ):
        raise ValueError("invalid exposure schema or index")
    family, match, window = row["family"], row["match"], row["window"]
    if (
        not isinstance(family, dict)
        or set(family) != {"id", "definition"}
        or not isinstance(family["id"], str)
        or not re.fullmatch("[a-z0-9-]+", family["id"])
        or not _text(family["definition"])
    ):
        raise ValueError("invalid economic family")
    if (
        not isinstance(match, dict)
        or set(match) != {"name_regex", "instruments"}
        or not _text(match["name_regex"])
        or not _texts(match["instruments"])
        or ("*" in match["instruments"] and match["instruments"] != ["*"])
    ):
        raise ValueError("invalid exposure match")
    re.compile(match["name_regex"], re.IGNORECASE)
    if not _texts(row["instruments"]):
        raise ValueError("invalid exposure instruments")
    if not isinstance(window, dict) or set(window) != {"start", "end"}:
        raise ValueError("invalid exposure window")
    if _date(window["start"]) > _date(window["end"]):
        raise ValueError("exposure window is reversed")
    _date(row["seen_on"])
    if any(not _text(row[k]) for k in ("statistic_released", "source")) or not _texts(
        row["seen_by"]
    ):
        raise ValueError("invalid exposure disclosure")
    if not isinstance(row["status"], str) or row["status"] not in {"known", "suspected", "unknown"}:
        raise ValueError("invalid exposure status")
    if not isinstance(row["note"], str) or row["label"] != LABEL:
        raise ValueError("invalid exposure note or label")


def read_entries(ledger: Path) -> list[dict[str, Any]] | None:
    """Strictly read the adjacent log; None distinguishes a missing log from an empty one."""
    return snapshot(ledger)[0]


def entries_from_bytes(raw: bytes) -> list[dict[str, Any]]:
    """Validate one byte snapshot, also used to bind evaluator input hashes to labels."""
    if raw and not raw.endswith(b"\n"):
        raise DataError("incomplete exposure log line")
    entries = []
    for index, line in enumerate(raw.splitlines(), 1):
        try:
            row = json.loads(line)
            _validate(row, index)
        except (ValueError, TypeError, KeyError, UnicodeError, re.error) as error:
            raise DataError(f"invalid exposure log line {index}: {error}") from error
        entries.append(row)
    return entries


def snapshot(ledger: Path) -> tuple[list[dict[str, Any]] | None, bytes | None]:
    """Read once so the returned entries and hash input always describe the same bytes."""
    path = _log_path(ledger)
    if not path.exists():
        return None, None
    lock_path = Path(str(path) + ".lock")
    if not lock_path.exists():  # reading never creates files; `add` always creates the lock
        raw = path.read_bytes()
        return entries_from_bytes(raw), raw
    # Shared lock: `add` appends line by line under the exclusive lock on the same file.
    with lock_path.open("rb") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        raw = path.read_bytes()
    return entries_from_bytes(raw), raw


def label_for(trial_row: dict[str, Any], entries: list[dict[str, Any]] | None) -> dict[str, Any]:
    if entries is None:
        return {"previously_exposed": None, "worst_status": "no exposure log", "matches": []}
    start = trial_row["windows"]["reserved_start"]
    instruments = set(trial_row.get("instruments", LOOP_UNIVERSE))
    matches = [
        {"entry_index": e["entry_index"], "family_id": e["family"]["id"], "status": e["status"]}
        for e in entries
        if e["window"]["end"] >= start
        and re.search(e["match"]["name_regex"], trial_row["name"], re.IGNORECASE) is not None
        and (
            e["match"]["instruments"] == ["*"]
            or instruments.intersection(e["match"]["instruments"])
        )
    ]
    worst = max((m["status"] for m in matches), key=SEVERITY.__getitem__, default="none")
    return {
        "protected_window_start": start,
        "previously_exposed": worst in {"known", "suspected"},
        "worst_status": worst,
        "matches": matches,
    }


def add(ledger: Path, source: Path) -> list[dict[str, Any]]:
    path = _log_path(ledger)
    try:
        items = json.loads(source.read_bytes())
    except (ValueError, UnicodeError) as error:
        raise DataError(f"invalid exposure input: {error}") from error
    if not isinstance(items, list) or not items:
        # An empty log would read as "no exposure" rather than "no exposure log".
        raise DataError("exposure input must be a non-empty list")
    with Path(str(path) + ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        raw = path.read_bytes() if path.exists() else b""
        history = entries_from_bytes(raw)
        contents = {canonical({k: v for k, v in r.items() if k != "entry_index"}) for r in history}
        rows: list[dict[str, Any]] = []
        for item in items:
            index = len(history) + len(rows) + 1
            try:
                if not isinstance(item, dict) or set(item) != ENTRY_FIELDS - {
                    "schema",
                    "entry_index",
                    "label",
                }:
                    raise ValueError("invalid new exposure fields")
                row = {**item, "schema": SCHEMA, "entry_index": index, "label": LABEL}
                _validate(row, index)
                content = canonical({k: v for k, v in row.items() if k != "entry_index"})
                if content in contents:
                    raise ValueError("duplicate exposure content")
            except (ValueError, TypeError, KeyError, re.error) as error:
                raise DataError(f"invalid new exposure entry {index}: {error}") from error
            contents.add(content)
            rows.append(row)
        with path.open("ab", buffering=0) as stream:
            for row in rows:
                line = canonical(row)
                if stream.write(line) != len(line):
                    raise DataError("short exposure log write")
                os.fsync(stream.fileno())
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    adding = sub.add_parser("add")
    adding.add_argument("--ledger", type=Path, required=True)
    adding.add_argument("--file", type=Path, required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--ledger", type=Path, required=True)
    listing.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "add":
        for row in add(args.ledger, args.file):
            print(canonical(row).decode(), end="")
        return
    entries = read_entries(args.ledger)
    trials = [
        {
            "trial_index": r["trial_index"],
            "name": r["name"],
            "status": r["status"],
            "exposure": label_for(r, entries),
        }
        for r in _read_ledger(args.ledger)
    ]
    if args.json:
        print(canonical({"entries": entries or [], "trials": trials}).decode(), end="")
        return
    for e in entries or []:
        print(
            f"#{e['entry_index']} {e['status']} {e['family']['id']} "
            f"{e['window']['start']}..{e['window']['end']} {','.join(e['instruments'])}"
        )
    for t in trials:
        exposure = t["exposure"]
        label = (
            "previously exposed"
            if exposure["previously_exposed"]
            else "previously_exposed=" + str(exposure["previously_exposed"])
        )
        print(f"{t['trial_index']} {t['name']} {t['status']} {label} ({exposure['worst_status']})")


if __name__ == "__main__":
    main()
