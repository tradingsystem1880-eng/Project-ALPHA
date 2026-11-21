"""`alpha follow today` and the `alpha next` count: groups, read-only proof, stable keys."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import follow_cmds, follow_store, follow_today
from alpha_cli.follow_counts import followed_counts, followed_line
from alpha_cli.main import app
from tests.fixtures import follow_today_fixtures as fx

RUNNER = CliRunner()
D17, D18, D19 = date(2026, 11, 17), date(2026, 11, 18), date(2026, 11, 19)
TAIL = "Paper only. Forward use; not research. Not advice."


def _cli(home: Path, *args: str, command: str = "follow") -> tuple[int, str]:
    result = RUNNER.invoke(app, [command, *args], env={"ALPHA_DATA_DIR": str(home)})
    return result.exit_code, result.output


@pytest.fixture(autouse=True)
def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(follow_cmds, "CLOCK", lambda: fx.NOW)
    monkeypatch.setattr("alpha_cli.follow_counts.CLOCK", lambda: fx.NOW)


def _world(home: Path) -> dict[str, str]:
    """Five active follows, one per group, plus one stopped follow that must not show."""
    fx.seed(home)
    claim = fx.card(home, "Gaps in quiet stocks close within a week")
    ids = {
        "new": fx.start(home, "AAA", run_id="a" * 16, card=claim),
        "open": fx.start(home, "BBB", run_id="b" * 16),
        "nothing": fx.start(home, "CCC", run_id="c" * 16),
        "late": fx.start(home, "DDD", run_id="d" * 16),
        "waiting": fx.start(home, "BTC/USD", run_id="e" * 16, at=fx.NOW.replace(minute=30)),
        "stopped": fx.start(home, "AAA", run_id="f" * 16),
    }
    for key, units in (("new", 0.0), ("open", 12.5), ("nothing", 0.0)):
        for day in (D17, D18):
            fx.add(home, ids[key], day, units=units)
    fx.add(home, ids["new"], D19, action="enter", words="would buy at the next open")
    fx.add(home, ids["open"], D19, action="hold", words="holding", units=12.5, equity_pct=1.5)
    fx.add(home, ids["nothing"], D19)
    fx.add(home, ids["late"], D17)
    fx.add(home, ids["late"], D18)
    fx.add(home, ids["late"], D19, kind="late")
    follow_store.stop_follow(home, ids["stopped"], reason="test", clock=lambda: fx.NOW)
    return ids


def test_rows_are_grouped_in_order_with_readings_and_age(tmp_path: Path) -> None:
    ids = _world(tmp_path)
    code, out = _cli(tmp_path, "today", "--json")
    facts = json.loads(out)
    assert code == 0
    assert [g["key"] for g in facts["groups"]] == [
        "new_signal",
        "open_position",
        "nothing_today",
        "late_or_missed",
        "waiting",
    ]
    by = {r["follow_id"]: r for r in facts["rows"]}
    assert ids["stopped"] not in by and len(by) == 5
    assert [by[ids[k]]["group"] for k in ("new", "open", "nothing", "late", "waiting")] == [
        g["key"] for g in facts["groups"]
    ]
    assert [r["group"] for r in facts["rows"]] == [g["key"] for g in facts["groups"]]
    new = by[ids["new"]]
    assert new["name"] == "Gaps in quiet stocks close within a week"
    assert new["decision"] == "would buy at the next open" and new["asset"] == "AAA"
    assert (
        new["readings"] == {"fast average price": 101.2, "slow average price": 99.8}
        and new["session_date"] == "2026-11-19"
    )
    assert new["sessions_ago"] == 0 and new["paper"]["open"] is False
    assert by[ids["open"]]["paper"]["equity_pct"] == 1.5 and by[ids["open"]]["paper"]["open"]
    assert by[ids["late"]]["entry_kind"] == "late"
    assert by[ids["waiting"]]["session_date"] is None
    assert facts["behind"] == 0
    assert set(facts) >= {"as_of", "groups", "rows", "behind"}


def test_the_text_view_has_the_header_groups_and_the_closing_line(tmp_path: Path) -> None:
    _world(tmp_path)
    code, out = _cli(tmp_path, "today")
    print(out)
    assert code == 0 and out.rstrip().endswith(TAIL)
    assert "newest closed session" in out.lower() and "XNYS" in out and "2026-11-19" in out
    assert out.index("NEW SIGNAL") < out.index("OPEN PAPER POSITION") < out.index("NOTHING TODAY")
    assert out.index("NOTHING TODAY") < out.index("LATE OR MISSED") < out.index("WAITING")
    assert "as of the close of 2026-11-19" in out and "fast average price 101.20" in out


def test_a_follow_with_no_entry_for_the_newest_closed_session_is_behind(tmp_path: Path) -> None:
    fx.seed(tmp_path)
    old = fx.start(tmp_path, "AAA", run_id="a" * 16)
    fx.add(tmp_path, old, D17)
    fx.add(tmp_path, old, D18)
    facts = follow_today.build(tmp_path, fx.NOW)
    row = facts["rows"][0]
    assert row["group"] == "late_or_missed" and row["sessions_ago"] == 1
    assert facts["behind"] == 1 and "1 session ago" in follow_today.text(facts)
    silent = fx.start(tmp_path, "BBB", run_id="b" * 16)
    assert follow_today.build(tmp_path, fx.NOW)["behind"] == 2
    assert silent


def test_today_writes_nothing(tmp_path: Path) -> None:
    _world(tmp_path)

    def listing() -> list[tuple[str, int, int, str]]:
        return [
            (str(p.relative_to(tmp_path)), p.stat().st_size, p.stat().st_mtime_ns, _hash(p))
            for p in sorted(tmp_path.rglob("*"))
        ]

    before = listing()
    _cli(tmp_path, "today")
    _cli(tmp_path, "today", "--json")
    _cli(tmp_path, "", command="next")
    assert listing() == before


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def test_next_prints_one_followed_line_only_when_follows_exist(tmp_path: Path) -> None:
    code, out = _cli(tmp_path, command="next")
    assert code == 0 and "Followed on paper" not in out
    assert "followed" not in json.loads(_cli(tmp_path, "--json", command="next")[1])
    _world(tmp_path)
    line = followed_line(followed_counts(tmp_path) or {})
    assert line == (
        "Followed on paper: 5 (1 new signal, 1 open, 1 late or missed). See: alpha follow today. "
        "As one paper account: alpha follow book"
    )
    code, out = _cli(tmp_path, command="next")
    assert out.count("Followed on paper") == 1 and line in out
    assert json.loads(_cli(tmp_path, "--json", command="next")[1])["followed"]["active"] == 5


def test_a_follow_two_sessions_behind_is_shown_behind_not_as_nothing(tmp_path: Path) -> None:
    fx.seed(tmp_path)
    old = fx.start(tmp_path, "AAA", run_id="a" * 16)
    fx.add(tmp_path, old, D17)  # the newest closed session is D19: this entry is 2 sessions old
    facts = follow_today.build(tmp_path, fx.NOW)
    row = facts["rows"][0]
    assert row["group"] == "late_or_missed" and row["sessions_ago"] == 2 and row["behind"]
    out = follow_today.text(facts)
    assert "Behind it: 1 of 1" in out and "NOTHING TODAY" not in out and "2 sessions ago" in out


def test_without_an_idea_card_the_row_shows_the_rule_in_words_and_keeps_the_id(
    tmp_path: Path,
) -> None:
    from alpha_cli.follow_source import rule_words

    assert rule_words({"kind": "ma_cross", "fast": 50, "slow": 200}) == "50/200-day average cross"
    assert rule_words({"kind": "breakout", "window": 20}) == "breakout rule (window 20)"
    assert rule_words(None) == ""


def test_the_count_facade_passes_counts_only(tmp_path: Path) -> None:
    _world(tmp_path)
    counts = followed_counts(tmp_path)
    assert counts is not None
    assert set(counts) == {"active", "new_signal", "open_position", "late_or_missed"}
    assert all(isinstance(v, int) for v in counts.values())
