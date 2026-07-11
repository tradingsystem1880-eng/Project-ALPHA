"""Live Kronos: real weight download (HF) + real inference. Network + torch stack required.

Run on a machine with network access after ``uv sync --group kronos``:

    uv run pytest tests/integration/test_kronos_live.py -m network -q

Uses Kronos-mini (smallest open checkpoint) so the download and CPU inference stay cheap.
Also captures rough wall-times to feed the cost table in the design doc.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.network

torch = pytest.importorskip("torch", reason="torch stack not installed (uv sync --group kronos)")

from alpha_forecast import KronosForecaster, pull_model  # noqa: E402
from tests.fixtures.forecast_fixtures import daily_bars  # noqa: E402


@pytest.fixture(scope="module")
def weights_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("kronos-weights")
    t0 = time.monotonic()
    paths = pull_model("mini", target)
    print(f"\npull mini: {time.monotonic() - t0:.1f}s -> {list(paths)}")
    return target


def test_pull_then_real_inference_mini(weights_dir: Path) -> None:
    f = KronosForecaster(
        model_name="mini", weights_dir=weights_dir, cache_dir=None, seed=7, device="cpu"
    )
    bars = daily_bars(n=64)
    t0 = time.monotonic()
    out = f.forecast(bars, 4)
    print(f"mini forecast (ctx 64, h 4, cpu): {time.monotonic() - t0:.1f}s")
    assert len(out) == 4
    assert all(b.close > 0 and b.low <= b.close <= b.high for b in out)


def test_real_inference_is_deterministic_per_seed(weights_dir: Path) -> None:
    def run() -> list[float]:
        f = KronosForecaster(
            model_name="mini", weights_dir=weights_dir, cache_dir=None, seed=7, device="cpu"
        )
        return [b.close for b in f.forecast(daily_bars(n=64), 4)]

    assert run() == run()


def test_band_from_multiple_samples(weights_dir: Path) -> None:
    f = KronosForecaster(
        model_name="mini",
        weights_dir=weights_dir,
        cache_dir=None,
        seed=7,
        sample_count=3,
        device="cpu",
    )
    result = f.forecast_full(daily_bars(n=64), 4)
    assert result.close_p10 is not None and result.close_p90 is not None
    assert all(lo <= hi for lo, hi in zip(result.close_p10, result.close_p90, strict=True))
