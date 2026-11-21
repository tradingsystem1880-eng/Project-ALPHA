"""The idea file: one page of facts per idea, joined from records that already exist.

Read-only. It computes no statistic. Every reading is the one the existing reading code stores or
derives; the map is a list of facts about what has been done, never a gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_cli.follow_counts import follows_of_card
from alpha_cli.run_store import find_run_dir, read_manifest
from alpha_cli.spine import idea_card as cards
from alpha_cli.spine import reserve
from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.facts import read_json, read_study, tool_outputs
from alpha_cli.spine.idea_map import DONE, build_map, next_steps
from alpha_cli.spine.ledger import read_trials_readonly
from alpha_cli.spine.reading import reading_word, stored_reading
from alpha_cli.toolbox import declarations
from alpha_core import DataError

UNKNOWN = "not recorded"
_READ_ERRORS = (ValueError, OSError, DataError, KeyError)


def _chain(home: Path, identity: str) -> tuple[list[str], list[str]]:
    """Cards this one replaced (nearest first) and the cards that replace it (nearest first)."""
    older: list[str] = []
    node = cards.load(home, identity).supersedes
    while node and node not in older:
        older.append(node)
        try:
            node = cards.load(home, node).supersedes
        except SpineError:
            break
    newer: list[str] = []
    following = cards.successors(home)
    node = following.get(identity, "")
    while node and node not in newer:
        newer.append(node)
        node = following.get(node, "")
    return older, newer


def _rule_text(spine: dict[str, Any]) -> str:
    rule = spine.get("rule") or {}
    extras = ", ".join(f"{k}={v}" for k, v in rule.items() if k != "kind" and v is not None)
    kind = rule.get("kind") or "rule not recorded"
    return f"{kind} ({extras})" if extras else str(kind)


def _checks(home: Path, run_id: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        stored = tool_outputs(home, run_id)
    except _READ_ERRORS as exc:
        return [], f"the stored check results could not be read: {exc}"
    return [
        {
            "tool": item["tool"],
            "word": declarations.word_of(item["labels"] or []),
            "reading": item["reading"],
            "recorded_at": item["recorded_at"],
            "file": item["file"],
            "labels": item["labels"] or [],
        }
        for item in stored
    ], None


def _figure_ids(rdir: Path, manifest: dict[str, Any]) -> list[str]:
    """The ids of the figures that can be drawn for the run. Ids only; nothing is rendered."""
    from alpha_cli.figures import available_figures

    try:
        return [f.definition.figure_id for f in available_figures(rdir, manifest) if f.available]
    except _READ_ERRORS:
        return []


def _rule_entry(home: Path, run_id: str, ledger: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": "rule test",
        "id": run_id,
        "recorded_at": ledger.get("recorded_at"),
        "tested": {"asset": ledger.get("symbol") or UNKNOWN},
        "reading": None,
        "figures_available": [],
        "word": None,
        "sentence": None,
        "aim": None,
        "checks": [],
        "problem": None,
        "_manifest": {},
    }
    rdir = find_run_dir(home, run_id)
    if rdir is None:
        entry["problem"] = "the run folder is missing or has no manifest"
        return entry
    try:
        manifest = read_manifest(rdir)
        reading = stored_reading(manifest, read_json(rdir / "diagnostics.json"))
    except _READ_ERRORS as exc:
        entry["problem"] = f"the stored run could not be read: {exc}"
        return entry
    entry["figures_available"] = _figure_ids(rdir, manifest)
    spine = manifest.get("spine") or {}
    data, traded = spine.get("data_period") or {}, spine.get("traded_period") or {}
    block = manifest.get("reserve") or spine.get("reserve")
    labels = reserve.read_labels(manifest)
    held = (
        reserve.describe(block)
        if block
        else "This test saw the reserved period."
        if reserve.SEEN in labels
        else None
    )
    rows = (reading.get("aim") or {}).get("rows") or []
    entry["tested"] |= {
        "rule": _rule_text(spine),
        "data_from": str(data.get("first_ts") or "")[:10] or None,
        "data_to": str(data.get("last_ts") or "")[:10] or None,
        "scored_from": str(traded.get("first_ts") or "")[:10] or None,
        "scored_to": str(traded.get("last_ts") or "")[:10] or None,
        "held_back": held,
    }
    entry |= {
        "reading": reading,
        "word": reading_word(reading),
        "sentence": reading.get("sentence"),
        "aim": rows[0] if rows else None,
        "_manifest": manifest,
    }
    entry["checks"], entry["problem"] = _checks(home, run_id)
    return entry


def _study_entries(home: Path, find_id: str) -> list[dict[str, Any]]:
    found = []
    for path in sorted((home / "setup-studies").glob("*/manifest.json")):
        try:
            if read_json(path).get("find_id") != find_id:
                continue
            summary = read_study(path.parent)
            found.append(
                {
                    "id": path.parent.name,
                    "reading": summary.get("reading"),
                    "labels": summary.get("labels", []),
                    "occurrences": summary.get("occurrences"),
                    "problem": None,
                }
            )
        except _READ_ERRORS as exc:
            found.append(
                {
                    "id": path.parent.name,
                    "reading": None,
                    "labels": [],
                    "occurrences": None,
                    "problem": f"the stored study could not be read: {exc}",
                }
            )
    return found


def _find_entry(home: Path, find_id: str) -> dict[str, Any]:
    folder = home / "setups" / find_id
    entry: dict[str, Any] = {
        "kind": "setup find",
        "id": find_id,
        "recorded_at": None,
        "tested": {},
        "totals": {},
        "labels": [],
        "studies": [],
        "problem": None,
    }
    try:
        manifest = read_json(folder / "manifest.json")
        totals = read_json(folder / "summary.json").get("totals") or {}
    except _READ_ERRORS as exc:
        entry["problem"] = f"the stored find could not be read: {exc}"
        return entry
    assets = [a.get("asset") if isinstance(a, dict) else a for a in manifest.get("assets") or []]
    entry |= {
        "recorded_at": manifest.get("recorded_at"),
        "tested": {
            "idea": manifest.get("idea"),
            "assets": assets,
            "context_bars": manifest.get("context_bars"),
        },
        "totals": {
            "accepted": totals.get("accepted"),
            "pending": totals.get("pending"),
            "set_aside": totals.get("rejected"),
        },
        "labels": manifest.get("labels") or [],
        "studies": _study_entries(home, find_id),
    }
    return entry


def build(home: Path, wanted: str) -> dict[str, Any]:
    identity = cards.resolve(home, wanted)
    card = cards.load(home, identity)
    older, newer = _chain(home, identity)
    ledger = read_trials_readonly(home)
    entries: list[dict[str, Any]] = []
    for link in cards.links_of(home, identity):
        ref = link.get("ref", "")
        if link.get("kind") == "setup_find":
            entries.append(_find_entry(home, ref))
        else:
            row = next(
                (r for r in ledger if r.get("run_id") == ref and r["kind"] == "rule_test"), {}
            )
            entries.append(_rule_entry(home, ref, row))
    entries.sort(key=lambda e: str(e.get("recorded_at") or ""))
    runs = [e for e in entries if e["kind"] == "rule test"]
    finds = [e for e in entries if e["kind"] == "setup find"]
    follows = follows_of_card(home, identity)
    steps = build_map(identity, runs, finds, follows)
    checks = [c for r in runs for c in r["checks"]]
    assets = {r["tested"]["asset"] for r in runs if r["tested"]["asset"] != UNKNOWN}
    assets |= {a for f in finds for a in f["tested"].get("assets") or [] if a}
    refs = {e["id"] for e in entries}
    counted = declarations.counts(c["labels"] for c in checks)
    variants = [c for c in [*older, *newer] if c]
    readings = [{k: v for k, v in e.items() if k != "_manifest"} for e in entries]
    return {
        "card": {
            "id": identity,
            **{name: getattr(card, name) or None for name in cards.LABELS},
            "source": card.source or None,
            "supersedes": card.supersedes or None,
            "superseded_by": newer[0] if newer else None,
        },
        "map": steps,
        "follows": follows,
        "readings": readings,
        "counts": {
            "tests_linked": len(entries),
            "rule_tests": len(runs),
            "setup_finds": len(finds),
            "distinct_assets": len(assets),
            "checks_run": {k: counted[k] for k in ("total", "declared", "exploratory")},
            "variants_of_this_idea": len(variants),
            "trials": [
                {
                    "run": r["id"],
                    **{
                        k: r["reading"]["counts"].get(k)
                        for k in ("trial_n", "family_trials", "variants_tried")
                    },
                }
                for r in runs
                if r["reading"] is not None
            ],
            "ledger_rows_naming_these_runs": sum(1 for r in ledger if r.get("run_id") in refs),
        },
        "open_points": {
            "not_stated": [cards.LABELS[n].lower() for n in card.not_stated()],
            "map_not_yet": [s["step"] for s in steps if s["state"] != DONE],
            "too_little_to_read": [r["id"] for r in runs if r["word"] == "too little to read"],
            "next_steps": next_steps(identity, steps, finds),
        },
    }
