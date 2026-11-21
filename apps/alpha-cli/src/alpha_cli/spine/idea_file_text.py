"""Plain-word text of the idea file. Short sentences, no advice, no grade."""

from __future__ import annotations

import textwrap
from typing import Any

from alpha_cli.spine import idea_card as cards

SHOWN_EACH_END = 10
CAP = 2 * SHOWN_EACH_END


def _wrap(first: str, text: str, indent: int) -> list[str]:
    """Wrap one stored sentence to a readable width; the words are not changed."""
    pad = " " * indent
    return textwrap.wrap(f"{first} {text}", 92, initial_indent=pad, subsequent_indent=pad + "  ")


def _card(card: dict[str, Any]) -> list[str]:
    lines = [f"  {label}: {card[name] or cards.NOT_STATED}" for name, label in cards.LABELS.items()]
    lines.append(f"  Source: {card['source'] or cards.NOT_STATED}")
    if card["supersedes"]:
        lines.append(f"  This card replaces card {card['supersedes']}.")
    if card["superseded_by"]:
        lines.append(f"  This card is replaced by card {card['superseded_by']}.")
    return lines


def _map(steps: list[dict[str, Any]]) -> list[str]:
    lines = ["  This is a map of what has been done. It is not a gate."]
    for s in steps:
        what = f" ({', '.join(s['evidence'])})" if s["evidence"] else ""
        note = f" - {s['note']}" if s["note"] and s["state"] != "done" else ""
        lines.append(f"  [{s['state']}] {s['step']}{what}{note}")
    return lines


def _checks(checks: list[dict[str, Any]]) -> list[str]:
    if not checks:
        return ["    Checks run on it: none recorded."]
    lines = [f"    Checks run on it: {len(checks)}."]
    for c in checks:
        lines += _wrap(f"{c['tool']} [{c['word']}]", str(c["reading"]), 6)
    return lines


def _rule(n: int, total: int, e: dict[str, Any]) -> list[str]:
    day = str(e["recorded_at"] or "date not recorded")[:10]
    t = e["tested"]
    lines = [f"  Reading {n} of {total}: rule test {e['id']}, recorded {day}"]
    if e["reading"] is None:
        return [*lines, f"    Fault: {e['problem']}. The reading is not available."]
    lines.append(f"    Tested: {t['asset']}, {t['rule']}.")
    lines.append(
        f"    Data used: {t['data_from'] or UNREC} to {t['data_to'] or UNREC}; "
        f"scored out of sample: {t['scored_from'] or UNREC} to {t['scored_to'] or UNREC}."
    )
    if t["held_back"]:
        lines.append(f"    Held back: {t['held_back']}")
    lines += _wrap("Reading:", str(e["sentence"]), 4)
    lines.append(f"    Evidence word: {e['word']}")
    aim = e["aim"]
    lines.append(
        f"    Aim: out-of-sample Sharpe {aim['observed']:.2f} against buy-and-hold "
        f"{aim['aim']:.2f}: {aim['relation']}."
        if aim
        else "    Aim: none stored for this run."
    )
    lines += _checks(e["checks"])
    if e["problem"]:
        lines.append(f"    Fault: {e['problem']}.")
    return lines


UNREC = "not recorded"


def _find(n: int, total: int, e: dict[str, Any]) -> list[str]:
    day = str(e["recorded_at"] or "date not recorded")[:10]
    lines = [f"  Reading {n} of {total}: setup find {e['id']}, recorded {day}"]
    if e["problem"]:
        return [*lines, f"    Fault: {e['problem']}."]
    t, g = e["tested"], e["totals"]
    lines.append(f"    Looked at: {t['idea']}; assets {', '.join(t['assets']) or UNREC}.")
    lines.append(
        f"    Occurrences: {g['accepted']} accepted, {g['pending']} pending, "
        f"{g['set_aside']} set aside. Labels: {', '.join(e['labels']) or 'none'}."
    )
    for s in e["studies"]:
        if s["problem"]:
            lines.append(f"    Study {s['id']}: Fault: {s['problem']}.")
        else:
            lines += _wrap(f"Study {s['id']} [{', '.join(s['labels'])}]:", str(s["reading"]), 4)
    return lines


def _readings(entries: list[dict[str, Any]]) -> list[str]:
    if not entries:
        return ["  No test is linked to this card yet."]
    total = len(entries)
    shown = list(enumerate(entries, 1))
    skipped = max(0, total - CAP)
    if skipped:
        shown = shown[:SHOWN_EACH_END] + shown[-SHOWN_EACH_END:]
    lines: list[str] = []
    for n, e in shown:
        if skipped and n == total - SHOWN_EACH_END + 1:
            lines.append(
                f"  {skipped} readings in between are counted but not printed. See --json."
            )
        lines += _rule(n, total, e) if e["kind"] == "rule test" else _find(n, total, e)
    if any(
        s["problem"] is None for e in entries if e["kind"] == "setup find" for s in e["studies"]
    ):
        lines.append("  Study outcome word not shown (old wording). The study sentence is shown.")
    return lines


def _follows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["  No paper follow names this card."]
    return [
        f"  Follow {r['follow_id']} (version {r['version']}, {r['state']}): "
        f"{', '.join(r['assets'])}; {r['sessions']} session(s) recorded. Paper only."
        for r in rows
    ]


def _counts(c: dict[str, Any]) -> list[str]:
    k = c["checks_run"]
    lines = [
        f"  Tests linked: {c['tests_linked']} ({c['rule_tests']} rule tests, "
        f"{c['setup_finds']} setup finds).",
        f"  Distinct assets: {c['distinct_assets']}.",
        f"  Checks run: {k['total']} ({k['declared']} declared, {k['exploratory']} exploratory).",
        f"  Variants of this idea (cards linked by replacement): {c['variants_of_this_idea']}.",
    ]
    for t in c["trials"]:
        lines.append(
            f"  Run {t['run']}: trial number {t['trial_n'] or UNREC}; family trials counted: "
            f"{t['family_trials'] or UNREC}; variants tried {t['variants_tried'] or UNREC}."
        )
    lines.append(f"  Ledger rows naming these runs: {c['ledger_rows_naming_these_runs']}.")
    return lines


def _open(o: dict[str, Any]) -> list[str]:
    lines = [
        "  Card fields not stated: " + ("; ".join(o["not_stated"]) or "none") + ".",
        "  Map lines not yet done: " + ("; ".join(o["map_not_yet"]) or "none") + ".",
        "  Readings that say too little to read: "
        + (", ".join(o["too_little_to_read"]) or "none")
        + ".",
    ]
    if o["next_steps"]:
        lines.append("  A next step could be:")
        lines += [f"    {s['step']}: {s['command']}" for s in o["next_steps"]]
    return lines


def render(facts: dict[str, Any]) -> str:
    card = facts["card"]
    parts = [
        (f"Idea file {card['id']}", []),
        ("1. The card", _card(card)),
        ("2. Where it is on the map", _map(facts["map"])),
        ("3. Readings so far, oldest first", _readings(facts["readings"])),
        ("4. Followed forward on paper", _follows(facts["follows"])),
        ("5. Counts", _counts(facts["counts"])),
        ("6. Open points", _open(facts["open_points"])),
    ]
    out: list[str] = []
    for title, lines in parts:
        out += [title, *lines]
    out.append("This page joins stored records. It computes nothing new. It is not advice.")
    return "\n".join(out)
