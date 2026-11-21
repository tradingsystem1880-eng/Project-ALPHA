"""The plain words of a follow: one label for each signal column, one sentence for each entry.

This is the ONE place a code name becomes words. A raw name such as `fast_sma` never reaches the
owner: `follow show`, `follow list`, `follow today` and the Workstation Today screen all use it.
Pure text. It reads no store and no clock. Paper only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LABELS: dict[str, str] = {
    "close": "closing price",
    "fast_sma": "fast average price",
    "slow_sma": "slow average price",
    "channel_high": "top of the recent price range",
    "channel_low": "bottom of the recent price range",
    "rolling_mean": "recent average price",
    "upper_entry_band": "upper price band",
    "lower_entry_band": "lower price band",
    "zscore": "distance from the recent average (in standard deviations)",
    "entry_z": "distance that starts a trade (in standard deviations)",
    "momentum_return": "recent price change",
    "momentum_recent": "recent price",
    "momentum_past": "earlier price",
    "rsi": "RSI (a 0 to 100 gauge of recent strength)",
    "stop": "stop price",
    "target": "target price",
}
EXIT_WORDS = {
    "stop": "stop-loss",
    "stop-gap": "stop-loss (the price opened beyond it)",
    "target": "profit target",
    "time": "time limit",
    "max-hold": "longest allowed hold",
    "opposite": "opposite signal",
    "open-at-end": "still open",
}


def plain(name: str) -> str:
    """A signal column in plain words. A name with no entry in `LABELS` (a label the owner chose
    in a rule) is shown as its own words: underscores become spaces."""
    return LABELS.get(name, name.replace("_", " ").strip())


def plain_readings(readings: Mapping[str, float]) -> dict[str, float]:
    return {plain(k): v for k, v in readings.items()}


def readings_text(readings: Mapping[str, float]) -> str:
    return ", ".join(f"{plain(k)} {v:.2f}" for k, v in readings.items())


def exit_words(reason: str) -> str:
    return EXIT_WORDS.get(reason, reason.replace("-", " "))


def exits_text(exits: Mapping[str, Any]) -> list[str]:
    """The exit rules of a setup follow, one plain line each. Missing rules are left out."""
    lines: list[str] = []
    for key, word in (("stop", "Stop-loss"), ("target", "Profit target")):
        if exits.get(key):
            lines.append(f"{word}: {exits[key]}")
    if exits.get("time_bars"):
        lines.append(f"Time limit: {exits['time_bars']} trading days")
    if exits.get("opposite"):
        lines.append("Leaves early on an opposite signal")
    return lines


def entry_sentence(kind: str, payload: Mapping[str, Any]) -> str:
    """One plain sentence for a journal entry: what happened and what the paper account did."""
    if kind == "late":
        return "The day's price bar was not stored in time, so there is no decision."
    if kind == "missed":
        said = str(payload.get("would_have") or "nothing recorded")
        return f"The day was recorded too late for a paper order. The rule would have said: {said}."
    words = str(payload.get("decision", {}).get("words") or payload.get("reason") or "no decision")
    fills = payload.get("fills", [])
    done = [
        f"paper {f['side']} of {f['units']:.4g} units at {f['price']:.2f}"
        + (f" ({exit_words(f['reason'])})" if f.get("reason") else "")
        for f in fills
    ]
    paid = [f"dividend of {d['cash']:.2f} paid" for d in payload.get("dividends", [])]
    parts = [words[:1].upper() + words[1:], *done, *paid]
    return "; ".join(parts) + "."
