"""Append-only exposure records and protected-window matching, without market data."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import rdagent_exposure as ex
from alpha_cli import rdagent_factor_eval as ev
from alpha_core import DataError


def entry() -> dict[str, Any]:
    return {
        "family": {"id": "xs-range", "definition": "Cross-sectional differences in trading range"},
        "match": {"name_regex": "range", "instruments": ["BTCUSDT"]},
        "instruments": ["BTCUSDT", "ETHUSDT"],
        "window": {"start": "2023-01-01", "end": "2024-02-01"},
        "statistic_released": "Mean rank correlation",
        "seen_by": ["owner"],
        "seen_on": "2026-11-14",
        "source": "/historical/result.json",
        "status": "known",
        "note": "",
    }


def stored(index: int = 1, **updates: Any) -> dict[str, Any]:
    return {
        **entry(),
        "schema": "AlphaExposureEntryV1",
        "entry_index": index,
        "label": ev.LABEL,
        **updates,
    }


def trial(**updates: Any) -> dict[str, Any]:
    return {"name": "RANGE_7d", "windows": ev.WINDOWS, "instruments": ["BTCUSDT"], **updates}


INVALID = [
    ("schema", "wrong"),
    ("entry_index", 2),
    ("entry_index", True),
    ("family", {}),
    ("family", {"id": "Bad slug", "definition": "Economic definition"}),
    ("family", {"id": "range", "definition": "  "}),
    ("match", {"name_regex": "[", "instruments": ["*"]}),
    ("match", {"name_regex": 3, "instruments": ["*"]}),
    ("match", {"name_regex": ".*", "instruments": "BTCUSDT"}),
    ("match", {"name_regex": ".*", "instruments": ["*", "BTCUSDT"]}),
    ("instruments", "BTCUSDT"),
    ("instruments", [3]),
    ("window", {"start": "2024-02-01", "end": "2024-01-01"}),
    ("window", {"start": "2024-1-01", "end": "2024-02-01"}),
    ("window", {"start": "2024-01-01", "end": "2024-02-30"}),
    ("statistic_released", ""),
    ("seen_by", []),
    ("seen_by", [""]),
    ("seen_on", "20261114"),
    ("source", ""),
    ("status", "certain"),
    ("note", None),
    ("label", "admitted"),
]


@pytest.mark.parametrize(("field", "value"), INVALID)
def test_strict_read_invalid_fields(tmp_path: Path, field: str, value: Any) -> None:
    ledger = tmp_path / "trials.jsonl"
    row = stored(**{field: value})
    ex.exposure_log_path(ledger).write_bytes(ev.canonical(row))
    with pytest.raises(DataError):
        ex.read_entries(ledger)


@pytest.mark.parametrize("field", list(stored()))
def test_strict_read_requires_every_field(tmp_path: Path, field: str) -> None:
    ledger = tmp_path / "trials.jsonl"
    row = stored()
    del row[field]
    ex.exposure_log_path(ledger).write_bytes(ev.canonical(row))
    with pytest.raises(DataError):
        ex.read_entries(ledger)


@pytest.mark.parametrize(
    "raw",
    [
        b"{bad json}\n",
        b"[]\n",
        ev.canonical(stored())[:-1],
        ev.canonical(stored()) + ev.canonical(stored(3)),
    ],
)
def test_strict_read_rejects_broken_lines(tmp_path: Path, raw: bytes) -> None:
    ledger = tmp_path / "trials.jsonl"
    ex.exposure_log_path(ledger).write_bytes(raw)
    with pytest.raises(DataError):
        ex.read_entries(ledger)


def invoke(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["rdagent_exposure", *args])
    ex.main()


def test_add_is_append_only_and_atomic_on_validation_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger, source = tmp_path / "trials.jsonl", tmp_path / "entries.json"
    source.write_text(json.dumps([entry()]))
    args = ("add", "--ledger", str(ledger), "--file", str(source))
    invoke(monkeypatch, *args)
    path = ex.exposure_log_path(ledger)
    before = path.read_bytes()
    assert before == ev.canonical(stored()) == capsys.readouterr().out.encode()
    changed = {**entry(), "note": "A separate release"}
    for entries in (
        [changed, entry()],
        [changed, {**entry(), "status": "bad"}],
        [changed, changed],
    ):
        source.write_text(json.dumps(entries))
        with pytest.raises(DataError):
            invoke(monkeypatch, *args)
        assert path.read_bytes() == before
    source.write_text(json.dumps([changed]))
    invoke(monkeypatch, *args)
    assert path.read_bytes() == before + ev.canonical(stored(2, note=changed["note"]))
    loaded = ex.read_entries(ledger)
    assert loaded is not None
    assert len(loaded) == 2


def test_log_must_be_absolute_and_outside_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for path in (Path("trials.jsonl"), tmp_path / "trials.jsonl"):
        with pytest.raises(DataError):
            ex.read_entries(path)


def test_labels_match_windows_regex_and_instruments() -> None:
    matched = stored()
    assert ex.label_for(trial(), [matched]) == {
        "protected_window_start": "2024-01-01",
        "previously_exposed": True,
        "worst_status": "known",
        "matches": [{"entry_index": 1, "family_id": "xs-range", "status": "known"}],
    }
    before = stored(window={"start": "2022-01-01", "end": "2023-12-31"})
    boundary = stored(window={"start": "2024-01-01", "end": "2024-01-01"})
    assert ex.label_for(trial(), [boundary])["previously_exposed"] is True
    for row, item in [
        (trial(), before),
        (trial(name="momentum"), matched),
        (trial(instruments=["SOLUSDT"]), matched),
    ]:
        assert ex.label_for(row, [item])["worst_status"] == "none"
    wildcard = copy.deepcopy(matched)
    wildcard["match"]["instruments"] = ["*"]
    assert ex.label_for(trial(instruments=["OTHER"]), [wildcard])["previously_exposed"] is True
    legacy = trial()
    del legacy["instruments"]
    assert ex.label_for(legacy, [matched])["previously_exposed"] is True


@pytest.mark.parametrize(
    ("statuses", "worst", "exposed"),
    [
        ([], "none", False),
        (["unknown"], "unknown", False),
        (["unknown", "suspected"], "suspected", True),
        (["suspected", "known", "unknown"], "known", True),
    ],
)
def test_status_severity(statuses: list[str], worst: str, exposed: bool) -> None:
    entries = [stored(i, status=status) for i, status in enumerate(statuses, 1)]
    label = ex.label_for(trial(), entries)
    assert label["worst_status"] == worst
    assert label["previously_exposed"] is exposed
    assert [m["entry_index"] for m in label["matches"]] == list(range(1, len(entries) + 1))


def test_missing_log_is_unknown_not_empty(tmp_path: Path) -> None:
    assert ex.read_entries(tmp_path / "trials.jsonl") is None
    assert ex.label_for(trial(), None) == {
        "previously_exposed": None,
        "worst_status": "no exposure log",
        "matches": [],
    }


def test_list_json_and_plain_are_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = tmp_path / "trials.jsonl"
    ex.exposure_log_path(ledger).write_bytes(ev.canonical(stored()))
    row = {
        **trial(),
        "schema": "AlphaRdagentFactorTrialV1",
        "trial_index": 1,
        "code_sha256": "a" * 64,
        "run_id": "old",
        "iteration": 0,
        "panel_sha256": "0" * 64,
        "stage": "none",
        "status": "FAILED",
        "p": 1.0,
        "q": 1.0,
        "family_size": 1,
        "total_trials": 1,
        "screen": {},
        "replay": {},
        "label": ev.LABEL,
        "survivorship": ev.SURVIVORSHIP,
        "authority": ev.AUTHORITY,
    }
    ledger.write_bytes(ev.canonical(row))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    invoke(monkeypatch, "list", "--ledger", str(ledger), "--json")
    assert capsys.readouterr().out.encode() == ev.canonical(
        {
            "entries": [stored()],
            "trials": [
                {
                    "trial_index": 1,
                    "name": "RANGE_7d",
                    "status": "FAILED",
                    "exposure": ex.label_for(row, [stored()]),
                }
            ],
        }
    )
    invoke(monkeypatch, "list", "--ledger", str(ledger))
    output = capsys.readouterr().out
    assert "#1 known xs-range" in output
    assert "1 RANGE_7d FAILED" in output
    assert "previously exposed" in output
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_add_refuses_an_empty_list_and_writes_no_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty log would read as "no exposure" instead of "no exposure log".
    ledger, source = tmp_path / "trials.jsonl", tmp_path / "entries.json"
    source.write_text("[]")
    with pytest.raises(DataError):
        invoke(monkeypatch, "add", "--ledger", str(ledger), "--file", str(source))
    assert not ex.exposure_log_path(ledger).exists()
    assert ex.label_for(trial(), ex.read_entries(ledger))["previously_exposed"] is None


def test_empty_name_regex_is_refused(tmp_path: Path) -> None:
    ledger = tmp_path / "trials.jsonl"
    row = stored(match={"name_regex": "", "instruments": ["*"]})
    ex.exposure_log_path(ledger).write_bytes(ev.canonical(row))
    with pytest.raises(DataError):
        ex.read_entries(ledger)


def test_incomplete_last_line_fails_loud(tmp_path: Path) -> None:
    ledger = tmp_path / "trials.jsonl"
    ex.exposure_log_path(ledger).write_bytes(ev.canonical(stored())[:-5])
    with pytest.raises(DataError):
        ex.snapshot(ledger)
