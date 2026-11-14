"""Seeded synthetic holding-clock contracts; no market or reserved-window data."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from alpha_cli import rdagent_factor_eval as ev
from alpha_core import DataError
from tests.unit.test_rdagent_factor_eval import evaluate, fixture, trial_series


def arrays() -> tuple[np.ndarray, np.ndarray, list[date], list[date]]:
    first, last = map(date.fromisoformat, ev.EXPLORATION)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    open_days = [first + timedelta(days=i) for i in range(1095)]
    rng = np.random.default_rng(193)
    opens = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (1095, 15)), axis=0))
    signal = rng.normal(size=(len(days), 15))
    return signal, opens, days, open_days


@pytest.mark.parametrize("clock,h", [("daily", 1), ("weekly", 7), ("monthly", 28)])
def test_decision_windows_are_nonoverlapping_and_bounded(clock: str, h: int) -> None:
    signal, opens, days, open_days = arrays()
    series: dict[str, Any] = {}
    ev.screen_at_clock(signal, opens, days, "a" * 64, clock, open_days=open_days, series=series)
    chosen = series["days"]
    assert chosen[0] == date(2021, 1, 1)
    assert all((b - a).days == h for a, b in zip(chosen, chosen[1:], strict=False))
    seen: set[date] = set()
    for day, outcome in zip(chosen, series["outcome"], strict=True):
        i = (day - days[0]).days
        window = {day + timedelta(days=j) for j in range(1, h + 1)}
        assert seen.isdisjoint(window)
        seen |= window
        assert day + timedelta(days=1 + h) <= date(2023, 12, 31)
        np.testing.assert_array_equal(outcome, opens[i + 1 + h] / opens[i + 1] - 1)


@pytest.mark.parametrize("clock", ["daily", "weekly", "monthly"])
def test_locked_open_and_value_dates_refused(clock: str) -> None:
    signal, opens, days, open_days = arrays()
    with pytest.raises(DataError, match="reserved"):
        ev.screen_at_clock(
            signal,
            np.vstack([opens, opens[-1]]),
            days,
            "a" * 64,
            clock,
            open_days=[*open_days, date(2024, 1, 1)],
        )
    with pytest.raises(DataError, match="reserved"):
        ev.screen_at_clock(
            signal, opens, [*days[:-1], date(2024, 1, 1)], "a" * 64, clock, open_days=open_days
        )


def test_daily_matches_prechange_fixture(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    request, panel, values, _ = ev._inputs(run, req)
    _, _, days, open_days = arrays()
    symbols = sorted(panel["instrument"].unique().to_list())
    signal = ev.matrix(values, "factor", days, symbols)
    opens = ev.matrix(panel, "open", open_days, symbols)
    digest = request["factors"][0]["code_sha256"]
    daily = ev.screen_at_clock(signal, opens, days, digest, "daily", open_days=open_days)
    old = ev.screen(signal, opens[2 : len(days) + 2] / opens[1 : len(days) + 1] - 1, digest)
    for key in ("mean_ic", "p", "mean_ci_95", "effective_n", "z"):
        assert daily[key] == old[key]
    # Pinned numbers: produced by the pre-clock evaluator (commit 3d332156's screen and replay)
    # on this fixture and cross-checked by an independent reviewer on 2026-11-15, so they catch a
    # future drift of the daily clock away from the original judge.
    assert daily["mean_ic"] == 0.8978991596638654
    assert daily["p"] == 0.0
    assert daily["mean_ci_95"] == {
        "point": 0.8978991596638654,
        "lower": 0.8943299017621064,
        "upper": 0.9014275934351692,
        "confidence": 0.95,
    }
    metrics, returns = ev.replay(panel, signal, days, 1, clock="daily")
    previous, previous_returns = ev.replay(panel, signal, days, 1)
    assert metrics == previous
    np.testing.assert_array_equal(returns, previous_returns)
    assert metrics["net"]["annualized_return"] == 5.859214231363481
    assert metrics["gross"]["annualized_return"] == 6.732550010231889
    assert metrics["mean_turnover"] == 1.2908954804316646


@pytest.mark.parametrize("clock", ["daily", "weekly", "monthly"])
def test_noise_calibration(clock: str) -> None:
    _, opens, days, open_days = arrays()
    passes = 0
    for seed in range(200):
        signal = np.random.default_rng(seed + 1000).normal(size=(len(days), 15))
        result = ev.screen_at_clock(
            signal, opens, days, f"{seed:064x}", clock, open_days=open_days, n_resamples=20
        )
        passes += result["p"] < 0.05
    assert 0.01 <= passes / 200 <= 0.10


def test_low_sample_is_labelled_not_refused() -> None:
    signal, opens, days, open_days = arrays()
    result = ev.screen_at_clock(
        signal[:280], opens, days[:280], "a" * 64, "monthly", open_days=open_days
    )
    assert result["status"] == "OK"
    assert result["n"] == 10
    assert result["warnings"] == ["low_sample: n=10"]


def test_family_counts_factor_times_clock(tmp_path: Path) -> None:
    run = tmp_path / "run"
    result = evaluate(run, fixture(run), tmp_path / "ledger.jsonl")
    row = result["factors"][0]
    assert result["family_size"] == row["family_size"] == 3
    assert result["distinct_factors"] == row["distinct_factors"] == 1
    assert row["schema"] == "AlphaRdagentFactorTrialV3"
    assert list(row["clocks"]) == ["daily", "weekly", "monthly"]
    for key in ("p", "q", "screen", "replay"):
        assert row[key] == row["clocks"]["daily"][key]
    assert result["legacy_result"]["IC"] == row["clocks"][row["lead_clock"]]["screen"]["mean_ic"]
    assert result["disclosures"]["clocks"] == {"daily": 1, "weekly": 7, "monthly": 28}
    assert "distinct factors: 1" in result["feedback_text"]
    folder, manifest = trial_series(run)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    ev.evaluate(run, run / "request.json", run / "second.json", tmp_path / "fresh.jsonl")
    assert (run / "result.json").read_bytes() == (run / "second.json").read_bytes()
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
    assert manifest["factors"]


def synthetic_signal(run: Path, mode: str) -> Path:
    req = fixture(run)
    rng = np.random.default_rng(204)
    n, m = 1095, 15
    log_returns = rng.normal(0, 0.005, (n, m))
    signal = rng.normal(size=(n, m))
    if mode == "slow":
        # Monthly-only information: sum days 2..28, explicitly excluding next-day return.
        for d in range(0, n - 29, 28):
            signal[d] = log_returns[d + 3 : d + 30].sum(axis=0)
    else:
        # Antithetic pairs cancel at 7/28-day endpoints; information lasts one return day.
        shocks = rng.normal(0, 0.015, (n // 2, m))
        log_returns[: 2 * len(shocks) : 2] = shocks
        log_returns[1 : 2 * len(shocks) : 2] = -shocks
        signal[:-2] = log_returns[2:] + rng.normal(0, 0.004, (n - 2, m))
        # Make the pre-stated swing decision days independent of their forward outcomes.
        for d in range(0, n - 29, 7):
            signal[d] = rng.normal(size=m)
    opens = 100 * np.exp(np.cumsum(log_returns, axis=0))
    panel = pl.read_parquet(run / "panel/panel.parquet").with_columns(
        pl.Series("open", opens.ravel()),
        pl.Series("close", opens.ravel()),
        pl.Series("high", opens.ravel() * 1.01),
        pl.Series("low", opens.ravel() * 0.99),
    )
    panel.write_parquet(run / "panel/panel.parquet")
    import json

    receipt_path = run / "panel/panel-receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["panel_sha256"] = ev.sha((run / "panel/panel.parquet").read_bytes())
    receipt_path.write_text(json.dumps(receipt))
    values = pl.read_parquet(run / "factors.parquet").with_columns(
        pl.Series("factor", signal.ravel())
    )
    values.write_parquet(run / "factors.parquet")
    return req


def test_slow_signal_is_monthly_candidate_without_daily_pass(tmp_path: Path) -> None:
    run = tmp_path / "slow"
    result = evaluate(run, synthetic_signal(run, "slow"), tmp_path / "ledger.jsonl")
    row = result["factors"][0]
    assert row["clocks"]["monthly"]["q"] < 0.10
    assert row["clocks"]["monthly"]["replay"]["net"]["annualized_return"] > 0
    assert row["clocks"]["monthly"]["status"] == "PASS"
    assert row["clocks"]["daily"]["status"] == "SCREEN_FAIL"
    assert row["status"] == "CANDIDATE" and result["decision"] is True


def test_fast_only_signal_cannot_be_candidate(tmp_path: Path) -> None:
    run = tmp_path / "fast"
    result = evaluate(run, synthetic_signal(run, "fast"), tmp_path / "ledger.jsonl")
    row = result["factors"][0]
    assert row["clocks"]["daily"]["q"] < 0.10
    assert row["status"] in {"FAST_ONLY", "REPLAY_FAIL"}
    assert result["decision"] is False


@pytest.mark.parametrize("clock,h", [("weekly", 7), ("monthly", 28)])
def test_drifted_targets_have_small_residual_trades(tmp_path: Path, clock: str, h: int) -> None:
    run = tmp_path / clock
    fixture(run)
    panel = pl.read_parquet(run / "panel/panel.parquet")
    days = [date(2021, 1, 1) + timedelta(days=i) for i in range(85)]
    # Smooth, different asset growth; disjoint top thirds at each rebalance.
    prices = 100 * np.exp(np.arange(1095)[:, None] * np.linspace(0.0001, 0.0003, 15))
    panel = panel.with_columns(
        *[pl.Series(k, prices.ravel()) for k in ("open", "close", "low", "high")]
    )
    signal = np.vstack([np.roll(np.arange(15), (i // h % 3) * 5) for i in range(len(days))])
    series: dict[str, Any] = {}
    metrics, _ = ev.replay(panel, signal, days, 1, clock=clock, series=series)
    periods = series["periods"]
    between = [p.turnover for i, p in enumerate(periods[:-1]) if i % h]
    assert max(between) < 0.01
    assert all(
        p.turnover == pytest.approx(2, abs=0.01)
        for i, p in enumerate(periods[:-1])
        if i and i % h == 0
    )
    assert metrics["rebalances"] == (len(days) - 1) // h + 1
    assert metrics["turnover_per_rebalance"] == pytest.approx(
        sum(p.turnover for p in periods) / metrics["rebalances"]
    )
    assert metrics["annual_cost"] > 0


@pytest.mark.parametrize(
    "statuses,qs,expected,lead",
    [
        (["PASS", "PASS", "PASS"], [0.001, 0.03, 0.02], "CANDIDATE", "monthly"),
        (["PASS", "SCREEN_FAIL", "REPLAY_FAIL"], [0.001, 0.5, 0.03], "FAST_ONLY", "daily"),
        (["SCREEN_FAIL", "REPLAY_FAIL", "SCREEN_FAIL"], [0.5, 0.03, 0.6], "REPLAY_FAIL", "weekly"),
        (["DEGENERATE"] * 3, [1.0] * 3, "DEGENERATE", "daily"),
        (["SCREEN_FAIL", "DEGENERATE", "ERROR"], [0.5, 1.0, 1.0], "SCREEN_FAIL", "daily"),
    ],
)
def test_status_precedence_and_lead(
    statuses: list[str], qs: list[float], expected: str, lead: str
) -> None:
    from alpha_cli._rdagent_clocks import overall_status

    clocks: dict[str, dict[str, Any]] = {
        c: {"status": s, "q": q} for c, s, q in zip(ev.CLOCKS, statuses, qs, strict=True)
    }
    assert overall_status(clocks) == (expected, lead)


def test_v3_ledger_rejects_invalid_clock_trials(tmp_path: Path) -> None:
    import copy

    run, ledger = tmp_path / "run", tmp_path / "ledger.jsonl"
    row = evaluate(run, fixture(run), ledger)["factors"][0]
    for change in ("missing", "p", "q", "mirror", "lead", "distinct"):
        broken = copy.deepcopy(row)
        if change == "missing":
            del broken["clocks"]["monthly"]
        elif change in {"p", "q"}:
            broken["clocks"]["monthly"][change] = float("nan")
        elif change == "mirror":
            broken["p"] = 0.8
        elif change == "lead":
            broken["lead_clock"] = "hourly"
        else:
            del broken["distinct_factors"]
        ledger.write_bytes(ev.canonical(broken))
        with pytest.raises(DataError, match="invalid trial ledger"):
            ev._read_ledger(ledger)


def test_same_request_repeat_has_final_clock_statuses_and_no_extra_dsr_trials(
    tmp_path: Path,
) -> None:
    import json

    run = tmp_path / "run"
    req = fixture(run)
    request = json.loads(req.read_bytes())
    request["factors"].append({**request["factors"][0], "name": "repeat"})
    req.write_text(json.dumps(request))
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    first, repeat = result["factors"]
    assert repeat["status"] == "REPEAT"
    assert repeat["clocks"] == first["clocks"]
    assert repeat["lead_clock"] == first["lead_clock"]
    replayed = sum("net" in t["replay"] for t in first["clocks"].values())
    assert result["replayed_trials"] == replayed
    for trial in first["clocks"].values():
        if "net" in trial["replay"]:
            assert trial["replay"]["deflated_sharpe"]["n_trials"] == replayed
            assert trial["replay"]["deflated_sharpe_family"]["n_trials"] == 3


def test_legacy_result_includes_each_factor_clock_and_warning_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    original = ev.screen_at_clock

    def warned(
        signal: np.ndarray,
        opens: np.ndarray,
        days: list[date],
        digest: str,
        clock: str,
        *,
        open_days: list[date],
        series: dict[str, Any] | None = None,
        n_resamples: int | None = None,
    ) -> dict[str, Any]:
        stats = original(
            signal,
            opens,
            days,
            digest,
            clock,
            open_days=open_days,
            series=series,
            n_resamples=n_resamples,
        )
        stats["warnings"] = ["low_sample: n=10"]
        return stats

    monkeypatch.setattr(ev, "screen_at_clock", warned)
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    row = result["factors"][0]
    for clock, trial in row["clocks"].items():
        prefix = f"factor.{clock}."
        legacy = result["legacy_result"]
        assert legacy[prefix + "status"] == trial["status"]
        assert legacy[prefix + "mean_ic"] == trial["screen"]["mean_ic"]
        assert legacy[prefix + "q"] == trial["q"]
        assert legacy[prefix + "net_annual_excess"] == trial["replay"]["net"]["annualized_return"]
        assert legacy[prefix + "mean_turnover"] == trial["replay"]["mean_turnover"]
    assert "low_sample: n=10" in result["feedback_text"]
    assert "low_sample: n=10" in result["legacy_result"]["factor.feedback"]


@pytest.mark.parametrize("clock", ["daily", "weekly", "monthly"])
def test_a_missing_open_drops_one_name_not_the_whole_clock(clock: str) -> None:
    signal, opens, days, open_days = arrays()
    opens = opens.copy()
    opens[1:40, 3] = np.nan  # one coin has no bars at the start (listed later)
    result = ev.screen_at_clock(signal, opens, days, "a" * 64, clock, open_days=open_days)
    assert result["status"] in {"OK", "DEGENERATE"}
    assert "mean_ic" in result or result["status"] == "DEGENERATE"


def test_any_errored_replay_after_a_screen_pass_is_an_error() -> None:
    from alpha_cli._rdagent_clocks import overall_status

    clocks = {
        "daily": {"status": "SCREEN_FAIL", "q": 0.5},
        "weekly": {"status": "ERROR", "q": 0.01},
        "monthly": {"status": "REPLAY_FAIL", "q": 0.05},
    }
    assert overall_status(clocks)[0] == "ERROR"
