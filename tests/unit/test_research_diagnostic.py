"""Weekly discovery has a fixed target, chronological labels, and explicit failure modes."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from alpha_core import Bar, DataError
from alpha_research.weekly_diagnostic import weekly_diagnostic


def sample(n: int = 900) -> tuple[list[Bar], list[date]]:
    days = [date(2019, 1, 1) + timedelta(days=i) for i in range(n * 2)]
    days = [d for d in days if d.weekday() < 5][:n]
    rng = np.random.default_rng(917)
    prices = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
    bars = [
        Bar(
            symbol="TEST",
            ts=datetime.combine(d, datetime.min.time(), UTC),
            open=float(p),
            high=float(p * 1.02),
            low=float(p * 0.98),
            close=float(p * 1.001),
            volume=100,
        )
        for d, p in zip(days, prices, strict=True)
    ]
    return bars, days + [
        days[-1] + timedelta(days=i)
        for i in range(1, 10)
        if (days[-1] + timedelta(days=i)).weekday() < 5
    ]


def test_chronological_target_and_baselines() -> None:
    bars, days = sample()
    result = weekly_diagnostic(bars, sessions=days, cost_bps_per_side=2)
    assert result["status"] == "completed_evidence"
    predictions = result["predictions"]
    assert len(predictions) > 40
    assert set(result["metrics"]) == {"validation", "test"}
    assert result["train_last_label_date"] < predictions[0]["decision_date"]
    assert set(result["metrics"]["test"]) == {"classifier", "majority", "momentum"}
    by_date = {b.ts.date().isoformat(): b for b in bars}
    for p in predictions:
        assert p["target"] == int(
            by_date[p["label_date"]].close > by_date[p["decision_date"]].close
        )
        assert p["entry_date"] > p["decision_date"]
        assert p["exit_date"] > p["label_date"]
        assert 0 <= p["probability"] <= 1
    assert result["admitted"] is False


def test_missing_session_and_short_data_fail() -> None:
    bars, days = sample()
    with pytest.raises(DataError, match="missing"):
        weekly_diagnostic(bars[:50] + bars[51:], sessions=days)
    with pytest.raises(DataError, match="100"):
        weekly_diagnostic(bars[:100], sessions=days)


@pytest.mark.bias_guard
def test_future_poison_preserves_earlier_predictions() -> None:
    bars, days = sample()
    original = weekly_diagnostic(bars, sessions=days)
    changed = [
        b
        if i < 800
        else b.model_copy(
            update={"open": b.open * 3, "high": b.high * 3, "low": b.low * 3, "close": b.close * 3}
        )
        for i, b in enumerate(bars)
    ]
    poisoned = weekly_diagnostic(changed, sessions=days)
    cutoff = bars[800].ts.date().isoformat()
    for a, b in zip(original["predictions"], poisoned["predictions"], strict=True):
        if a["exit_date"] < cutoff:
            assert a == b


def test_nonfinite_derived_return_fails_loud() -> None:
    bars, days = sample()
    baseline = weekly_diagnostic(bars, sessions=days)
    entry = baseline["predictions"][-2]["entry_date"]
    changed = [
        b
        if b.ts.date().isoformat() != entry
        else b.model_copy(update={"open": 1e-310, "low": 1e-311})
        for b in bars
    ]
    with pytest.raises(DataError, match="finite"):
        weekly_diagnostic(changed, sessions=days)


def test_cli_publishes_repeatable_evidence_and_not_launchable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from alpha_cli import _runner
    from alpha_cli import research_diagnostic_cmds as cli
    from alpha_cli.info_cmds import _launchable
    from alpha_core.config import AlphaSettings

    bars, _ = sample()
    monkeypatch.setattr(cli, "AlphaSettings", lambda: AlphaSettings(data_dir=tmp_path))
    monkeypatch.setattr(_runner, "load_bars", lambda *a, **kw: (bars, "fixture"))
    monkeypatch.setattr(_runner, "verified_snapshot_hash", lambda *a: "a" * 64)
    for _ in range(2):
        cli.weekly_classifier(
            "TEST", snapshot="fixture", as_of="2026-09-26", calendar="24/5", cost_bps_per_side=2
        )
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "completed_evidence"
    assert len(list((tmp_path / "diagnostics").glob("*/manifest.json"))) == 1
    assert not _launchable("research diagnostic weekly-classifier")
    assert _launchable("research compare")


@pytest.mark.parametrize("cost", [-1, float("inf"), float("nan")])
def test_bad_cost_rejected(cost: float) -> None:
    bars, days = sample()
    with pytest.raises(DataError, match="cost"):
        weekly_diagnostic(bars, sessions=days, cost_bps_per_side=cost)


def test_rejects_disorder_mixed_symbols_calendar_and_single_class() -> None:
    bars, days = sample()
    invalid = [
        ([], days),
        (bars, []),
        (bars, days[::-1]),
        (bars[::-1], days),
        ([*bars, bars[-1]], days),
        ([bars[0].model_copy(update={"symbol": "OTHER"}), *bars[1:]], days),
        (bars, days[:900]),
    ]
    for bs, ds in invalid:
        with pytest.raises(DataError):
            weekly_diagnostic(bs, sessions=ds)
    flat = [
        b.model_copy(update={"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0})
        for b in bars
    ]
    with pytest.raises(DataError, match="both classes"):
        weekly_diagnostic(flat, sessions=days)


def test_report_schema_and_metrics_reconcile_independent_predictions() -> None:
    bars, days = sample()
    result = weekly_diagnostic(bars, sessions=days, cost_bps_per_side=3)
    assert set(result) == {
        "version",
        "status",
        "admitted",
        "target",
        "train_last_label_date",
        "train_n",
        "feature_names",
        "coefficients",
        "train_feature_mean",
        "train_feature_scale",
        "metrics",
        "predictions",
        "cost_bps_per_side",
        "limitations",
    }
    assert result["version"] == "weekly-close-logistic-v1"
    assert result["target"] == "next calendar week final close > current week final close"
    assert result["cost_bps_per_side"] == pytest.approx(3)
    assert result["feature_names"] == [
        "return_5_sessions",
        "prior_sma20_deviation",
        "gain_fraction14",
        "normalized_macd12_26",
    ]
    assert result["train_n"] == 103  # 174 eligible rows: floor(.6 * 174), less one boundary label
    assert len(result["coefficients"]) == 5
    assert len(result["train_feature_mean"]) == len(result["train_feature_scale"]) == 4
    for partition in ("validation", "test"):
        rows = [r for r in result["predictions"] if r["partition"] == partition]
        for name, key in [
            ("classifier", "probability"),
            ("majority", "majority_probability"),
            ("momentum", "momentum_probability"),
        ]:
            ps = [r[key] for r in rows]
            targets = [r["target"] for r in rows]
            score = result["metrics"][partition][name]
            assert set(score) == {
                "n",
                "accuracy",
                "brier",
                "mean_episode_net_return",
                "long_episodes",
            }
            assert score["n"] == len(rows)
            assert score["accuracy"] == pytest.approx(
                sum(int(p >= 0.5) == y for p, y in zip(ps, targets, strict=True)) / len(rows)
            )
            assert score["brier"] == pytest.approx(
                sum((p - y) ** 2 for p, y in zip(ps, targets, strict=True)) / len(rows)
            )
            longs = [r for r, p in zip(rows, ps, strict=True) if p >= 0.5]
            assert score["long_episodes"] == len(longs)
            by_date = {b.ts.date().isoformat(): b for b in bars}
            net = sum(
                by_date[r["exit_date"]].open / by_date[r["entry_date"]].open - 1 - 0.0006
                for r in longs
            ) / len(rows)
            assert score["mean_episode_net_return"] == pytest.approx(net, abs=1e-12)


def test_scaler_overflow_does_not_publish_success() -> None:
    import warnings

    bars, days = sample()
    changed = [
        b if i != 180 else b.model_copy(update={"close": 1e200, "high": 1e200})
        for i, b in enumerate(bars)
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(DataError, match="scaler"):
            weekly_diagnostic(changed, sessions=days)


def test_zero_cost_minimum_history_and_constant_features(monkeypatch: pytest.MonkeyPatch) -> None:
    import alpha_research.weekly_diagnostic as module

    bars, days = sample(530)
    monkeypatch.setattr(module, "_features", lambda close, at: [0.0, 0.0, 0.5, 0.0])
    result = module.weekly_diagnostic(bars, sessions=days, cost_bps_per_side=0)
    assert result["train_n"] == 59
    assert result["train_feature_scale"] == pytest.approx([1, 1, 1, 1])
    for r in result["predictions"]:
        assert r["probability"] == pytest.approx(r["majority_probability"], abs=1e-7)
        assert r["momentum_probability"] == pytest.approx(0)


def test_optimizer_failure_is_not_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import alpha_research.weekly_diagnostic as module

    monkeypatch.setattr(
        module,
        "minimize",
        lambda *a, **kw: SimpleNamespace(success=False, x=np.ones(2), message="failed"),
    )
    with pytest.raises(DataError, match="^logistic fit did not converge: failed$"):
        module._fit(np.ones((3, 2)), np.array([0, 1, 1]))


def test_ties_and_unclosed_terminal_week_have_explicit_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alpha_research.weekly_diagnostic as module

    bars, days = sample(899)  # ends Friday: no next-open exit for the final weekly label
    original = module.weekly_diagnostic(bars, sessions=days)
    target = original["predictions"][-2]
    by_date = {b.ts.date().isoformat(): b for b in bars}
    tied = by_date[target["decision_date"]].close
    bars = [
        b
        if b.ts.date().isoformat() != target["label_date"]
        else b.model_copy(
            update={"close": tied, "high": max(b.high, tied), "low": min(b.low, tied)}
        )
        for b in bars
    ]
    monkeypatch.setattr(module, "_fit", lambda x, y: np.zeros(x.shape[1]))
    result = module.weekly_diagnostic(bars, sessions=days)
    row = next(r for r in result["predictions"] if r["label_date"] == target["label_date"])
    assert row["target"] == 0
    for score in result["metrics"].values():
        assert score["classifier"]["long_episodes"] == score["classifier"]["n"]
    assert result["limitations"] == [
        "Discovery only; repeated use consumes evaluation data.",
        "No statistical edge claim, dividends, borrow or portfolio simulation.",
        "Costs are assumptions; both sides charged on entry notional for each long episode.",
    ]
