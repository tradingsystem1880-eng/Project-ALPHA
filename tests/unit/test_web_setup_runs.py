"""Synthetic stored setup records; no engine, subprocess, network or TestClient."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_web import _setup_runs

FIND = "a" * 16
STUDY = "b" * 16
TRADE = "c" * 16


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False))


def find_fixture(home: Path, find_id: str = FIND) -> Path:
    folder = home / "setups" / find_id
    write_json(
        folder / "manifest.json",
        {
            "schema": "AlphaSetupFindV1",
            "find_id": find_id,
            "spec_sha256": "d" * 64,
            "name": "Synthetic pullback",
            "idea": "A synthetic pullback after a rise.",
            "recorded_at": "2026-11-01T00:00:00+00:00",
            "labels": ["daily-only"],
            "assets": [
                {
                    "asset": "SYN",
                    "first_bar": "2020-01-01T00:00:00+00:00",
                    "last_bar": "2026-10-31T00:00:00+00:00",
                }
            ],
            "files": {"candidates": "candidates.parquet", "summary": "summary.json", "sheets": []},
        },
    )
    write_json(folder / "spec.json", {"setup": {"idea": "Synthetic idea"}})
    write_json(
        folder / "summary.json",
        {"find_id": find_id, "labels": ["daily-only"], "totals": {"accepted": 1, "rejected": 1}},
    )
    pl.DataFrame(
        {
            "candidate_id": [1, 2],
            "symbol": ["SYN", "SYN"],
            "event_ts": ["2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00"],
            "status": ["accepted", "rejected"],
            "reason": [None, "no-trigger"],
            "entry_price": [12.5, None],
        }
    ).write_parquet(folder / "candidates.parquet")
    return folder


def outcome_fixture(home: Path, kind: str, **fields: Any) -> Path:
    trade = kind == "trade"
    run_id = TRADE if trade else STUDY
    folder = home / ("setup-trades" if trade else "setup-studies") / run_id
    summary: dict[str, Any] = {
        f"{kind}_id": run_id,
        "find_id": FIND,
        "spec_sha256": "d" * 64,
        "labels": ["too-few-occurrences", "remeasured-new-cost-rule"],
        "costs": {"SYN": {"fee_bps": 1, "slippage_bps": 2}},
        "total_trials": 7,
        "occurrences": 1,
    }
    if trade:
        summary["pooled"] = {"trades": 1, "mean": -0.02}
    else:
        summary["curve"] = {
            "mean": [0, -0.02, None],
            "drift": [0, 0.01, None],
            "lower": [0, -0.03, None],
            "upper": [0, 0.03, None],
        }
    write_json(folder / "summary.json", summary)
    row = {
        "asset": "SYN",
        "candidate_id": 1,
        "entry_price": 12.5,
        "stop": 12.2,
        "target": 13.0,
        "exit_price": 12.2,
        "reason": "stop",
        "net_return": -0.02,
        "complete": True,
    }
    parquet = "trades.parquet" if trade else "outcomes.parquet"
    pl.DataFrame([{**row, **fields}]).write_parquet(folder / parquet)
    # Valid PNG signature is enough for the reader; no image is generated here.
    png = "trades.png" if trade else "event-study.png"
    (folder / png).write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    files = {
        name: {
            "size": (folder / name).stat().st_size,
            "sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest(),
        }
        for name in ("summary.json", parquet, png)
    }
    write_json(
        folder / "manifest.json",
        {
            "schema": "AlphaSetupTradeV1" if trade else "AlphaSetupStudyV1",
            f"{kind}_id": run_id,
            "find_id": FIND,
            "spec_sha256": "d" * 64,
            "files": files,
            "labels": summary["labels"],
        },
    )
    return folder


def test_empty_store_and_newest_first(tmp_path: Path) -> None:
    assert _setup_runs.list_runs(tmp_path).items == []
    find_fixture(tmp_path)
    newer = find_fixture(tmp_path, "e" * 16)
    manifest = json.loads((newer / "manifest.json").read_text())
    manifest["recorded_at"] = "2026-11-02T00:00:00+00:00"
    write_json(newer / "manifest.json", manifest)
    items = _setup_runs.list_runs(tmp_path).items
    assert [row.find_id for row in items] == ["e" * 16, FIND]
    assert items[0].description == "A synthetic pullback after a rise."


def test_reads_candidates_curves_trades_costs_and_missing_bars(tmp_path: Path) -> None:
    find_fixture(tmp_path)
    outcome_fixture(tmp_path, "study")
    outcome_fixture(tmp_path, "trade")
    detail = _setup_runs.read_run(tmp_path, FIND)
    assert detail.candidates is not None
    assert detail.candidates[1]["reason"] == "no-trigger"
    assert detail.price_bars is None
    assert "not recorded" in detail.price_bars_reason
    assert detail.studies[0].summary is not None
    assert detail.studies[0].summary["curve"] == {
        "mean": [0, -0.02, None],
        "drift": [0, 0.01, None],
        "lower": [0, -0.03, None],
        "upper": [0, 0.03, None],
    }
    trade = detail.trades[0]
    assert trade.rows is not None and trade.rows[0]["net_return"] == -0.02
    assert trade.summary is not None and trade.summary["costs"] == {
        "SYN": {"fee_bps": 1, "slippage_bps": 2}
    }
    assert "too-few-occurrences" in trade.labels
    assert trade.run_id == TRADE
    assert trade.trial_indices is None  # A recorded trial count is not a trial identifier.


def test_missing_is_distinct_from_empty_and_corruption(tmp_path: Path) -> None:
    folder = find_fixture(tmp_path)
    pl.DataFrame(schema={"candidate_id": pl.Int64}).write_parquet(folder / "candidates.parquet")
    assert _setup_runs.read_run(tmp_path, FIND).candidates == []
    (folder / "candidates.parquet").unlink()
    assert _setup_runs.read_run(tmp_path, FIND).candidates is None
    (folder / "summary.json").write_text("broken")
    with pytest.raises(ValueError):
        _setup_runs.read_run(tmp_path, FIND)


@pytest.mark.parametrize("run_id", ["../outside", "/tmp", "f" * 16])
def test_unknown_ids_cannot_select_paths(tmp_path: Path, run_id: str) -> None:
    find_fixture(tmp_path)
    with pytest.raises(FileNotFoundError):
        _setup_runs.read_run(tmp_path, run_id)


def test_rejects_symlink_artifacts_and_tampered_outcomes(tmp_path: Path) -> None:
    folder = find_fixture(tmp_path)
    (folder / "summary.json").unlink()
    (folder / "summary.json").symlink_to(folder / "spec.json")
    with pytest.raises(ValueError, match="symlink"):
        _setup_runs.read_run(tmp_path, FIND)
    (folder / "summary.json").unlink()
    write_json(folder / "summary.json", {})
    study = outcome_fixture(tmp_path, "study")
    write_json(study / "summary.json", {"mean": 999})
    with pytest.raises(ValueError, match="integrity"):
        _setup_runs.read_run(tmp_path, FIND)


def test_nonfinite_and_oversize_records_fail_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = find_fixture(tmp_path)
    (folder / "summary.json").write_text('{"value": NaN}')
    with pytest.raises(ValueError):
        _setup_runs.read_run(tmp_path, FIND)
    write_json(folder / "summary.json", {})
    monkeypatch.setattr(_setup_runs, "MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="limit"):
        _setup_runs.list_runs(tmp_path)


def test_direct_routes_return_typed_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    from alpha_web.api import setup_runs

    monkeypatch.setattr(setup_runs, "data_dir", lambda: tmp_path)
    assert setup_runs.list_runs().items == []
    with pytest.raises(HTTPException) as missing:
        setup_runs.run_detail(FIND)
    assert missing.value.status_code == 404
    folder = find_fixture(tmp_path)
    assert setup_runs.run_detail(FIND).run.find_id == FIND
    (folder / "summary.json").write_text("bad JSON")
    with pytest.raises(HTTPException) as corrupt:
        setup_runs.run_detail(FIND)
    assert corrupt.value.status_code == 422


def test_trial_labels_remain_attached_to_their_recorded_trial(tmp_path: Path) -> None:
    find_fixture(tmp_path)
    outcome_fixture(tmp_path, "trade")
    path = tmp_path / "ledger" / "trials.jsonl"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "schema": "AlphaTrialV1",
                "trial_index": 1,
                "total_trials": 1,
                "kind": "setup_trade",
                "trade_id": TRADE,
                "labels": ["repeat"],
            }
        )
        + "\n"
    )
    detail = _setup_runs.read_run(tmp_path, FIND)
    assert detail.trades[0].trial_labels == {"1": ["repeat"]}


def test_total_read_budget_and_trial_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    find_fixture(tmp_path)
    outcome_fixture(tmp_path, "trade")
    ledger = tmp_path / "ledger" / "trials.jsonl"
    ledger.parent.mkdir()
    ledger.write_text(
        json.dumps(
            {
                "schema": "AlphaTrialV1",
                "trial_index": 1,
                "total_trials": 1,
                "kind": "setup_trade",
                "find_id": FIND,
                "trade_id": TRADE,
                "run_id": TRADE,
            }
        )
        + "\n"
    )
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert _setup_runs.read_run(tmp_path, FIND).trades[0].trial_indices == [1]
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    monkeypatch.setattr(_setup_runs, "MAX_READ_BYTES", 1)
    with pytest.raises(ValueError, match="limit"):
        _setup_runs.read_run(tmp_path, FIND)


def test_trade_fields_round_trip_and_old_rows_stay_unknown(tmp_path: Path) -> None:
    find_fixture(tmp_path)
    outcome_fixture(tmp_path, "trade")
    old = _setup_runs.read_run(tmp_path, FIND).trades[0].rows
    fields = dict(direction="short", risk_fraction=0.01, r_multiple=-2.0)
    assert old and all(old[0].get(key) is None for key in fields)
    outcome_fixture(tmp_path, "trade", **fields)
    detail = _setup_runs.read_run(tmp_path, FIND)
    rows = detail.trades[0].rows
    assert rows and {k: rows[0][k] for k in fields} == fields
    for label in ("short-costs-assumed", "short-needs-perpetual"):
        assert detail.label_explanations[label]


def test_the_context_label_is_explained_in_plain_words() -> None:
    assert "less than three years" in _setup_runs.LABELS["short-context-history"]


def test_reserved_period_labels_are_explained() -> None:
    assert _setup_runs.LABELS["reserved-period-held-back"] == (
        "Data from 2024-01-01 on was held back for the owner's confirmation."
    )
    assert _setup_runs.LABELS["reserved-period-seen"] == (
        "This run used data from 2024-01-01 on, before that data was held back. "
        "It is not a fresh test on that period."
    )


def test_a_stored_outcome_reads_as_the_command_lines_evidence_word(tmp_path: Path) -> None:
    find_fixture(tmp_path)
    folder = outcome_fixture(tmp_path, "study")
    summary = json.loads((folder / "summary.json").read_text())
    summary |= {"idea": "Volume spike", "outcome": "not supported", "evidence": "some evidence"}
    write_json(folder / "summary.json", summary)
    manifest = json.loads((folder / "manifest.json").read_text())
    data = (folder / "summary.json").read_bytes()
    manifest["files"]["summary.json"] = {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    write_json(folder / "manifest.json", manifest)
    found = _setup_runs.read_run(tmp_path, FIND).studies[0].reading
    assert found is not None
    assert (found.evidence, found.old_wording) == ("some evidence", False)
    assert found.family_position is None  # no ledger row of this study; the CLI counts them


def test_only_the_first_match_sheet_rides_with_the_detail(tmp_path: Path) -> None:
    folder = find_fixture(tmp_path)
    names = ["sheets/accepted-001.png", "sheets/accepted-002.png"]
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["files"]["sheets"] = names
    write_json(folder / "manifest.json", manifest)
    for name in names:
        (folder / name).parent.mkdir(exist_ok=True)
        (folder / name).write_bytes(b"\x89PNG\r\n\x1a\nsheet")
    detail = _setup_runs.read_run(tmp_path, FIND)
    assert detail.sheets is not None
    assert [(s.name, s.png is not None, s.deferred or False) for s in detail.sheets] == [
        (names[0], True, False),
        (names[1], False, True),
    ]
    assert _setup_runs.read_sheet(tmp_path, FIND, names[1]).png is not None
    with pytest.raises(FileNotFoundError):
        _setup_runs.read_sheet(tmp_path, FIND, "sheets/rejected-009.png")
    with pytest.raises(ValueError):
        _setup_runs.read_sheet(tmp_path, FIND, "../summary.json")
