"""Every signal column of a follow has one plain label; no raw code name reaches the owner."""

from __future__ import annotations

import re
from pathlib import Path

import alpha_strategies
from alpha_cli import follow_labels, follow_show
from alpha_cli.follow_journal import Entry

STRATEGIES = Path(alpha_strategies.__file__ or "").parent
COLUMN = re.compile(r'"([a-z_]+)":\s*\(')


def _columns() -> set[str]:
    names = {"close"}  # the base snapshot of every strategy
    for name in ("ma_crossover", "breakout", "mean_reversion", "ts_momentum"):
        text = (STRATEGIES / f"{name}.py").read_text(encoding="utf-8")
        names |= set(COLUMN.findall(text))
    return names


def test_every_signal_column_of_the_strategies_has_a_plain_label() -> None:
    columns = _columns()
    assert {"fast_sma", "slow_sma", "channel_high", "zscore", "momentum_return"} <= columns
    missing = sorted(c for c in columns if c not in follow_labels.LABELS)
    assert missing == []
    assert all("_" not in label for label in follow_labels.LABELS.values())


def test_an_owner_named_label_is_shown_as_words() -> None:
    assert follow_labels.plain("my_fast_line") == "my fast line"
    assert follow_labels.plain_readings({"fast_sma": 1.0}) == {"fast average price": 1.0}


def test_an_entry_sentence_names_the_exit_in_words() -> None:
    sentence = follow_labels.entry_sentence(
        "bar",
        {
            "decision": {"words": "paper position closed: stop-loss"},
            "fills": [{"side": "sell", "units": 2.0, "price": 95.0, "reason": "stop"}],
            "dividends": [{"cash": 1.5}],
        },
    )
    assert sentence == (
        "Paper position closed: stop-loss; paper sell of 2 units at 95.00 (stop-loss); "
        "dividend of 1.50 paid."
    )
    assert follow_labels.entry_sentence("late", {}).startswith("The day's price bar")
    assert follow_show.RECENT == 20 and Entry is not None
