"""``KronosForecaster`` facade: lazy loading, fail-loud validation, pandas round-trip.

No HuggingFace downloads here — the loader is stubbed. The real-model smoke test lives in
``tests/integration/test_kronos_live.py`` behind the ``network`` marker.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from alpha_core import DataError
from alpha_forecast import Forecaster
from alpha_forecast.kronos import VENDORED_KRONOS_SHA, KronosForecaster
from tests.fixtures.forecast_fixtures import daily_bars


def _forecaster() -> KronosForecaster:
    return KronosForecaster(
        model_id="NeoQuasar/Kronos-small",
        model_revision="main",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="main",
        device="cpu",
    )


class _StubPredictor:
    """Stands in for the vendored KronosPredictor: echoes drifted copies of the last close."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def predict_batch(
        self,
        df_list: list[pd.DataFrame],
        x_timestamp_list: list[pd.Series],
        y_timestamp_list: list[pd.Series],
        pred_len: int,
        T: float,
        top_k: int,
        top_p: float,
        sample_count: int,
        verbose: bool,
    ) -> list[pd.DataFrame]:
        self.calls.append(
            {
                "n_series": len(df_list),
                "pred_len": pred_len,
                "T": T,
                "top_k": top_k,
                "top_p": top_p,
                "sample_count": sample_count,
                "verbose": verbose,
                "columns": list(df_list[0].columns),
                "n_context": len(df_list[0]),
            }
        )
        out = []
        for i, y_ts in enumerate(y_timestamp_list):
            base = float(df_list[i]["close"].iloc[-1]) * (1.0 + 0.01 * (i + 1))
            closes = [base + step for step in range(pred_len)]
            out.append(
                pd.DataFrame(
                    {
                        "open": closes,
                        "high": [c * 1.01 for c in closes],
                        "low": [c * 0.99 for c in closes],
                        "close": closes,
                        "volume": [10.0] * pred_len,
                        "amount": [0.0] * pred_len,
                    },
                    index=pd.DatetimeIndex(y_ts),
                )
            )
        return out


def test_satisfies_protocol_and_import_stays_torch_free() -> None:
    assert isinstance(_forecaster(), Forecaster)
    code = "import sys, alpha_forecast; sys.exit(1 if 'torch' in sys.modules else 0)"
    proc = subprocess.run([sys.executable, "-c", code], check=False)
    assert proc.returncode == 0, "importing alpha_forecast must not import torch"


