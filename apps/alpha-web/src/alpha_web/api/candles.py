"""``/api/candles/{symbol}`` — PIT-adjusted OHLCV for the price chart."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from alpha_cli import paper_store
from alpha_web import _candles
from alpha_web.api._common import data_dir
from alpha_web.api.models import Candles

router = APIRouter(prefix="/api", tags=["candles"])


@router.get("/candles/{symbol:path}", response_model=Candles)
def candles(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    snapshot: str | None = None,
    tail: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    """Point-in-time candles for ``symbol`` (``{symbol:path}`` so ``BTC/USD`` works).

    ``tail`` trims the response to the last N bars of the window. It is a payload trim only:
    the reader still loads the whole window once and caches it on the parquet mtime, so Market
    Watch's ``tail=2`` reads are cheap after the first.
    """
    directory = data_dir()
    try:
        result = _candles.candles(
            symbol, data_dir=directory, start=start, end=end, snapshot=snapshot
        )
        bars = result.get("bars")
        rows = bars if isinstance(bars, list) else []
        if tail is not None:  # copy: the reader's cached dict must keep the full window
            rows = rows[-tail:]
            result = {**result, "bars": rows}
        bar_times = sorted(
            int(row["t"])
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("t"), (int, float))
            and not isinstance(row.get("t"), bool)
        )
        markers: list[dict[str, object]] = []
        if bar_times:
            for session in paper_store.list_sessions(directory):
                if str(session["symbol"]).upper() != symbol.strip().upper():
                    continue
                for event in paper_store.read_events(directory, str(session["session_id"])):
                    event_type = event["event_type"]
                    if event_type not in {"intent", "order", "fill", "cancel", "expired"}:
                        continue
                    recorded = datetime.fromisoformat(
                        str(event["recorded_at"]).replace("Z", "+00:00")
                    )
                    raw_ts_event = event["ts_event_ns"]
                    exact_ts = (
                        raw_ts_event // 1_000_000_000
                        if isinstance(raw_ts_event, int) and not isinstance(raw_ts_event, bool)
                        else int(recorded.timestamp())
                    )
                    bar_ts = next(
                        (
                            candidate
                            for candidate in reversed(bar_times)
                            if candidate <= exact_ts < candidate + 86_400
                        ),
                        None,
                    )
                    if bar_ts is None:
                        continue
                    payload = event["payload"]
                    if not isinstance(payload, dict):
                        continue
                    quantity = payload.get("quantity")
                    price = payload.get("price")
                    markers.append(
                        {
                            "session_id": session["session_id"],
                            "sequence": event["sequence"],
                            "t": bar_ts,
                            "exact_ts": exact_ts,
                            "event_type": event_type,
                            "execution_mode": session["execution_mode"],
                            "side": payload.get("side")
                            if isinstance(payload.get("side"), str)
                            else None,
                            "quantity": float(quantity)
                            if isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
                            else None,
                            "price": float(price)
                            if isinstance(price, (int, float)) and not isinstance(price, bool)
                            else None,
                            "intent_id": payload.get("intent_id")
                            if isinstance(payload.get("intent_id"), str)
                            else None,
                        }
                    )
        return {**result, "paper_markers": markers}
    except RuntimeError as exc:  # CLI failed (unknown symbol / empty window) — surface as 404
        raise HTTPException(status_code=404, detail=str(exc)) from exc
