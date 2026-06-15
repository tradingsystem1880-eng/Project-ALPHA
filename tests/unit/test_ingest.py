from pathlib import Path

from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from alpha_data.ingest import store_fetch_result
from alpha_data.store import ParquetStore
from tests.fixtures.yf_fixtures import aapl_like


def test_store_fetch_result_writes_bars_and_actions(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = parse_yfinance_history(aapl_like(), "AAPL")
    store_fetch_result(store, result)
    assert store.read_bars("AAPL")["close"].to_list() == [500.0, 129.0, 133.0]
    assert len(store.read_actions("AAPL")) == 2  # one split + one dividend