def test_validates_before_any_model_load(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _forecaster()

    def _boom() -> Any:
        raise AssertionError("model load attempted before input validation")

    monkeypatch.setattr(f, "_load_predictor", _boom)
    bars = daily_bars(10)
    with pytest.raises(DataError, match="bars"):
        f.forecast(bars[:1], horizon=3, sample_count=2)
    with pytest.raises(DataError, match="horizon"):
        f.forecast(bars, horizon=0, sample_count=2)
    with pytest.raises(DataError, match="sample_count"):
        f.forecast(bars, horizon=3, sample_count=0)
    with pytest.raises(DataError, match="sorted"):
        f.forecast(list(reversed(bars)), horizon=3, sample_count=2)


def test_stubbed_round_trip_uses_batched_single_sample_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    f = _forecaster()
    stub = _StubPredictor()
    monkeypatch.setattr(f, "_load_predictor", lambda: stub)

    bars = daily_bars(20)
    r = f.forecast(bars, horizon=4, sample_count=3, temperature=1.2, top_p=0.85, top_k=5, seed=9)

    # one batched call: S copies of the series, sample_count=1 each (upstream averages
    # within sample_count — the batch dimension is what keeps paths distinct)
    (call,) = stub.calls
    assert call["n_series"] == 3
    assert call["sample_count"] == 1
    assert call["pred_len"] == 4
    assert call["T"] == 1.2 and call["top_p"] == 0.85 and call["top_k"] == 5
    assert call["verbose"] is False
    assert call["columns"] == ["open", "high", "low", "close", "volume"]
    assert call["n_context"] == 20

    assert r.horizon == 4 and len(r.samples) == 3
    assert r.samples[0].close != r.samples[1].close  # stub drifts per-copy -> distinct paths
    assert r.origin_ts == bars[-1].ts
    assert all(t.weekday() < 5 for t in r.step_ts)


class _RecordingLoader:
    """Stands in for a vendored class: records ``from_pretrained`` kwargs, returns itself."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def from_pretrained(self, name_or_path: str, **kwargs: Any) -> _RecordingLoader:
        self.calls.append({"name_or_path": name_or_path, **kwargs})
        return self


def test_from_pretrained_receives_cache_dir_and_local_files_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tokenizer_loader, model_loader = _RecordingLoader(), _RecordingLoader()
    monkeypatch.setattr("alpha_forecast._vendor.kronos.KronosTokenizer", tokenizer_loader)
    monkeypatch.setattr("alpha_forecast._vendor.kronos.Kronos", model_loader)
    monkeypatch.setattr(
        "alpha_forecast._vendor.kronos.KronosPredictor", lambda *a, **k: (a, k)
    )

    offline = KronosForecaster(
        model_id="NeoQuasar/Kronos-base",
        model_revision="pinned-model-rev",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="pinned-tok-rev",
        device="cpu",
        cache_dir=tmp_path,
        local_files_only=True,
    )
    offline._load_predictor()
    (tok_call,) = tokenizer_loader.calls
    (model_call,) = model_loader.calls
    assert tok_call == {
        "name_or_path": "NeoQuasar/Kronos-Tokenizer-base",
        "revision": "pinned-tok-rev",
        "cache_dir": tmp_path,
        "local_files_only": True,
    }
    assert model_call == {
        "name_or_path": "NeoQuasar/Kronos-base",
        "revision": "pinned-model-rev",
        "cache_dir": tmp_path,
        "local_files_only": True,
    }

    tokenizer_loader.calls.clear()
    model_loader.calls.clear()
    _forecaster()._load_predictor()  # defaults: hub cache untouched, network permitted
    assert tokenizer_loader.calls[0]["cache_dir"] is None
    assert tokenizer_loader.calls[0]["local_files_only"] is False
    assert model_loader.calls[0]["cache_dir"] is None
    assert model_loader.calls[0]["local_files_only"] is False


def test_missing_local_weights_fail_loud_offline(tmp_path: Path) -> None:
    f = KronosForecaster(
        model_id="NeoQuasar/Kronos-base",
        model_revision="main",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="main",
        device="cpu",
        cache_dir=tmp_path,  # empty: no weights here
        local_files_only=True,  # offline by construction — hub raises before any HTTP
    )
    with pytest.raises(DataError, match="NeoQuasar/Kronos-Tokenizer-base"):
        f._load_predictor()


def test_provenance_unchanged_by_cache_location(tmp_path: Path) -> None:
    cached = KronosForecaster(
        model_id="NeoQuasar/Kronos-small",
        model_revision="main",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="main",
        device="cpu",
        cache_dir=tmp_path,
        local_files_only=True,
    )
    p = cached.provenance()
    assert p == _forecaster().provenance()
    assert "cache_dir" not in p and "local_files_only" not in p


def test_provenance_reports_pin_and_determinism() -> None:
    p = _forecaster().provenance()
    assert p["model_id"] == "NeoQuasar/Kronos-small"
    assert p["model_revision"] == "main"
    assert p["tokenizer_id"] == "NeoQuasar/Kronos-Tokenizer-base"
    assert p["device"] == "cpu"
    assert p["vendor_sha"] == VENDORED_KRONOS_SHA == "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
    assert p["determinism"] == "exact"
    assert isinstance(p["torch_version"], str) and p["torch_version"]
    mps = KronosForecaster(
        model_id="m", model_revision="r", tokenizer_id="t", tokenizer_revision="r", device="mps"
    )
    assert mps.provenance()["determinism"] == "best-effort"
