"""A setup trade can be followed forward on paper: start, update, verify and stop."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli import follow_source, follow_store, follow_update
from alpha_cli.spine.errors import SpineError
from tests.fixtures.follow_setup_fixtures import (
    EVENTS,
    START,
    START_BAR,
    clock_after,
    day_of,
    make_study,
)


def _start(home: Path, trade_id: str) -> str:
    source = follow_source.setup_trade_source(home, trade_id, "")
    facts = follow_store.start_follow(home, source, card="", size_pct=10.0, clock=lambda: START)
    return str(facts["follow_id"])


def _run(home: Path, follow: str, last_bar: int) -> list[Any]:
    for i in range(START_BAR, last_bar + 1):
        follow_update.update_follow(home, follow, clock=partial(clock_after, i))
    return follow_store.entries_of(home, follow)


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    home = tmp_path_factory.mktemp("setup-follow")
    study = make_study(home)
    follow = _start(home, study["trade_id"])
    entries = _run(home, follow, 160)
    return {"home": home, "study": study, "follow": follow, "entries": entries}


def test_start_keeps_the_study_labels_and_trial_identity(world: dict[str, Any]) -> None:
    start = world["entries"][0].payload["setup"]
    trade = world["study"]["trade"]
    assert start["trade_id"] == trade["trade_id"] and start["find_id"] == trade["find_id"]
    assert start["labels"] == trade["labels"]
    assert start["exits"]["stop"] == "5 %" and start["exits"]["target"] == "10 %"
    record = follow_store.load_record(follow_store.folder_of(world["home"], world["follow"]))
    assert record.kind == "setup_trade" and record.source_id == trade["trade_id"]


def test_one_entry_per_session_and_the_chain_is_intact(world: dict[str, Any]) -> None:
    entries = world["entries"]
    assert [e.kind for e in entries] == ["start", *["bar"] * (160 - START_BAR + 1)]
    assert [e.session_date for e in entries[1:3]] == [day_of(105), day_of(106)]
    report = follow_store.journal_report(world["home"], world["follow"], now=clock_after(160))
    assert report.first_break is None and report.entries == len(entries)


def test_the_first_decisions_equal_the_studys_own_trades(world: dict[str, Any]) -> None:
    rows = pl.read_parquet(world["study"]["trade"]["folder"] + "/trades.parquet")
    wanted = rows.filter(pl.col("entry_index") > START_BAR).sort("entry_index").to_dicts()
    seen = [e.payload["setup"]["trade"] for e in world["entries"] if e.kind == "bar"]
    seen = [t for t in seen if t]
    assert len(seen) == len(wanted) == 2
    for got, study in zip(seen, wanted, strict=True):
        assert got["entry_ts"] == study["entry_ts"].isoformat()
        assert got["exit_ts"] == study["exit_ts"].isoformat()
        assert got["reason"] == study["reason"]
        assert got["entry_price"] == pytest.approx(study["entry_price"], rel=1e-9, abs=1e-12)
        assert got["exit_price"] == pytest.approx(study["exit_price"], rel=1e-9, abs=1e-12)
        assert got["net_return"] == pytest.approx(study["net_return"], rel=1e-9, abs=1e-12)
    assert [t["reason"] for t in seen] == ["target", "stop"]


def test_the_order_is_decided_at_the_close_and_filled_at_the_next_open(
    world: dict[str, Any],
) -> None:
    by_day = {e.session_date: e.payload for e in world["entries"][1:]}
    decided = by_day[day_of(EVENTS[3])]
    assert decided["decision"]["action"] == "enter" and decided["fills"] == []
    filled = by_day[day_of(EVENTS[3] + 1)]
    assert filled["fills"][0]["side"] == "buy" and filled["fills"][0]["bar_ts"].startswith(
        day_of(EVENTS[3] + 1).isoformat()
    )
    assert filled["decision"]["words"] == "holding"
    exit_day = by_day[day_of(EVENTS[3] + 2)]
    assert exit_day["fills"][0]["side"] == "sell" and exit_day["fills"][0]["reason"] == "target"
    assert exit_day["decision"]["action"] == "closed"


def test_no_decision_changes_when_later_bars_arrive(world: dict[str, Any]) -> None:
    from alpha_cli import follow_setup
    from alpha_cli._runner import load_bars

    bars, _ = load_bars("SPY", data_dir=world["home"])
    study = world["study"]["trade"]
    costs = study["costs"]["SPY"]
    spec = follow_source.frozen_setup(
        world["home"], world["study"]["trade_id"], study["spec_sha256"], "SPY"
    )[0]
    full = follow_setup.replay(bars, spec, "SPY", costs, START_BAR)
    for upto in (125, 140, 155):
        part = follow_setup.replay(bars[: upto + 1], spec, "SPY", costs, START_BAR)
        assert all(part[d] == full[d] for d in part if d in full and d < day_of(upto - 4))


def test_the_replay_check_agrees_and_a_second_update_writes_nothing(world: dict[str, Any]) -> None:
    again = follow_update.update_follow(
        world["home"], world["follow"], clock=lambda: clock_after(160)
    )
    assert again["status"] == "no-op" and again["replay"]["agrees"] is True
    assert again["replay"]["checked"] == 160 - START_BAR + 1


def test_paper_book_after_the_trade(world: dict[str, Any]) -> None:
    book = world["entries"][-1].payload["book"]
    assert book["trades_closed"] == 2 and book["units"] == 0.0
    assert book["dividends_cum"] == 0.0


def test_stop_and_the_refusals(world: dict[str, Any], tmp_path: Path) -> None:
    follow_store.stop_follow(
        world["home"], world["follow"], reason="done", clock=lambda: clock_after(161)
    )
    with pytest.raises(SpineError) as stopped:
        follow_update.update_follow(world["home"], world["follow"], clock=lambda: clock_after(162))
    assert stopped.value.payload["code"] == "FOLLOW_STOPPED"
    other = tmp_path / "short"
    other.mkdir()
    short = make_study(other, direction="short")
    with pytest.raises(SpineError) as refused:
        follow_source.setup_trade_source(other, short["trade_id"], "")
    assert refused.value.payload["code"] == "FOLLOW_SETUP_REFUSED"
    assert "long only" in str(refused.value)


def test_today_shows_a_setup_follow_with_its_exits_in_plain_words(world: dict[str, Any]) -> None:
    from alpha_cli import follow_today

    home = world["home"]
    fresh = follow_source.setup_trade_source(home, world["study"]["trade_id"], "SPY")
    facts = follow_store.start_follow(home, fresh, card="", size_pct=20.0, clock=lambda: START)
    view = follow_today.build(home, clock_after(START_BAR))
    row = next(r for r in view["rows"] if r["follow_id"] == facts["follow_id"])
    assert row["kind"] == "setup_trade" and row["name"].startswith("Synthetic spike")
    assert row["exits"] == [
        "Stop-loss: 5 %",
        "Profit target: 10 %",
        "Time limit: 3 trading days",
    ]
    assert "Exits:" in follow_today.text(view)


def test_show_takes_all_or_last_and_uses_plain_words(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from typer.testing import CliRunner

    from alpha_cli import follow_cmds

    monkeypatch.setenv("ALPHA_DATA_DIR", str(world["home"]))
    run = CliRunner()
    default = json.loads(
        run.invoke(follow_cmds.follow_app, ["show", world["follow"], "--json"]).output
    )
    assert default["shown"] == 20 and default["sessions"] == 160 - START_BAR + 1
    last = json.loads(
        run.invoke(
            follow_cmds.follow_app, ["show", world["follow"], "--last", "3", "--json"]
        ).output
    )
    assert last["shown"] == 3
    every = run.invoke(follow_cmds.follow_app, ["show", world["follow"], "--all", "--json"])
    assert json.loads(every.output)["shown"] == default["sessions"]
    text = run.invoke(follow_cmds.follow_app, ["show", world["follow"], "--all"]).output
    assert "dividends" in text and "_" not in "".join(
        line for line in text.splitlines() if line.startswith("    ")
    )
