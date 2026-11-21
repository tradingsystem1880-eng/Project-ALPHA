"""The idea file: one read-only page per idea that joins records that already exist."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.spine import idea_card as cards
from alpha_cli.spine.ledger import append_trial
from tests.unit.test_reading_rule import manifest

RUNNER = CliRunner()
FORBIDDEN = re.compile(r"\b(supported|rejected|pass|fail|profit|verdict)\b", re.IGNORECASE)
WEAK_RUN, FAULT_RUN = "aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"
TOOL_FILE = "diagnostics/aaaaaaaaaaaaaaaa/costs.break_even@v1-abcd1234.json"
TOOL_WORDS = "Costs would have to reach 14 basis points a side before the edge is gone."


def _run_files(home: Path, run_id: str, doc: dict[str, Any]) -> None:
    folder = home / "runs" / run_id
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(doc))
    (folder / "diagnostics.json").write_text(json.dumps({"audit": [], "variants_evaluated": 2}))


def _spine(first: str, last: str, **extra: Any) -> dict[str, Any]:
    base = manifest()["spine"]
    return {
        **base,
        "rule": {"kind": "ma_cross", "fast": 5, "slow": 20},
        "data_period": {"first_ts": first, "last_ts": last},
        "traded_period": {"first_ts": "2022-01-03T00:00:00+00:00", "last_ts": last},
        **extra,
    }


def synthetic_home(home: Path, *, with_runs: bool = True) -> str:
    identity, _ = cards.save(
        home,
        cards.IdeaCard(
            claim="Quiet weeks lead to a bigger move.",
            mechanism="Traders under-react to calm.",
            baseline="Buy and hold.",
            source="from library record quiet-weeks, published 2011",
        ),
    )
    if not with_runs:
        return identity
    weak = manifest(spine=_spine("2020-01-02T00:00:00+00:00", "2024-06-28T00:00:00+00:00"))
    weak["spine"]["periods"]["scored"]["strategy"]["trades"] = 12
    weak["spine"]["idea_card"] = identity
    broken = manifest(
        oos_metrics={"max_drawdown": -0.1, "risk_of_ruin": 0.0},
        spine=_spine("2020-01-02T00:00:00+00:00", "2024-06-28T00:00:00+00:00"),
    )
    _run_files(home, WEAK_RUN, weak)
    _run_files(home, FAULT_RUN, broken)
    for run_id in (WEAK_RUN, FAULT_RUN):
        append_trial(home, {"kind": "rule_test", "run_id": run_id, "symbol": "SPY", "labels": []})
        cards.note_link(home, identity, "rule_test", run_id)
    append_trial(
        home,
        {
            "kind": "tool:costs.break_even",
            "run_id": WEAK_RUN,
            "tool_output": TOOL_FILE,
            "outcome": "ok",
            "labels": [],
        },
    )
    out = home / TOOL_FILE
    out.parent.mkdir(parents=True)
    out.write_text(
        json.dumps(
            {
                "tool": "costs.break_even",
                "run_id": WEAK_RUN,
                "cache_key": {},
                "labels": ["exploratory"],
                "recorded_at": "2026-11-19T10:00:00+00:00",
                "reading": TOOL_WORDS,
                "facts": [],
            }
        )
    )
    return identity


def _file(home: Path, *args: str) -> tuple[int, str]:
    result = RUNNER.invoke(app, ["idea", "file", *args], env={"ALPHA_DATA_DIR": str(home)})
    return result.exit_code, result.output


def _snapshot(home: Path) -> list[tuple[str, int, int]]:
    return [
        (str(p.relative_to(home)), p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(home.rglob("*"))
    ]


def test_readings_and_the_fault_appear_in_order_and_none_is_dropped(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    code, text = _file(tmp_path, card)
    assert code == 0, text
    assert text.index(f"rule test {WEAK_RUN}") < text.index(f"rule test {FAULT_RUN}")
    assert "too little to read" in text
    assert "Fault:" in text
    assert TOOL_WORDS in " ".join(text.split()) and "[exploratory]" in text
    assert "ma_cross" in text and "SPY" in text and "2020-01-02" in text


def test_map_lines_are_true_or_false_as_the_records_say(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    facts = json.loads(_file(tmp_path, card, "--json")[1])
    steps = {row["step"]: row for row in facts["map"]}
    assert steps["card written"]["state"] == "done"
    assert steps["examples looked at"]["state"] == "not yet"
    assert steps["compared with controls"]["state"] == "done"
    assert steps["compared with a simple baseline"]["state"] == "done"
    assert steps["settings checked"]["state"] == "done"
    assert steps["costs checked"]["state"] == "done"
    assert steps["costs checked"]["evidence"] == [TOOL_FILE]
    assert steps["out-of-sample numbers recorded"]["state"] == "done"
    assert steps["held-back confirmation"]["state"] == "not built yet"
    assert steps["followed forward on paper"]["state"] == "not yet"


def test_counts_are_named_for_what_they_count(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    facts = json.loads(_file(tmp_path, card, "--json")[1])
    assert sorted(facts) == ["card", "counts", "follows", "map", "open_points", "readings"]
    counts = facts["counts"]
    assert counts["tests_linked"] == 2
    assert counts["distinct_assets"] == 1
    assert counts["checks_run"] == {"total": 1, "declared": 0, "exploratory": 1}
    assert counts["variants_of_this_idea"] == 0
    assert len(facts["readings"]) == 2
    assert facts["readings"][1]["reading"]["evidence"]["word"] is None


def test_empty_card_says_not_stated_and_lists_open_points(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path, with_runs=False)
    code, text = _file(tmp_path, card)
    assert code == 0
    assert "Who is on the other side of the trade: not stated" in text
    assert "No test is linked to this card yet." in text
    facts = json.loads(_file(tmp_path, card, "--json")[1])
    assert "who is on the other side of the trade" in facts["open_points"]["not_stated"]
    commands = [row["command"] for row in facts["open_points"]["next_steps"]]
    assert any(c.startswith("alpha tool find") for c in commands)
    assert any("alpha setup study" in c for c in commands)


def test_the_idea_file_changes_nothing(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    before = _snapshot(tmp_path)
    for args in ((card,), (card, "--json")):
        assert _file(tmp_path, *args)[0] == 0
    assert _snapshot(tmp_path) == before


def test_no_forbidden_words_in_text_or_json(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    for args in ((card,), (card, "--json")):
        output = _file(tmp_path, *args)[1]
        assert not FORBIDDEN.search(output), FORBIDDEN.search(output)


def test_show_points_to_the_idea_file_and_next_names_it(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    shown = RUNNER.invoke(app, ["idea", "show", card], env={"ALPHA_DATA_DIR": str(tmp_path)})
    assert f"alpha idea file {card}" in shown.output
    nxt = RUNNER.invoke(app, ["next"], env={"ALPHA_DATA_DIR": str(tmp_path)})
    assert "See one: alpha idea file" in nxt.output


def test_long_lists_are_capped_in_text_but_complete_in_json(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path, with_runs=False)
    for n in range(25):
        run_id = f"{n:016x}"
        _run_files(tmp_path, run_id, manifest(spine=_spine("2020-01-02", "2024-01-02")))
        append_trial(
            tmp_path, {"kind": "rule_test", "run_id": run_id, "symbol": "SPY", "labels": []}
        )
        cards.note_link(tmp_path, card, "rule_test", run_id)
    text = _file(tmp_path, card)[1]
    assert "5 readings in between" in text
    assert text.count(": rule test ") == 20
    assert len(json.loads(_file(tmp_path, card, "--json")[1])["readings"]) == 25


def _setup_find_and_study(home: Path, card: str, *, break_study: bool = False) -> None:
    import hashlib

    find = home / "setups" / "f1"
    find.mkdir(parents=True)
    manifest_doc = {
        "idea": "a synthetic reclaim",
        "recorded_at": "2026-11-18T09:00:00+00:00",
        "context_bars": 30,
        "labels": ["exploratory"],
        "assets": [{"asset": "SPY"}, {"asset": "QQQ"}],
    }
    (find / "manifest.json").write_text(json.dumps(manifest_doc))
    totals = {"accepted": 12, "pending": 1, "rejected": 3}
    (find / "summary.json").write_text(json.dumps({"totals": totals}))
    cards.note_link(home, card, "setup_find", "f1")
    study = home / "setup-studies" / "s1"
    study.mkdir(parents=True)
    files = {}
    summary = {
        "reading": "Too few occurrences (12) to judge.",
        "labels": ["exploratory"],
        "occurrences": 12,
        "facts": [],
    }
    for name, data in (
        ("outcomes.parquet", b"x"),
        ("summary.json", json.dumps(summary).encode()),
        ("event-study.png", b"y"),
    ):
        (study / name).write_bytes(data)
        files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    if break_study:
        files["outcomes.parquet"]["sha256"] = "0"
    (study / "manifest.json").write_text(
        json.dumps({"schema": "AlphaSetupStudyV1", "find_id": "f1", "files": files})
    )


def test_setup_find_and_study_are_read_and_a_broken_study_is_a_fault(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    _setup_find_and_study(tmp_path, card)
    text = _file(tmp_path, card)[1]
    assert "setup find f1" in text and "SPY, QQQ" in text
    assert "12 accepted, 1 pending, 3 set aside" in text
    assert "Too few occurrences (12) to judge." in text
    assert text.lower().count("outcome word not shown (old wording)") == 1
    steps = {r["step"]: r for r in json.loads(_file(tmp_path, card, "--json")[1])["map"]}
    assert steps["examples looked at"]["evidence"] == ["f1"]
    assert "s1" in steps["compared with controls"]["evidence"]
    (tmp_path / "setup-studies" / "s1" / "summary.json").write_text("{}")
    assert "the stored study could not be read" in _file(tmp_path, card)[1]


def test_missing_and_unreadable_runs_print_as_faults_and_map_says_not_recorded(
    tmp_path: Path,
) -> None:
    card = synthetic_home(tmp_path, with_runs=False)
    cards.note_link(tmp_path, card, "rule_test", "cccccccccccccccc")
    _run_files(tmp_path, "dddddddddddddddd", manifest())
    (tmp_path / "runs" / "dddddddddddddddd" / "diagnostics.json").write_text("[")
    cards.note_link(tmp_path, card, "rule_test", "dddddddddddddddd")
    text = _file(tmp_path, card)[1]
    assert text.count("The reading is not available.") == 2
    assert "run folder is missing" in text and "could not be read" in text
    steps = {r["step"]: r for r in json.loads(_file(tmp_path, card, "--json")[1])["map"]}
    assert steps["settings checked"]["state"] == "not recorded"


def test_replaced_cards_are_counted_as_variants_and_held_back_is_disclosed(
    tmp_path: Path,
) -> None:
    old = synthetic_home(tmp_path, with_runs=False)
    new, _ = cards.save(tmp_path, cards.IdeaCard(claim="Quiet weeks, version two.", supersedes=old))
    doc = manifest(spine=_spine("2020-01-02", "2024-01-02"))
    doc["reserve"] = {"reserved_start": "2025-01-01", "held_back_bars": 40}
    _run_files(tmp_path, WEAK_RUN, doc)
    append_trial(tmp_path, {"kind": "rule_test", "run_id": WEAK_RUN, "symbol": "SPY", "labels": []})
    cards.note_link(tmp_path, new, "rule_test", WEAK_RUN)
    facts = json.loads(_file(tmp_path, new, "--json")[1])
    assert facts["card"]["supersedes"] == old and facts["counts"]["variants_of_this_idea"] == 1
    assert "Held back 40 bars" in _file(tmp_path, new)[1]
    assert "replaced by card" in _file(tmp_path, old)[1]
    assert json.loads(_file(tmp_path, old, "--json")[1])["card"]["superseded_by"] == new


def test_unknown_card_is_a_plain_error(tmp_path: Path) -> None:
    code, output = _file(tmp_path, "0123456789ab")
    assert code != 0 and "0123456789ab" in output


def test_no_file_is_created_when_the_ledger_has_no_lock_file(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    lock = tmp_path / "ledger" / "trials.jsonl.lock"
    lock.unlink()
    before = _snapshot(tmp_path)
    assert _file(tmp_path, card)[0] == 0
    assert _file(tmp_path, card, "--json")[0] == 0
    nxt = RUNNER.invoke(app, ["next"], env={"ALPHA_DATA_DIR": str(tmp_path)})
    assert nxt.exit_code == 0, nxt.output
    assert not lock.exists()
    assert _snapshot(tmp_path) == before


def test_a_fault_counts_for_nothing_on_the_map(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path, with_runs=False)
    broken = manifest(
        oos_metrics={"max_drawdown": -0.1, "risk_of_ruin": 0.0},
        spine=_spine("2020-01-02T00:00:00+00:00", "2024-06-28T00:00:00+00:00"),
    )
    broken["nulls"] = [{"tier": "t", "percentile": 0.5, "p_value": 0.5, "passed": True}]
    _run_files(tmp_path, FAULT_RUN, broken)
    (tmp_path / "runs" / FAULT_RUN / "diagnostics.json").write_text("[")
    append_trial(
        tmp_path, {"kind": "rule_test", "run_id": FAULT_RUN, "symbol": "SPY", "labels": []}
    )
    cards.note_link(tmp_path, card, "rule_test", FAULT_RUN)
    steps = {r["step"]: r for r in json.loads(_file(tmp_path, card, "--json")[1])["map"]}
    for name in ("compared with controls", "settings checked", "costs checked"):
        assert steps[name]["state"] != "done", name
    assert "Fault:" in _file(tmp_path, card)[1]


def test_one_run_with_default_settings_is_not_yet_for_settings_checked(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path, with_runs=False)
    _run_files(tmp_path, WEAK_RUN, manifest(spine=_spine("2020-01-02", "2024-01-02")))
    (tmp_path / "runs" / WEAK_RUN / "diagnostics.json").write_text(json.dumps({"audit": []}))
    append_trial(tmp_path, {"kind": "rule_test", "run_id": WEAK_RUN, "symbol": "SPY", "labels": []})
    cards.note_link(tmp_path, card, "rule_test", WEAK_RUN)
    steps = {r["step"]: r for r in json.loads(_file(tmp_path, card, "--json")[1])["map"]}
    assert steps["settings checked"]["state"] == "not yet"


def _follow_world(home: Path, card: str) -> dict[str, str]:
    from datetime import date

    from tests.fixtures import follow_today_fixtures as fx

    fx.seed(home)
    other = fx.card(home, "A different idea about gaps")
    stopped = fx.start(home, "BBB", run_id="b" * 16, card=card)
    mine = fx.start(home, "AAA", run_id="a" * 16, card=card)
    foreign = fx.start(home, "CCC", run_id="c" * 16, card=other)
    fx.add(home, mine, date(2026, 11, 18))
    fx.add(home, mine, date(2026, 11, 19))
    return {"mine": mine, "stopped": stopped, "foreign": foreign}


def test_follows_list_only_this_cards_follows_and_the_map_step_turns_true(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    ids = _follow_world(tmp_path, card)
    facts = json.loads(_file(tmp_path, card, "--json")[1])
    rows = {row["follow_id"]: row for row in facts["follows"]}
    assert set(rows) == {ids["mine"], ids["stopped"]}
    assert rows[ids["mine"]]["state"] == "active" and rows[ids["mine"]]["sessions"] == 2
    assert rows[ids["stopped"]]["state"] == "stopped"
    assert rows[ids["stopped"]]["stop_reason"] == "replaced by version 2"
    assert rows[ids["mine"]]["assets"] == ["AAA"] and rows[ids["mine"]]["version"] == 2
    step = {r["step"]: r for r in facts["map"]}["followed forward on paper"]
    assert step["state"] == "done" and ids["mine"] in step["evidence"]
    assert "paper" in _file(tmp_path, card)[1].lower()


def test_no_follows_keeps_the_old_step_and_an_empty_list(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    facts = json.loads(_file(tmp_path, card, "--json")[1])
    assert facts["follows"] == []
    step = {r["step"]: r for r in facts["map"]}["followed forward on paper"]
    assert step["state"] == "not yet" and step["evidence"] == []


def test_each_linked_run_names_its_figures_by_id_only(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    facts = json.loads(_file(tmp_path, card, "--json")[1])
    for row in facts["readings"]:
        assert isinstance(row["figures_available"], list)
        assert all(isinstance(name, str) for name in row["figures_available"])
    assert "image" not in json.dumps(facts) and ".png" not in json.dumps(facts["readings"])
