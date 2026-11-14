"""Synthetic screening/replay and cross-run ledger contracts (no market data)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import polars as pl
import pytest

from alpha_cli import rdagent_factor_eval as ev
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.providers.binance import parse_binance_klines
from alpha_data.crypto.storage import Capacity, CryptoBulkStore


def fixture(run: Path, *, seed: int = 42, noise: bool = False) -> Path:
    (run / "panel").mkdir(parents=True)
    dates = pd.date_range("2021-01-01", "2023-12-31", tz="UTC")
    rng = np.random.default_rng(42)
    component = rng.normal(0, 0.018, (len(dates), 15))
    returns = component + rng.normal(0, 0.006, component.shape)
    opens = 100 * np.cumprod(1 + returns, axis=0)
    index = pd.MultiIndex.from_product(
        [dates.date, [f"C{i:02}USDT" for i in range(15)]], names=["date", "instrument"]
    )
    panel = pd.DataFrame(
        {
            "open": opens.ravel(),
            "close": opens.ravel(),
            "high": opens.ravel() * 1.01,
            "low": opens.ravel() * 0.99,
            "volume": 100.0,
            "quote_volume": 10000.0,
        },
        index=index,
    ).reset_index()
    panel.to_parquet(run / "panel/panel.parquet", index=False)
    (run / "panel/panel-receipt.json").write_text(
        json.dumps(
            {
                "panel_sha256": hashlib.sha256(
                    (run / "panel/panel.parquet").read_bytes()
                ).hexdigest(),
                "instruments": {s: {"last_day": "2023-12-31"} for s in panel.instrument.unique()},
            }
        )
    )
    signal = np.roll(component, -2, axis=0) + np.random.default_rng(seed).normal(
        0, 0.003, component.shape
    )
    if noise:
        signal = np.random.default_rng(seed).normal(size=component.shape)
    pd.DataFrame({"factor": signal.ravel()}, index=index).reset_index().to_parquet(
        run / "factors.parquet", index=False
    )
    req = run / "request.json"
    req.write_text(
        json.dumps(
            {
                "schema": "AlphaRdagentFactorRequestV1",
                "iteration": 0,
                "hypothesis_sha256": "b" * 64,
                "values_file": "factors.parquet",
                "factors": [
                    {
                        "name": "factor",
                        "code_sha256": hashlib.sha256(str(seed).encode()).hexdigest(),
                        "status": "OK",
                        "lookahead": {"status": "PASS"},
                    }
                ],
            }
        )
    )
    return req


def evaluate(run: Path, req: Path, ledger: Path) -> dict[str, Any]:
    return ev.evaluate(run, req, run / "result.json", ledger)


def test_planted_factor_is_candidate_and_deterministic(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    ledger = tmp_path / "trials.jsonl"
    result = evaluate(run, req, ledger)
    factor = result["factors"][0]
    assert factor["status"] == "CANDIDATE"
    assert factor["q"] < 0.10
    assert factor["replay"]["net"]["annualized_return"] > 0
    assert result["decision"] is True
    assert result["label"] == ev.LABEL
    assert ev.SURVIVORSHIP in result["feedback_text"]
    assert all(v is False for v in result["authority"].values())
    original = (run / "result.json").read_bytes()
    original_lines = ledger.read_bytes()
    other = tmp_path / "empty-ledger.jsonl"
    ev.evaluate(run, req, run / "second-result.json", other)
    assert (run / "second-result.json").read_bytes() == original
    assert other.read_bytes() == original_lines


@pytest.mark.parametrize("seed", [19, 81])
def test_noise_never_replayed(tmp_path: Path, seed: int) -> None:
    run = tmp_path / "run"
    req = fixture(run, seed=seed, noise=True)
    with patch.object(
        ev, "run_weight_replay", side_effect=AssertionError("screen failed but replay called")
    ):
        record = evaluate(run, req, tmp_path / "ledger.jsonl")
    assert record["decision"] is False
    assert record["factors"][0]["status"] == "SCREEN_FAIL"
    assert record["factors"][0]["q"] >= ev.Q_THRESHOLD


def test_noise_screen_is_calibrated() -> None:
    # Pure noise passes a 10% screen about 10% of the time (seed 7 of the fixture is one such
    # chance pass, q 0.01); a much higher rate would mean the inference is anti-conservative.
    first, last = (pd.Timestamp(d) for d in ev.EXPLORATION)
    shape = ((last - first).days + 1, 15)
    outcome = np.random.default_rng(42).normal(0, 0.02, shape)
    passes = 0
    for seed in range(80):
        signal = np.random.default_rng(1000 + seed).normal(size=shape)
        passes += ev.screen(signal, outcome, f"{seed:064x}")["p"] < ev.Q_THRESHOLD
    assert passes / 80 <= 0.2


def test_repeat_across_runs_and_append_only(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    ledger = tmp_path / "ledger.jsonl"
    evaluate(first, fixture(first), ledger)
    before = ledger.read_bytes()
    result = evaluate(second, fixture(second), ledger)
    assert ledger.read_bytes().startswith(before)
    assert result["family_size"] == 1
    assert result["total_trials"] == 2
    repeated = result["factors"][0]
    assert repeated["status"] == "REPEAT"
    assert repeated["first_trial"]["run_id"] == "first"
    assert not result["decision"]


def test_failures_and_degenerate_count_in_family(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    frame = pd.read_parquet(run / "factors.parquet")
    frame["factor"] = 1.0
    frame.to_parquet(run / "factors.parquet", index=False)
    value = json.loads(req.read_bytes())
    value["factors"] += [
        {"name": s, "code_sha256": h * 64, "status": s, "lookahead": {}}
        for s, h in [("FAILED", "c"), ("LOOKAHEAD", "d")]
    ]
    req.write_text(json.dumps(value))
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    assert result["family_size"] == 3
    assert [f["status"] for f in result["factors"]] == ["DEGENERATE", "FAILED", "LOOKAHEAD"]
    assert all(f["p"] == pytest.approx(1) for f in result["factors"])


@pytest.mark.parametrize("kind", ["values", "panel", "tamper", "ledger"])
def test_invalid_inputs_refused(tmp_path: Path, kind: str) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    ledger = tmp_path / "ledger.jsonl"
    if kind == "values":
        frame = pd.read_parquet(run / "factors.parquet")
        frame.loc[0, "date"] = pd.Timestamp("2024-01-01").date()
        frame.to_parquet(run / "factors.parquet", index=False)
    elif kind == "panel":
        receipt = json.loads((run / "panel/panel-receipt.json").read_bytes())
        receipt["instruments"]["C00USDT"]["last_day"] = "2024-01-01"
        (run / "panel/panel-receipt.json").write_text(json.dumps(receipt))
    elif kind == "tamper":
        with (run / "panel/panel.parquet").open("ab") as stream:
            stream.write(b"tamper")
    else:
        ledger.write_text('{"schema": "wrong"}\n')
    with pytest.raises(DataError):
        evaluate(run, req, ledger)


def test_one_failing_factor_is_recorded_as_error_and_the_rest_still_land(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    value = json.loads(req.read_bytes())
    value["factors"].append(
        {"name": "broken", "code_sha256": "e" * 64, "status": "OK", "lookahead": {}}
    )
    frame = pd.read_parquet(run / "factors.parquet")
    frame["broken"] = frame["factor"]
    frame.to_parquet(run / "factors.parquet", index=False)
    req.write_text(json.dumps(value))
    real = ev.screen

    def flaky(
        signal: np.ndarray,
        outcome: np.ndarray,
        digest: str,
        *,
        series: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if digest == "e" * 64:
            raise ZeroDivisionError("planted")
        return real(signal, outcome, digest, series=series)

    ledger = tmp_path / "ledger.jsonl"
    with patch.object(ev, "screen", flaky):
        result = evaluate(run, req, ledger)
    statuses = {f["name"]: f["status"] for f in result["factors"]}
    assert statuses == {"factor": "CANDIDATE", "broken": "ERROR"}
    assert result["family_size"] == 2
    assert len(ledger.read_bytes().splitlines()) == 2


def test_a_day_with_too_few_names_is_degenerate_not_a_crash(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    frame = pd.read_parquet(run / "factors.parquet")
    day = frame["date"] == frame["date"].iloc[15 * 400]
    frame.loc[day & ~frame["instrument"].isin(["C00USDT", "C01USDT"]), "factor"] = float("nan")
    frame.to_parquet(run / "factors.parquet", index=False)
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    factor = result["factors"][0]
    assert factor["status"] == "DEGENERATE"
    assert factor["screen"]["thin_days"] == 1


# --- freeze: real store API on synthetic provider payloads (no market data) ------------------

FREEZE_START = datetime(2023, 12, 26, tzinfo=UTC)
UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"


def _bulk_store(root: Path) -> CryptoBulkStore:
    (root / "bulk").mkdir(parents=True, exist_ok=True)
    return CryptoBulkStore(
        bulk_root=root / "bulk",
        manifest_root=root / "control" / "crypto" / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: UUID,
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )


def _publish(
    store: CryptoBulkStore,
    instrument: str,
    closes: tuple[float, ...],
    *,
    start: datetime = FREEZE_START,
    skip: int | None = None,
    fetched: datetime | None = None,
) -> None:
    day = timedelta(days=1)
    dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        instrument=instrument,
        base_asset=instrument.removesuffix("USDT"),
        quote_asset="USDT",
        frequency="1d",
        units="provider_native_ohlcv",
        timestamp_convention="interval_start_utc",
    )
    rows = [
        [
            int((start + i * day).timestamp() * 1000),
            c,
            c + 1,
            c - 1,
            c,
            100.0,
            int((start + (i + 1) * day).timestamp() * 1000) - 1,
            1000.0,
            10,
            50.0,
            500.0,
            0,
        ]
        for i, c in enumerate(closes)
        if i != skip
    ]
    ingest_provider_payload(
        store,
        dataset=dataset,
        payload=json.dumps(rows).encode(),
        request=(("symbol", instrument), ("interval", "1d"), ("startTime", str(rows[0][0]))),
        fetched_at=fetched or datetime(2026, 1, 1, tzinfo=UTC),
        provider_schema="binance-public-rest-v1",
        parser_version="binance-archive-rest-v1",
        logical_name="daily.json",
        parser=lambda raw: parse_binance_klines(raw, source="rest_json"),
        observed_column="open_time",
        key_columns=("open_time",),
    )


def _freeze(tmp_path: Path, store: CryptoBulkStore) -> dict[str, Any]:
    with patch.object(ev, "configured_crypto_bulk_store", lambda _: store):
        return ev.freeze(tmp_path / "control", tmp_path / "out")


def test_freeze_two_coins_stops_before_the_reserved_window(tmp_path: Path) -> None:
    store = _bulk_store(tmp_path)
    _publish(store, "BTCUSDT", (10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0))
    _publish(store, "ETHUSDT", (5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0))
    _publish(  # an equal recapture counts once
        store,
        "ETHUSDT",
        (5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0),
        fetched=datetime(2026, 2, 1, tzinfo=UTC),
    )
    receipt = _freeze(tmp_path, store)
    panel = pd.read_parquet(tmp_path / "out/panel.parquet")
    assert receipt["rows"] == len(panel) == 12  # 2023-12-26..31 for two coins; 2024 dropped
    assert {i["last_day"] for i in receipt["instruments"].values()} == {"2023-12-31"}
    assert len(receipt["manifests"]) == 3
    digest = hashlib.sha256((tmp_path / "out/panel.parquet").read_bytes()).hexdigest()
    assert receipt["panel_sha256"] == digest


@pytest.mark.parametrize("defect", ["gap", "overlap", "empty"])
def test_freeze_refuses_gaps_overlaps_and_nothing(tmp_path: Path, defect: str) -> None:
    store = _bulk_store(tmp_path)
    if defect == "gap":
        _publish(store, "BTCUSDT", (10.0, 11.0, 12.0, 13.0), skip=1)
    elif defect == "overlap":
        _publish(store, "BTCUSDT", (10.0, 11.0, 12.0))
        _publish(store, "BTCUSDT", (10.0, 11.5, 12.0), fetched=datetime(2026, 3, 1, tzinfo=UTC))
    with pytest.raises(DataError):
        _freeze(tmp_path, store)


def test_validate_panel_refuses_invalid_prices_and_reserved_dates() -> None:
    base = pl.DataFrame(
        {
            "date": [date(2023, 1, 1), date(2023, 1, 2)],
            "instrument": ["A", "A"],
            "open": [1.0, 1.0],
            "high": [2.0, 2.0],
            "low": [0.5, 0.5],
            "close": [1.5, 1.5],
            "volume": [1.0, 1.0],
            "quote_volume": [1.0, 1.0],
        }
    )
    assert ev.validate_panel(base).height == 2
    for column, value in (("open", -1.0), ("high", 0.6), ("volume", float("nan"))):
        with pytest.raises(DataError):
            ev.validate_panel(base.with_columns(pl.lit(value).alias(column)))
    with pytest.raises(DataError):
        ev.validate_panel(base.with_columns(pl.lit(date(2024, 1, 1)).alias("date")))
    with pytest.raises(DataError):
        ev.validate_panel(base.head(0))


def historical(tmp_path: Path, *, code: bytes = b"42") -> tuple[Path, dict[str, Any]]:
    path = tmp_path / "factor.py"
    path.write_bytes(code)
    return path, {
        "name": "historical",
        "code_path": str(path),
        "run_id": "old-run",
        "iteration": 2,
        "windows": ev.WINDOWS,
        "evaluated_by": "external judge",
        "result_summary": "The result was previously viewed",
        "source": "/old/run/result.json",
    }


def import_command(ledger: Path, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "rdagent_factor_eval",
            "import-historical",
            "--ledger",
            str(ledger),
            "--file",
            str(source),
        ],
    )
    ev.main()


def test_evaluation_exposure_and_mixed_schema_ledger(tmp_path: Path) -> None:
    from alpha_cli import rdagent_exposure as ex

    ledger = tmp_path / "trials.jsonl"
    # A legacy line remains byte-for-byte valid before newly evaluated V2 lines.
    legacy = {
        "schema": "AlphaRdagentFactorTrialV1",
        "trial_index": 1,
        "name": "legacy",
        "code_sha256": "a" * 64,
        "run_id": "old",
        "iteration": 0,
        "panel_sha256": "0" * 64,
        "windows": ev.WINDOWS,
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
    original = ev.canonical(legacy)
    ledger.write_bytes(original)
    entry = {
        "schema": "AlphaExposureEntryV1",
        "entry_index": 1,
        "family": {"id": "xs-range", "definition": "Cross-sectional differences in trading range"},
        "match": {"name_regex": "factor", "instruments": ["*"]},
        "instruments": ["BTCUSDT"],
        "window": {"start": "2024-01-01", "end": "2024-04-01"},
        "statistic_released": "Rank correlation",
        "seen_by": ["owner"],
        "seen_on": "2026-11-14",
        "source": "/old/result.json",
        "status": "known",
        "note": "",
        "label": ev.LABEL,
    }
    log_bytes = ev.canonical(entry)
    ex.exposure_log_path(ledger).write_bytes(log_bytes)
    run = tmp_path / "run"
    result = evaluate(run, fixture(run), ledger)
    row = result["factors"][0]
    assert row["schema"] == "AlphaRdagentFactorTrialV2"
    assert row["instruments"] == [f"C{i:02}USDT" for i in range(15)]
    assert row["exposure"]["previously_exposed"] is True
    assert result["inputs"]["exposure_log_sha256"] == ev.sha(log_bytes)
    assert (
        "factor: protected window 2024-01-01+ previously exposed for family xs-range (known); "
        "it cannot give fresh confirmation." in result["feedback_text"]
    )
    assert ledger.read_bytes().startswith(original)
    assert ev._read_ledger(ledger) == [legacy, row]
    for key in ("instruments", "exposure"):
        broken = dict(row)
        del broken[key]
        ledger.write_bytes(original + ev.canonical(broken))
        with pytest.raises(DataError):
            ev._read_ledger(ledger)


def test_imported_identity_is_never_re_evaluated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, source = tmp_path / "trials.jsonl", tmp_path / "import.json"
    code_path, item = historical(tmp_path)
    source.write_text(json.dumps([item]))
    import_command(ledger, source, monkeypatch)
    before = ledger.read_bytes()
    row = ev._read_ledger(ledger)[0]
    assert row["schema"] == "AlphaRdagentFactorTrialV2"
    assert row["code_sha256"] == ev.sha(code_path.read_bytes())
    assert row["status"] == "IMPORTED" and row["stage"] == "none"
    assert row["p"] == row["q"] == 1.0
    assert row["screen"] == row["replay"] == {}
    assert row["panel_sha256"] == "0" * 64
    assert row["instruments"] == list(ev.LOOP_UNIVERSE)
    assert row["imported"] == {
        k: item[k] for k in ("evaluated_by", "result_summary", "source", "code_path")
    }
    assert row["authority"] == ev.AUTHORITY
    assert row["exposure"] == {
        "previously_exposed": None,
        "worst_status": "no exposure log",
        "matches": [],
    }
    run = tmp_path / "repeat"
    req = fixture(run)
    with (
        patch.object(ev, "screen", side_effect=AssertionError("import screened")),
        patch.object(ev, "replay", side_effect=AssertionError("import replayed")),
    ):
        result = evaluate(run, req, ledger)
    assert ledger.read_bytes().startswith(before)
    assert result["inputs"]["exposure_log_sha256"] is None
    assert result["factors"][0]["status"] == "REPEAT"
    assert result["factors"][0]["first_trial"]["status"] == "IMPORTED"
    assert result["family_size"] == 1
    assert result["replayed_trials"] == 0
    assert not result["decision"]
    del row["imported"]
    ledger.write_bytes(ev.canonical(row))
    with pytest.raises(DataError):
        ev._read_ledger(ledger)


@pytest.mark.parametrize("defect", ["existing", "batch_duplicate", "missing", "invalid_metadata"])
def test_import_refuses_whole_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    ledger, source = tmp_path / "trials.jsonl", tmp_path / "import.json"
    _, item = historical(tmp_path)
    source.write_text(json.dumps([item]))
    import_command(ledger, source, monkeypatch)
    before = ledger.read_bytes()
    different = tmp_path / "different.py"
    different.write_bytes(b"different")
    new = {**item, "code_path": str(different)}
    bad = {**new}
    if defect == "existing":
        bad = item
    elif defect == "missing":
        bad["code_path"] = str(tmp_path / "missing.py")
    elif defect == "invalid_metadata":
        bad["evaluated_by"] = ""
    source.write_text(json.dumps([new, bad]))
    with pytest.raises(DataError):
        import_command(ledger, source, monkeypatch)
    assert ledger.read_bytes() == before


def test_imported_rows_count_in_bh_family(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger, source = tmp_path / "trials.jsonl", tmp_path / "import.json"
    _, item = historical(tmp_path, code=b"older code")
    other_path = tmp_path / "other.py"
    other_path.write_bytes(b"other code")
    source.write_text(json.dumps([item, {**item, "code_path": str(other_path)}]))
    import_command(ledger, source, monkeypatch)
    imported = ev._read_ledger(ledger)
    assert [r["trial_index"] for r in imported] == [1, 2]
    assert all(r["family_size"] == r["total_trials"] == 2 for r in imported)
    before = ledger.read_bytes()
    run = tmp_path / "new-run"
    req = fixture(run)
    with (
        patch.object(ev, "screen", return_value={"status": "OK", "p": 0.05, "direction": 1}),
        patch.object(ev, "replay", side_effect=AssertionError("BH should prevent replay")),
    ):
        result = evaluate(run, req, ledger)
    assert result["family_size"] == result["total_trials"] == 3
    assert result["factors"][0]["q"] == pytest.approx(0.15)
    assert result["factors"][0]["status"] == "SCREEN_FAIL"
    assert ledger.read_bytes().startswith(before)


def test_import_refuses_a_different_reserved_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The exposure label is computed from reserved_start, so it must be the ledger's own.
    _, item = historical(tmp_path)
    item["windows"] = {**ev.WINDOWS, "reserved_start": "2030-01-01"}
    source, ledger = tmp_path / "items.json", tmp_path / "trials.jsonl"
    source.write_text(json.dumps([item]))
    with pytest.raises(DataError):
        import_command(ledger, source, monkeypatch)
    assert not ledger.exists() or not ledger.read_bytes()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("range_fraction_7d", "Range fraction over 7 days"),
        ("VOL_ret_21d", "Volatility return over 21 days"),
        (
            "vwap_ic_xs_ma_sma_std_atr_pct_zscore",
            "Volume-weighted average price information coefficient cross-sectional "
            "moving average moving average standard deviation average true range percent z-score",
        ),
        ("7d_ret", "7d return"),
    ],
)
def test_plain_names(name: str, expected: str) -> None:
    assert ev.plain_name(name) == expected


def trial_series(run: Path) -> tuple[Path, dict[str, Any]]:
    folder = run / "evaluations/iter-0/series"
    return folder, json.loads((folder / "series.json").read_bytes())


def test_series_reproduce_metrics_hashes_and_are_byte_identical(tmp_path: Path) -> None:
    run = tmp_path / "run"
    result = evaluate(run, fixture(run), tmp_path / "ledger.jsonl")
    factor = result["factors"][0]
    digest = factor["code_sha256"]
    folder, manifest = trial_series(run)
    assert manifest["schema"] == "AlphaRdagentTrialSeriesV1"
    assert manifest["factors"][0]["code_sha256"] == digest
    assert {f["name"] for f in manifest["factors"][0]["files"]} == {
        f"{digest}.{kind}.parquet"
        for kind in ("screen", "buckets", "buckets_daily", "replay", "holdings")
    }
    for item in manifest["factors"][0]["files"]:
        assert ev.sha((folder / item["name"]).read_bytes()) == item["sha256"]
    expected_hash = ev.sha((folder / "series.json").read_bytes())
    assert result["inputs"]["series_sha256"] == expected_hash
    assert factor["evidence"] == {
        "series_manifest": "evaluations/iter-0/series/series.json",
        "sha256": expected_hash,
    }
    ledger_row = json.loads((tmp_path / "ledger.jsonl").read_bytes())
    assert ledger_row["evidence"] == factor["evidence"]
    assert ledger_row["plain_name"] == "Factor"
    screen = pl.read_parquet(folder / f"{digest}.screen.parquet")
    assert screen.columns == ["clock", "date", "rank_ic", "names"]
    assert screen["clock"].unique().to_list() == ["daily"]
    assert screen["names"].to_list() == [15] * screen.height
    assert screen["rank_ic"].mean() == pytest.approx(factor["screen"]["mean_ic"])
    buckets = pl.read_parquet(folder / f"{digest}.buckets.parquet")
    daily = pl.read_parquet(folder / f"{digest}.buckets_daily.parquet")
    assert buckets.columns == ["clock", "bucket", "mean_outcome", "observations"]
    assert daily.columns == ["clock", "date", "bucket", "mean_outcome"]
    assert buckets["observations"].sum() == screen.height * 15
    for row in buckets.iter_rows(named=True):
        assert daily.filter(pl.col("bucket") == row["bucket"])[
            "mean_outcome"
        ].mean() == pytest.approx(row["mean_outcome"])
    replay = pl.read_parquet(folder / f"{digest}.replay.parquet")
    assert replay.columns == [
        "clock",
        "target_ts",
        "exit_ts",
        "gross_return",
        "net_return",
        "benchmark_return",
        "excess_return",
        "turnover",
        "fees",
        "slippage_cost",
    ]
    mean_excess = replay["excess_return"].mean()
    assert isinstance(mean_excess, float)
    assert mean_excess * 365 == pytest.approx(factor["replay"]["net"]["annualized_return"])
    assert replay["turnover"].mean() == pytest.approx(factor["replay"]["mean_turnover"])
    assert replay["excess_return"].to_numpy() == pytest.approx(
        (replay["net_return"] - replay["benchmark_return"]).to_numpy()
    )
    holdings = pl.read_parquet(folder / f"{digest}.holdings.parquet")
    assert holdings.columns == ["clock", "date", "instrument", "target_weight", "score"]
    assert holdings.group_by("date").agg(pl.col("target_weight").sum())[
        "target_weight"
    ].to_numpy() == pytest.approx(np.ones(screen.height))
    panel = pl.read_parquet(run / "panel/panel.parquet")
    outcomes = (
        panel.select("date", "instrument", "open")
        .sort(["instrument", "date"])
        .with_columns(
            (
                pl.col("open").shift(-2).over("instrument")
                / pl.col("open").shift(-1).over("instrument")
                - 1
            ).alias("outcome")
        )
    )
    top = (
        holdings.filter(pl.col("target_weight") > 0)
        .join(outcomes, on=["date", "instrument"])
        .group_by("date")
        .agg(pl.col("outcome").mean())
        .sort("date")
    )
    assert top["outcome"].to_numpy() == pytest.approx(
        daily.filter(pl.col("bucket") == 3)["mean_outcome"].to_numpy()
    )
    fresh = tmp_path / "fresh" / "run"
    evaluate(fresh, fixture(fresh), tmp_path / "fresh-ledger.jsonl")
    other_folder, _ = trial_series(fresh)
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == {
        p.name: p.read_bytes() for p in other_folder.iterdir()
    }


def test_series_failure_changes_no_metrics_or_decisions(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    good = evaluate(run, req, tmp_path / "good.jsonl")
    with patch.object(ev, "_write_series", side_effect=OSError("evidence disk unavailable")):
        failed = ev.evaluate(run, req, run / "other.json", tmp_path / "failed.jsonl")
    assert "evidence disk unavailable" in failed["series_note"]
    good["inputs"].pop("series_sha256")
    for row in good["factors"]:
        row.pop("evidence", None)
    failed.pop("series_note")
    assert ev.canonical(good) == ev.canonical(failed)


def test_degenerate_and_unscreened_factors_have_no_series(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    frame = pl.read_parquet(run / "factors.parquet").with_columns(pl.lit(1.0).alias("factor"))
    frame.write_parquet(run / "factors.parquet")
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    folder, manifest = trial_series(run)
    assert manifest["factors"] == []
    assert [p.name for p in folder.iterdir()] == ["series.json"]
    assert "evidence" not in result["factors"][0]


def test_same_request_repeat_has_no_evidence(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    request = json.loads(req.read_bytes())
    request["factors"].append({**request["factors"][0], "name": "repeat"})
    req.write_text(json.dumps(request))
    record = evaluate(run, req, tmp_path / "ledger.jsonl")
    assert record["factors"][1]["status"] == "REPEAT"
    assert "evidence" not in record["factors"][1]
    _, manifest = trial_series(run)
    assert len(manifest["factors"]) == 1


def test_screen_error_retains_computed_daily_ic_only(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    with patch.object(ev, "block_bootstrap_ci", side_effect=DataError("inference failed")):
        record = evaluate(run, req, tmp_path / "ledger.jsonl")
    factor = record["factors"][0]
    assert factor["status"] == "ERROR"
    folder, manifest = trial_series(run)
    files = manifest["factors"][0]["files"]
    assert [f["name"] for f in files] == [f"{factor['code_sha256']}.screen.parquet"]
    assert pl.read_parquet(folder / files[0]["name"])["rank_ic"].null_count() == 0


def test_partial_series_write_failure_is_not_a_scoring_failure(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    original = ev._series_file

    def fail_buckets(path: Path, payload: bytes) -> None:
        if path.name.endswith(".buckets.parquet"):
            raise OSError("bucket write failed")
        original(path, payload)

    with patch.object(ev, "_series_file", fail_buckets):
        record = evaluate(run, req, tmp_path / "ledger.jsonl")
    factor = record["factors"][0]
    assert factor["status"] == "CANDIDATE" and record["decision"] is True
    assert "bucket write failed" in factor["series_note"]
    folder, manifest = trial_series(run)
    assert [f["name"] for f in manifest["factors"][0]["files"]] == [
        f"{factor['code_sha256']}.screen.parquet"
    ]
    assert len(list(folder.iterdir())) == 2


@pytest.mark.parametrize("direction", [1, -1])
def test_bucket_three_matches_replay_ties_and_direction(tmp_path: Path, direction: int) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    request, panel, values, _ = ev._inputs(run, req)
    days = [date(2021, 1, 1) + timedelta(days=n) for n in range(4)]
    symbols = sorted(panel["instrument"].unique().to_list())
    signal = np.zeros((len(days), len(symbols)))
    signal[:, :7] = 1
    data: dict[str, Any] = {}
    ev.replay(panel, signal, days, direction, series=data)
    outcomes = ev.matrix(panel, "open", [days[0] + timedelta(days=n) for n in range(6)], symbols)
    outcomes = outcomes[2:] / outcomes[1:-1] - 1
    buckets, daily = ev._bucket_frames(signal, outcomes, days, symbols, direction)
    assert buckets["observations"].sum() == len(days) * len(symbols)
    selected = [
        t.symbol for t in data["targets"] if t.origin_ts.date() == days[0] and t.target_weight > 0
    ]
    assert selected == symbols[:5] if direction == 1 else selected == symbols[7:12]
    for i, day in enumerate(days):
        weights = np.array([t.target_weight for t in data["targets"] if t.origin_ts.date() == day])
        assert daily.filter((pl.col("date") == day) & (pl.col("bucket") == 3))["mean_outcome"][
            0
        ] == pytest.approx(float(weights @ outcomes[i]))


def test_bucket_table_keeps_empty_days_and_null_means() -> None:
    days = [date(2021, 1, 1), date(2021, 1, 2)]
    scores = np.tile(np.arange(6), (2, 1)).astype(float)
    outcomes = np.ones((2, 6))
    outcomes[1] = np.nan
    summary, daily = ev._bucket_frames(scores, outcomes, days, list("ABCDEF"), 1)
    assert daily.height == 6
    assert daily.filter(pl.col("date") == days[1])["mean_outcome"].to_list() == [None] * 3
    assert summary["observations"].to_list() == [2, 2, 2]
