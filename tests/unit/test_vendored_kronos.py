# mypy: ignore-errors
# (this smoke test drives the untyped vendored Kronos code end-to-end)
"""Functional verification of the vendored Kronos code with tiny random-init weights.

Runs only where the opt-in torch stack is installed (`uv sync --group kronos`) — CI and
the default sandbox env skip it visibly. No downloads: models are constructed directly
with tiny dims, which exercises the full tokenize -> autoregress -> decode pipeline and
therefore validates the vendored transcription end-to-end.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="torch stack not installed (uv sync --group kronos)")
pd = pytest.importorskip("pandas")


def _tiny_pair():  # -> tuple[KronosTokenizer, Kronos]
    from alpha_forecast._vendor.kronos import Kronos, KronosTokenizer

    tokenizer = KronosTokenizer(
        d_in=6,
        d_model=32,
        n_heads=2,
        ff_dim=64,
        n_enc_layers=2,
        n_dec_layers=2,
        ffn_dropout_p=0.0,
        attn_dropout_p=0.0,
        resid_dropout_p=0.0,
        s1_bits=4,
        s2_bits=4,
        beta=1.0,
        gamma0=1.0,
        gamma=1.0,
        zeta=1.0,
        group_size=4,
    )
    model = Kronos(
        s1_bits=4,
        s2_bits=4,
        n_layers=2,
        d_model=32,
        n_heads=2,
        ff_dim=64,
        ffn_dropout_p=0.0,
        attn_dropout_p=0.0,
        resid_dropout_p=0.0,
        token_dropout_p=0.0,
        learn_te=False,
    )
    tokenizer.eval()
    model.eval()
    return tokenizer, model


def test_tiny_random_model_end_to_end_predict() -> None:
    from alpha_forecast._vendor.kronos import KronosPredictor

    tokenizer, model = _tiny_pair()
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=64)

    rng = np.random.default_rng(7)
    n, pred_len = 32, 4
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": rng.integers(1_000, 10_000, n).astype(float),
        }
    )
    x_ts = pd.Series(pd.date_range("2026-01-05", periods=n, freq="B"))
    y_ts = pd.Series(
        pd.date_range(x_ts.iloc[-1] + pd.Timedelta(days=1), periods=pred_len, freq="B")
    )

    torch.manual_seed(7)
    out = predictor.predict(
        df=df,
        x_timestamp=x_ts,
        y_timestamp=y_ts,
        pred_len=pred_len,
        T=1.0,
        top_k=0,
        top_p=0.9,
        sample_count=1,
        verbose=False,
    )
    assert list(out.columns) == ["open", "high", "low", "close", "volume", "amount"]
    assert len(out) == pred_len
    assert np.isfinite(out.to_numpy()).all()

    # determinism per seed on CPU
    torch.manual_seed(7)
    out2 = predictor.predict(
        df=df,
        x_timestamp=x_ts,
        y_timestamp=y_ts,
        pred_len=pred_len,
        T=1.0,
        top_k=0,
        top_p=0.9,
        sample_count=1,
        verbose=False,
    )
    assert np.array_equal(out.to_numpy(), out2.to_numpy())
