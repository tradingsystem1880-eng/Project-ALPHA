"""`alpha next`: a read-only answer to "where am I, and what can I do now?"."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from alpha_cli._cli_json import emit
from alpha_cli.follow_counts import followed_counts, followed_line
from alpha_cli.nightly_status import last_night_line
from alpha_cli.spine import idea_card
from alpha_cli.spine.reading_read import owner_word, run_reading
from alpha_cli.spine.stores import _stores
from alpha_core.config import AlphaSettings
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, store_dir

JSON = Annotated[bool, typer.Option("--json", help="Print the same facts as one JSON object.")]
RECENT = 5
KIND_WORDS = {
    "rule_test": "rule test",
    "setup_find": "setup find",
    "setup_study": "setup study",
    "setup_trade": "setup trade",
    "tool": "tool check",
    "factor": "RD-Agent idea",
    "rule_family": "RD-Agent rule idea",
    "other": "other test",
}
OUTCOME_WORDS = {
    "supported": "supported by the data",
    "rejected": "not supported",
    "inconclusive": "not enough to say",
    "invalid": "a check failed, so no verdict",
    "error": "the run failed",
    "recorded": "recorded only",
}
EXAMPLE_SPEC = "research/examples/setup-find.example.toml"
NOTICE = "These are research records. They are not advice and not approvals."


def _smallest_asset(store: ParquetStore) -> str | None:
    """The stored symbol with the smallest bar file; only file sizes are read."""
    sizes = {s: store._bars_path(s).stat().st_size for s in store.list_symbols()}
    return min(sizes, key=lambda s: (sizes[s], s)) if sizes else None


def _health(store: ParquetStore, symbols: list[str]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "unchecked": 0}
    for symbol in symbols:
        try:
            verdict = json.loads((store.root / "health" / f"{symbol}.json").read_bytes())["verdict"]
        except (OSError, ValueError, KeyError, TypeError):
            verdict = None
        counts[verdict if verdict in ("pass", "warn", "fail") else "unchecked"] += 1
    return counts


def _stores_facts(home: Path) -> tuple[list[dict[str, Any]], str | None]:
    facts: list[dict[str, Any]] = []
    smallest: tuple[int, str] | None = None
    for name, directory in _stores(home).items():
        store = ParquetStore(store_dir(directory, DAILY))
        symbols = store.list_symbols()
        if not symbols:
            continue
        facts.append(
            {
                "name": name,
                "path": str(directory),
                "asset_count": len(symbols),
                "health": _health(store, symbols),
            }
        )
        pick = _smallest_asset(store)
        if pick is not None:
            size = store._bars_path(pick).stat().st_size
            ref = pick if name == "home" else f"{pick}@{name}"
            smallest = min(smallest, (size, ref)) if smallest else (size, ref)
    return facts, smallest[1] if smallest else None


def _outcome_words(home: Path, record: Any) -> str:
    """Rows read as evidence words; a row with only a letter says which rules graded it.

    A rule-test row written before the ledger kept the evidence word is read from its run folder.
    """
    if record.kind == "rule_test" and record.evidence is None and record.outcome != "error":
        return owner_word(home, record.run_id, record.raw_status)
    return str(OUTCOME_WORDS.get(record.outcome, record.outcome))


def _trial_facts(home: Path) -> list[dict[str, Any]]:
    from alpha_cli.ledger_cmds import _rdagent_ledger
    from alpha_cli.spine.trial_reader import ledger_sources, read_ledgers

    sources = ledger_sources(
        home,
        _rdagent_ledger(home, None),
        rdagent_optional=not (home / "ledger/sources.toml").exists(),
    )
    records = sorted(
        read_ledgers(sources).records,
        key=lambda r: (r.created_at is not None, r.created_at or "", r.source, r.source_line),
        reverse=True,
    )
    return [
        {
            "date": (r.created_at or "not recorded")[:10],
            "kind": KIND_WORDS.get(r.kind, r.kind),
            "name": r.name or r.subkind or r.family_id,
            "outcome": _outcome_words(home, r),
            **({"reading": run_reading(home, r.run_id)} if r.kind == "rule_test" else {}),
        }
        for r in records[:RECENT]
    ]


def _waiting_facts(home: Path) -> dict[str, Any]:
    from alpha_cli.rdagent_discussion import closed, round_folders

    found: list[dict[str, Any]] = []
    for run in sorted((home / "runs/rdagent").glob("*/")):
        try:
            folders = round_folders(run)
            if not folders or closed(run, folders[0]) is not None:
                continue
            proposal = json.loads((folders[0] / "proposal.json").read_bytes())
            found.append(
                {
                    "run": run.name,
                    "round": int(folders[0].name[6:]),
                    "ideas": len(proposal["ideas"]),
                    "run_dir": str(run),
                }
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return {"rdagent_proposals": found}


def _paths(smallest: str | None) -> dict[str, dict[str, str]]:
    asset = smallest or "SPY"
    return {
        "own_rule": {
            "say": "Test this rule: buy when the 20-day average crosses above the 50-day, "
            f"sell when it crosses below, on {asset}.",
            "command": "alpha test --rule ma_cross --param fast=20 --param slow=50 "
            f"--asset {asset}",
        },
        "own_chart_setup": {
            "say": "Find every time my chart setup happened. Here is how I describe it.",
            "command": "alpha setup find <spec.toml>",
            "example_spec": EXAMPLE_SPEC,
        },
        "rdagent_idea": {
            "say": "Let RD-Agent propose ideas.",
            "command": "alpha rdagent run --dry-run",
            "note": "Copy research/examples/rdagent.example.toml to rdagent.toml first.",
        },
    }


def collect(home: Path) -> dict[str, Any]:
    stores, smallest = _stores_facts(home)
    notes = [NOTICE]
    if not stores:
        notes.append(
            "No data is stored here yet. Get some with "
            "`alpha data pull SPY --start 2015-01-01 --end 2023-12-31` (needs network)."
        )
    notes.append("Decisions waiting are not shown: no local status data is read.")
    followed = followed_counts(home)
    return {
        **({"followed": followed} if followed else {}),
        "last_night": last_night_line(home),
        "stores": stores,
        "recent_trials": _trial_facts(home),
        "waiting": _waiting_facts(home),
        "ideas": idea_card.counts(home),
        "paths": _paths(smallest),
        "notes": notes,
    }


def _text(facts: dict[str, Any]) -> str:
    lines = [facts["last_night"]] if facts["last_night"] else []
    lines.append("What is here")
    if not facts["stores"]:
        lines.append("  " + facts["notes"][1])
    for s in facts["stores"]:
        h = s["health"]
        plural = "" if s["asset_count"] == 1 else "s"
        lines.append(
            f"  {s['name']}: {s['asset_count']} asset{plural}. Data health: {h['pass']} pass, "
            f"{h['warn']} warn, {h['fail']} fail, {h['unchecked']} unchecked."
        )
    lines.append("What you did recently")
    if not facts["recent_trials"]:
        lines.append("  Nothing recorded yet.")
    lines.extend(
        f"  {t['date']}  {t['kind']}  {t['name']}  ({t['outcome']})" for t in facts["recent_trials"]
    )
    if len(facts["recent_trials"]) >= 2:
        lines.append("  Do two rule tests move together? alpha results correlate <run id> <run id>")
    waiting = facts["waiting"]["rdagent_proposals"]
    if waiting:
        lines.append("Waiting for you")
        lines.extend(
            f"  RD-Agent run {w['run']} proposes {w['ideas']} idea(s) for round {w['round']}. "
            f"See them: alpha ledger proposal --run-dir {w['run_dir']}"
            for w in waiting
        )
    if facts.get("followed"):
        lines.append(followed_line(facts["followed"]))
    ideas = facts["ideas"]
    plural = "" if ideas["cards"] == 1 else "s"
    lines.append(
        f"Idea cards: {ideas['cards']} idea card{plural}, {ideas['without_test']} with no test yet."
        " Write one: alpha idea new. See one: alpha idea file <id>."
    )
    lines.append("  Link RD-Agent work: alpha idea link <id> --rdagent <run>/<idea>")
    lines.append('  Keep a note or decision: alpha idea note <id> "<text>" [--decision]')
    paths = facts["paths"]
    lines += [
        "Three ways to start",
        "  1. Test my own rule.",
        f"     Say: {paths['own_rule']['say']}",
        f"     First command: {paths['own_rule']['command']}",
        "  2. Study my own chart setup.",
        f"     Say: {paths['own_chart_setup']['say']}",
        f"     First command: {paths['own_chart_setup']['command']} (example spec: {EXAMPLE_SPEC})",
        "  3. Let RD-Agent propose ideas.",
        "     Say: Let RD-Agent propose ideas.",
        f"     First command: {paths['rdagent_idea']['command']} ({paths['rdagent_idea']['note']})",
        NOTICE,
    ]
    return "\n".join(lines)


def next_step(json_out: JSON = False) -> None:
    """Say where the project stands and what you can do now. Writes nothing."""
    facts = collect(AlphaSettings().data_dir)
    emit(facts, json_out=json_out, fallback=_text(facts))
