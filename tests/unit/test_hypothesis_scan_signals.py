"""Offline screening: causal windows, immutable inputs and honest attempt accounting."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from alpha_cli import _hypothesis_scan as scan
from alpha_core import DataError, UniverseMembership
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.hypothesis_scan_fixtures import frozen_equities


def request() -> dict[str, object]:
    return {
        "lane": "equity",
        "symbols": list("ABCDE"),
        "universe": None,
        "snapshot": "frozen",
        "as_of": "2020-04-09",
        "signals": ["rev_1m"],
        "horizons": [1, 5],
        "min_names": 5,
        "quantiles": 5,
        "cost_bps": 2.0,
        "category": "linear",
    }


@pytest.mark.bias_guard
def test_signal_windows_ignore_future_and_require_complete_history() -> None:
    closes = np.arange(1.0, 321.0).reshape(320, 1)
    before = scan.price_signals(closes, ["mom_12_1", "mom_6_1", "rev_1m", "vol_63", "range_52w"])
    poisoned = closes.copy()
    poisoned[290:] = 1e9
    after = scan.price_signals(poisoned, list(before))
    for name in before:
        np.testing.assert_equal(before[name][:290], after[name][:290])
    assert before["mom_12_1"][252, 0] == pytest.approx(closes[231, 0] / closes[0, 0] - 1)
    assert before["rev_1m"][21, 0] == pytest.approx(-(closes[21, 0] / closes[0, 0] - 1))
    closes[10] = np.nan
    assert np.isnan(scan.price_signals(closes, ["rev_1m"])["rev_1m"][21, 0])


def test_frozen_scan_replay_distinct_attempts_and_live_store_independence(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    first = scan.run_hypotheses(tmp_path, request())
    seed_store(tmp_path, symbol="A", n=100, drift=0.2)
    replay = scan.replay_hypotheses(tmp_path, first["scan_id"])
    assert first["result_digest"] == replay["result_digest"]
    assert first["attempt_id"] != replay["attempt_id"]
    assert first["authority"] == "none" and first["execution_authority"] is False
    assert first["trials"] == 2 and first["selection_adjustment"] == "not_performed"
    assert not (tmp_path / "runs").exists()
    specs = list((tmp_path / "scans" / "hypotheses" / "specs").glob("*.json"))
    assert len(specs) == 1
    frozen = json.loads(specs[0].read_text())
    assert len(frozen["snapshot_hash"]) == 64 and len(frozen["code_hash"]) == 64
    assert len(frozen["lock_hash"]) == 64


def test_failed_and_interrupted_attempts_are_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_equities(tmp_path)
    bad = {**request(), "snapshot": None}
    with pytest.raises(DataError, match="snapshot"):
        scan.run_hypotheses(tmp_path, bad)
    monkeypatch.setattr(
        scan, "evaluate_spec", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        scan.run_hypotheses(tmp_path, request())
    attempts = tmp_path / "scans" / "hypotheses" / "attempts"
    statuses = [json.loads(path.read_text())["status"] for path in attempts.glob("*/finished.json")]
    assert sorted(statuses) == ["failed", "interrupted"]


def test_replay_rejects_source_tampering_and_runtime_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_equities(tmp_path)
    first = scan.run_hypotheses(tmp_path, request())
    monkeypatch.setattr(
        scan, "runtime_identity", lambda: {"code_hash": "0" * 64, "lock_hash": "0" * 64}
    )
    with pytest.raises(DataError, match="code or lock"):
        scan.replay_hypotheses(tmp_path, first["scan_id"])
    monkeypatch.undo()
    path = tmp_path / "snapshots" / "frozen" / "bars" / "A.parquet"
    path.write_bytes(b"tampered")
    with pytest.raises(DataError, match="integrity"):
        scan.replay_hypotheses(tmp_path, first["scan_id"])


def test_canonical_identity_and_result_independence(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    first = scan.run_hypotheses(tmp_path, request())
    second = scan.run_hypotheses(tmp_path, {**request(), "symbols": list("EDCBA")})
    assert first["scan_id"] == second["scan_id"]
    assert scan.canonical_bytes({"a": -0.0}) == b'{"a":0.0}'


def test_symlink_storage_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "scans").symlink_to(outside, target_is_directory=True)
    with pytest.raises(DataError, match="symlink"):
        scan.run_hypotheses(tmp_path, request())
    assert not list(outside.iterdir())


@pytest.mark.bias_guard
def test_membership_mask_is_frozen_and_terminal_returns_are_composed(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    store = ParquetStore(tmp_path / "store")
    memberships = [
        UniverseMembership(symbol=symbol, effective_from=date(2020, 1, 1)) for symbol in "BCDE"
    ]
    memberships.append(
        UniverseMembership(
            symbol="A",
            effective_from=date(2020, 1, 15),
            effective_to=date(2020, 3, 1),
            delisting_return=-0.5,
        )
    )
    store.write_universe("sample", memberships)
    spec = scan.freeze_spec(tmp_path, {**request(), "symbols": [], "universe": "sample"})
    dates, closes, _ = scan.equity_panel(tmp_path, spec)
    eligible = scan.membership_prices(closes, dates, list("ABCDE"), memberships)
    signal = scan.price_signals(eligible, ["rev_1m"])["rev_1m"]
    assert np.isnan(signal[:35, 0]).all()
    assert np.isnan(eligible[60:, 0]).all()
    outcome = scan._outcomes(closes, dates, list("ABCDE"), memberships, 5)
    assert outcome[59, 0] == pytest.approx(-0.5)
    assert outcome[55, 0] == pytest.approx(closes[59, 0] / closes[55, 0] * 0.5 - 1)
    assert np.isnan(outcome[-5:]).all()
    store.write_universe("sample", [])
    _, replayed, _ = scan.equity_panel(tmp_path, spec)
    np.testing.assert_equal(closes, replayed)


@pytest.mark.bias_guard
def test_ordinary_universe_exit_does_not_erase_the_loss() -> None:
    dates = [date(2020, 1, day) for day in (1, 2, 3)]
    closes = np.array([[100.0], [50.0], [25.0]])
    memberships = [UniverseMembership(symbol="A", effective_from=dates[0], effective_to=dates[1])]
    eligible = scan.membership_prices(closes, dates, ["A"], memberships)
    assert np.isnan(eligible[1:]).all()
    outcomes = scan._outcomes(closes, dates, ["A"], memberships, 1)
    assert outcomes[0, 0] == pytest.approx(-0.5)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"lane": "unknown"}, "lane"),
        ({"as_of": "not-a-date"}, "as_of"),
        ({"symbols": [""]}, "symbols"),
        ({"symbols": []}, "exactly one"),
        ({"universe": "both"}, "exactly one"),
        ({"category": "spot"}, "category"),
        ({"signals": ["invented"]}, "signals"),
        ({"signals": ["rev_1m", "rev_1m"]}, "duplicate"),
        ({"horizons": [0]}, "horizons"),
        ({"horizons": [1, 1]}, "duplicate"),
        ({"min_names": 2}, "min_names"),
        ({"quantiles": 6}, "quantiles"),
        ({"cost_bps": -1.0}, "cost_bps"),
    ],
)
def test_screen_parameters_fail_before_evaluation(change: dict[str, object], message: str) -> None:
    with pytest.raises(DataError, match=message):
        scan._options({**request(), **change})


def test_missing_snapshot_symbols_and_absent_leavers_are_visible(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    snapshot = ParquetStore(tmp_path / "snapshots" / "frozen")
    snapshot.write_bars("F", snapshot.read_bars("A"))  # extra file has no manifest authority
    payload = scan.run_hypotheses(tmp_path, {**request(), "symbols": list("ABCDEF")})
    assert payload["missing"] == ["F"]
    signal = np.array([[0.0, 1.0, 2.0, 3.0, 4.0], [np.nan, 1.0, 2.0, 3.0, 4.0]])
    assert scan._absent_leavers(signal, minimum=5, quantiles=5) == 1


def test_spec_tampering_and_publication_conflicts_fail_closed(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    payload = scan.run_hypotheses(tmp_path, request())
    path = tmp_path / "scans" / "hypotheses" / "specs" / f"{payload['scan_id']}.json"
    scan._publish(path, json.loads(path.read_text()))
    with pytest.raises(DataError, match="conflict"):
        scan._publish(path, {"tampered": True})
    path.write_text('{"tampered":true}')
    with pytest.raises(DataError, match="integrity"):
        scan.replay_hypotheses(tmp_path, payload["scan_id"])
    with pytest.raises(DataError, match="scan_id"):
        scan.replay_hypotheses(tmp_path, "../escape")


def test_concurrent_repeats_keep_distinct_trial_attempts(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(
            executor.map(lambda _: scan.run_hypotheses(tmp_path, request()), range(2))
        )
    assert first["scan_id"] == second["scan_id"]
    assert first["attempt_id"] != second["attempt_id"]
    attempts = tmp_path / "scans" / "hypotheses" / "attempts"
    assert len(list(attempts.glob("*/trials/*-completed.json"))) == 4


def test_partial_trial_failure_retains_successful_measurements(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    with pytest.raises(DataError, match="horizon"):
        scan.run_hypotheses(tmp_path, {**request(), "horizons": [1, 500]})
    attempts = tmp_path / "scans" / "hypotheses" / "attempts"
    assert len(list(attempts.glob("*/trials/*-completed.json"))) == 1
    assert len(list(attempts.glob("*/trials/*-started.json"))) == 2
    with pytest.raises(DataError, match="cost_bps"):
        scan.run_hypotheses(tmp_path, {**request(), "cost_bps": float("nan")})
    assert len(list(attempts.glob("*/finished.json"))) == 2


def test_historical_reference_is_hash_only_and_does_not_require_current_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_equities(tmp_path)
    result = scan.run_hypotheses(tmp_path, request())
    monkeypatch.setattr(scan, "runtime_identity", lambda: (_ for _ in ()).throw(AssertionError()))
    reference = scan.verified_screening_reference(tmp_path, result["scan_id"])
    assert set(reference) == {
        "authority",
        "scan_id",
        "spec_sha256",
        "attempt_id",
        "result_sha256",
        "result_digest",
    }
    assert reference["attempt_id"] == result["attempt_id"]
    assert reference["authority"] == "none"


@pytest.mark.parametrize(
    "target", ["result.json", "finished.json", "resolved.json", "started.json"]
)
def test_historical_reference_rejects_changed_binding(tmp_path: Path, target: str) -> None:
    frozen_equities(tmp_path)
    result = scan.run_hypotheses(tmp_path, request())
    path = tmp_path / "scans" / "hypotheses" / "attempts" / result["attempt_id"] / target
    value = json.loads(path.read_text())
    value["attempt_id"] = "0" * 32
    path.write_text(json.dumps(value))
    with pytest.raises(DataError, match="binding|receipt"):
        scan.verified_screening_reference(
            tmp_path, result["scan_id"], attempt_id=result["attempt_id"]
        )


def test_multiple_attempts_require_explicit_historical_selection(tmp_path: Path) -> None:
    frozen_equities(tmp_path)
    first = scan.run_hypotheses(tmp_path, request())
    scan.replay_hypotheses(tmp_path, first["scan_id"])
    with pytest.raises(DataError, match="explicit attempt_id"):
        scan.verified_screening_reference(tmp_path, first["scan_id"])
    assert (
        scan.verified_screening_reference(
            tmp_path, first["scan_id"], attempt_id=first["attempt_id"]
        )["scan_id"]
        == first["scan_id"]
    )


@pytest.mark.parametrize("raw", [b"\xff", b'{"value":NaN}'])
def test_historical_corrupt_bytes_fail_with_typed_error(tmp_path: Path, raw: bytes) -> None:
    frozen_equities(tmp_path)
    result = scan.run_hypotheses(tmp_path, request())
    path = tmp_path / "scans" / "hypotheses" / "specs" / f"{result['scan_id']}.json"
    path.write_bytes(raw)
    with pytest.raises(DataError):
        scan.verified_screening_reference(tmp_path, result["scan_id"])
