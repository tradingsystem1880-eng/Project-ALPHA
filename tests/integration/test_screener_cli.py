"""``alpha screener`` — fails loud without a finnhub key (the offline-verifiable path)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app

runner = CliRunner()


def test_quote_fails_loud_without_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ALPHA_FINNHUB_API_KEY", raising=False)
    result = runner.invoke(app, ["screener", "quote", "AAPL", "--json"])
    assert result.exit_code != 0  # opt-in provider: no key → loud failure, not silent degradation


def test_news_fails_loud_without_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ALPHA_FINNHUB_API_KEY", raising=False)
    result = runner.invoke(app, ["screener", "news", "AAPL", "--json"])
    assert result.exit_code != 0
