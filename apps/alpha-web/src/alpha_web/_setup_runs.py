"""Bounded read-only projection of immutable setup artifacts; no research computation."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from alpha_core.reserve import RESERVED_START
from alpha_web._catalog import _run_json
from alpha_web.api.models.setup_runs import (
    SetupFigure,
    SetupOutcome,
    SetupReading,
    SetupRun,
    SetupRunDetail,
    SetupRunList,
)

MAX_READ_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_RUNS = 10_000
MAX_ROWS = 100_000
ID = re.compile(r"[0-9a-f]{16}")
LIMITS = [
    "Setup find: Nothing about what happened after entry: no return, exit or control is computed. "
    "A match count is not evidence of an edge.",
    "Setup find: Daily bars only; the evaluator records the day a pattern became known, "
    "not the dates of its own lows.",
    "Setup study: Exits, sizing, portfolios, dividends or reserved-data confirmation. "
    "Setups cluster in market states (a double bottom follows a decline): beating random "
    "dates says the dates were unusual, not that the setup can be traded.",
    "Setup trade: Currency position sizing, dividends, actual borrow or funding rates, portfolios "
    "or confirmation on reserved data. Unusual dates are not proof that the setup can be traded.",
]
LABELS = {
    "data-health-pass": "The data checks found no fault. The prices can still be wrong.",
    "data-health-warn": "A data check found a warning. Read the finding before using this result.",
    "data-health-fail": "A data check found a fault in the prices or their supporting records.",
    "data-health-unchecked": "At least one series has no current data health report.",
    "data-health-overridden": "The run records why it proceeded after a failed data check.",
    "exploratory": "An exploratory look; this does not confirm an edge.",
    "daily-only": "Only daily bars were used.",
    "dev-machine-data": "Uses data stored on the development machine.",
    "source-defaulted": "The source was selected by the stored-data default.",
    "short-history": "The recorded data spans less than three years.",
    "short-context-history": "The condition data spans less than three years; read it as a hint.",
    "outcomes-not-viewed": "This find recorded that outcomes had not been viewed.",
    "outcomes-viewed": "Outcomes have been viewed in a study or trade run.",
    "pending-at-end": "Some candidates were still waiting at the end of the data.",
    "sheets-truncated": "The sheet cap was reached; not every occurrence is pictured.",
    "too-few-occurrences": "Fewer than 30 complete occurrences or trades; too few to judge.",
    "too-few-trades": "Too few completed trades to judge; keep the recorded cap beside the result.",
    "single-asset": "Only one instrument was studied.",
    "overlapping-outcomes": "Some outcome windows overlap and are not independent.",
    "halves-disagree": "The two chronological halves have average returns with opposite signs.",
    "no-time-exit": "No time exit was declared; the tool uses its 250-bar limit.",
    "no-random-control": "The random-date comparison is unavailable; see the stored reason.",
    "many-skipped": "More than a quarter of occurrences were skipped while already in a trade.",
    "costs-assumed-high": "Unknown market identity used the higher crypto cost assumption.",
    "short-costs-assumed": "Borrow or funding is an assumed charge per calendar day held.",
    "short-needs-perpetual": "Crypto shorts need a perpetual contract. Spot prices are a proxy.",
    "older-cost-rule": "Recorded under the earlier cost rule.",
    "remeasured-new-cost-rule": "An earlier find was measured with a new cost rule; another look.",
    "repeat": "A repeat of an earlier result, not independent evidence.",
    "reserved-period-held-back": f"Data from {RESERVED_START} on was held back for the owner's "
    "confirmation.",
    "reserved-period-seen": f"This run used data from {RESERVED_START} on, before that data was "
    "held back. It is not a fresh test on that period.",
    "not-primary": "Also looked at, not tested as the primary horizon.",
}


def _bytes(folder: Path, name: str) -> bytes | None:
    path = folder / name
    for node in (folder, path.parent, path):
        if node.is_symlink():
            raise ValueError("setup symlink is not allowed")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("setup file limit exceeded")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("setup file limit exceeded")
    return data


class _Reader:
    def __init__(self) -> None:
        self.remaining = MAX_READ_BYTES

    def read(self, folder: Path, name: str) -> bytes | None:
        data = _bytes(folder, name)
        if data is not None:
            self.remaining -= len(data)
            if self.remaining < 0:
                raise ValueError("setup total read limit exceeded")
        return data


def _normal(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite setup value")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normal(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_normal(child) for child in value]
    return value


def _object(data: bytes | None) -> dict[str, Any] | None:
    if data is None:
        return None
    value = _normal(json.loads(data))
    if not isinstance(value, dict):
        raise ValueError("setup JSON must be an object")
    return value


def _folders(home: Path, area: str) -> list[Path]:
    root = home / area
    if root.is_symlink():
        raise ValueError("setup store symlink is not allowed")
    if not root.exists():
        return []
    folders = []
    for folder in root.iterdir():
        if ID.fullmatch(folder.name):
            if folder.is_symlink():
                raise ValueError("setup run symlink is not allowed")
            if folder.is_dir():
                folders.append(folder)
        if len(folders) > MAX_RUNS:
            raise ValueError("setup run limit exceeded")
    return sorted(folders)


def _manifest(folder: Path, kind: str, reader: _Reader) -> dict[str, Any] | None:
    value = _object(reader.read(folder, "manifest.json"))
    if value is not None and (
        value.get("schema") != f"AlphaSetup{kind.title()}V1"
        or value.get(f"{kind}_id") != folder.name
    ):
        raise ValueError("setup manifest identity mismatch")
    return value


def _run(value: dict[str, Any]) -> SetupRun:
    return SetupRun(
        find_id=value["find_id"],
        description=value.get("idea"),
        name=value.get("name"),
        recorded_at=value.get("recorded_at"),
        assets=value.get("assets"),
        labels=value.get("labels", []),
    )


def list_runs(home: Path) -> SetupRunList:
    reader = _Reader()
    items = [
        _run(m)
        for folder in _folders(home, "setups")
        if (m := _manifest(folder, "find", reader)) is not None
    ]
    return SetupRunList(
        items=sorted(items, key=lambda row: (row.recorded_at or "", row.find_id), reverse=True)
    )


def _rows(data: bytes | None) -> list[dict[str, Any]] | None:
    if data is None:
        return None
    frame = pl.read_parquet(io.BytesIO(data), n_rows=MAX_ROWS + 1)
    if frame.height > MAX_ROWS:
        raise ValueError("setup row limit exceeded")
    result: list[dict[str, Any]] = _normal(frame.to_dicts())
    return result


def _figure(name: str, data: bytes | None) -> SetupFigure:
    if data is not None and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("setup figure is not a PNG")
    return SetupFigure(name=name, png=base64.b64encode(data).decode("ascii") if data else None)


def _ledger(home: Path, reader: _Reader) -> list[dict[str, Any]] | None:
    data = reader.read(home / "ledger", "trials.jsonl")
    if data is None:
        return None
    rows = []
    for index, line in enumerate(data.splitlines(keepends=True), 1):
        row = _object(line)
        if (
            row is None
            or not line.endswith(b"\n")
            or row.get("schema") != "AlphaTrialV1"
            or row.get("trial_index") != index
            or row.get("total_trials") != index
        ):
            raise ValueError("setup trial ledger is invalid")
        rows.append(row)
    return rows


def _indices(ledger: list[dict[str, Any]] | None, kind: str, run_id: str) -> list[int] | None:
    if ledger is None:
        return None
    return [
        row["trial_index"]
        for row in ledger
        if row.get("kind") == f"setup_{kind}" and row.get(f"{kind}_id") == run_id
    ]


def _readings(home: Path, outcomes: list[SetupOutcome]) -> list[SetupOutcome]:
    """Each outcome with the CLI's own reading (``alpha setup show``), from one CLI call.

    Outcomes without a stored summary get no reading. No call is made when none has one.
    """
    ids = [row.run_id for row in outcomes if row.summary is not None]
    if not ids:
        return outcomes
    try:
        shown = _run_json(["setup", "show", *ids, "--json"], data_dir=home)["readings"]
    except RuntimeError as exc:
        raise ValueError("the setup reading could not be read from the command line") from exc
    by_id = {item["id"]: item for item in shown}
    result = []
    for row in outcomes:
        item = by_id.get(row.run_id)
        if item is None:
            result.append(row)
            continue
        family = item["family"] or {}
        reading = SetupReading(
            evidence=item["evidence"],
            old_wording=item["old_wording"],
            family_position=family.get("position"),
            family_count=family.get("studies"),
        )
        result.append(row.model_copy(update={"reading": reading}))
    return result


def _outcomes(
    home: Path,
    find: dict[str, Any],
    kind: str,
    ledger: list[dict[str, Any]] | None,
    reader: _Reader,
) -> list[SetupOutcome]:
    result = []
    area = "setup-studies" if kind == "study" else "setup-trades"
    row_name = "outcomes.parquet" if kind == "study" else "trades.parquet"
    figure_name = "event-study.png" if kind == "study" else "trades.png"
    for folder in _folders(home, area):
        manifest = _manifest(folder, kind, reader)
        if manifest is None or manifest.get("find_id") != find["find_id"]:
            continue
        if manifest.get("spec_sha256") != find.get("spec_sha256"):
            raise ValueError("setup outcome spec identity mismatch")
        data = {}
        for name in ("summary.json", row_name, figure_name):
            content = reader.read(folder, name)
            data[name] = content
            if content is not None:
                expected = manifest.get("files", {}).get(name, {})
                if len(content) != expected.get("size") or hashlib.sha256(
                    content
                ).hexdigest() != expected.get("sha256"):
                    raise ValueError("setup artifact integrity mismatch")
        summary = _object(data["summary.json"])
        if summary is not None and (
            summary.get(f"{kind}_id") != folder.name or summary.get("find_id") != find["find_id"]
        ):
            raise ValueError("setup summary identity mismatch")
        labels = list(
            dict.fromkeys([*manifest.get("labels", []), *(summary or {}).get("labels", [])])
        )
        result.append(
            SetupOutcome(
                run_id=folder.name,
                rule_version=manifest.get(f"{kind}_rule_version"),
                summary=summary,
                rows=_rows(data[row_name]),
                labels=labels,
                figure=_figure(figure_name, data[figure_name]),
                trial_indices=_indices(ledger, kind, folder.name),
                trial_labels=_trial_labels(ledger, kind, folder.name),
            )
        )
    return result


def _check_sheet_name(name: object) -> None:
    if not isinstance(name, str) or not re.fullmatch(
        r"sheets/(accepted|rejected)-\d{3}\.png", name
    ):
        raise ValueError("setup sheet name is invalid")


def read_sheet(home: Path, find_id: str, name: str) -> SetupFigure:
    """One recorded match sheet of a find, by the name its manifest lists."""
    _check_sheet_name(name)
    if not ID.fullmatch(find_id) or find_id not in {row.find_id for row in list_runs(home).items}:
        raise FileNotFoundError("setup run not found")
    reader = _Reader()
    folder = home / "setups" / find_id
    manifest = _manifest(folder, "find", reader)
    listed = manifest.get("files", {}).get("sheets") if manifest else None
    if not isinstance(listed, list) or name not in listed:
        raise FileNotFoundError("setup sheet not found")
    return _figure(name, reader.read(folder, name))


def read_run(home: Path, find_id: str) -> SetupRunDetail:
    if not ID.fullmatch(find_id):
        raise FileNotFoundError("setup run not found")
    if find_id not in {row.find_id for row in list_runs(home).items}:
        raise FileNotFoundError("setup run not found")
    reader = _Reader()
    folder = home / "setups" / find_id
    manifest = _manifest(folder, "find", reader)
    if manifest is None:
        raise FileNotFoundError("setup run not found")
    ledger = _ledger(home, reader)
    names = manifest.get("files", {}).get("sheets")
    sheets: list[SetupFigure] | None = None
    if names is not None:
        if not isinstance(names, list) or len(names) > 51:
            raise ValueError("setup sheet limit exceeded")
        sheets = []
        for name in names:
            _check_sheet_name(name)
            # Only the first sheet rides along; the rest are read one at a time (`read_sheet`).
            if sheets:
                sheets.append(SetupFigure(name=name, png=None, deferred=True))
            else:
                sheets.append(_figure(name, reader.read(folder, name)))
    studies = _outcomes(home, manifest, "study", ledger, reader)
    trades = _outcomes(home, manifest, "trade", ledger, reader)
    read = _readings(home, [*studies, *trades])
    studies, trades = read[: len(studies)], read[len(studies) :]
    return SetupRunDetail(
        run=_run(manifest),
        summary=_object(reader.read(folder, "summary.json")),
        spec=_object(reader.read(folder, "spec.json")),
        candidates=_rows(reader.read(folder, "candidates.parquet")),
        price_bars_reason="Price bars: not recorded as a setup-run snapshot. "
        "The stored sheets show only selected candidates up to entry.",
        sheets=sheets,
        studies=studies,
        trades=trades,
        trial_indices=_indices(ledger, "find", find_id),
        trial_labels=_trial_labels(ledger, "find", find_id),
        limits=LIMITS,
        label_explanations=LABELS,
    )


def _trial_labels(
    ledger: list[dict[str, Any]] | None, kind: str, run_id: str
) -> dict[str, list[str]] | None:
    if ledger is None:
        return None
    return {
        str(row["trial_index"]): row["labels"]
        for row in ledger
        if row.get("kind") == f"setup_{kind}"
        and row.get(f"{kind}_id") == run_id
        and "labels" in row
    }
