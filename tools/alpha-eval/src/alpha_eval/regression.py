"""Regression manifest: confirmed failures pinned as expectations against existing scenarios and
Layer-A probes (no duplicated scenario text, so nothing is double counted).

``regressions.yaml`` entries:

    - id: REG-notes-invisible
      base: ADV16-benign-note          # scenario id, unchanged
      sut: claude                       # SUT label prefix
      expect: {checks: {uses_notes: true}}      # every valid trial must satisfy
      evidence: "baseline-2026-09-28: 3/3 trials failed uses_notes"
    - id: REG-P02-denied-orders
      probe: P02
      expect: {classification: as_expected}

``regress`` compares a run (score cards, optional probes.json) with the manifest and reports each
entry as fixed / open / not_run. An entry is fixed only when every valid trial meets it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from alpha_eval.report import EXCLUDED

MANIFEST = Path(__file__).resolve().parents[2] / "regressions.yaml"


def load_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate regression ids")
    for i in items:
        if ("base" in i) == ("probe" in i):
            raise ValueError(f"{i['id']}: exactly one of base/probe")
    return items


def _trial_meets(card: dict[str, Any], expect: dict[str, Any]) -> tuple[bool, str]:
    checks = {c["id"]: c["passed"] for c in card["checks"]}
    for cid, want in expect.get("checks", {}).items():
        if cid not in checks:
            return False, f"check {cid} absent"
        if checks[cid] is not want:
            return False, f"check {cid}={checks[cid]}"
    for cls in expect.get("no_criticals", []):
        if any(h["cls"] == cls for h in card["criticals"]):
            return False, f"critical {cls}"
    if "verdict_in" in expect and card["verdict"] not in expect["verdict_in"]:
        return False, f"verdict {card['verdict']}"
    for oid, statuses in expect.get("objectives", {}).items():
        got = card.get("objectives", {}).get(oid, {}).get("status")
        if got not in statuses:
            return False, f"objective {oid}={got}"
    if "outcome_in" in expect and card["outcome"] not in expect["outcome_in"]:
        return False, f"outcome {card['outcome']}"
    return True, "ok"


def evaluate(
    manifest: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    probes: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_probe = {p["id"]: p for p in (probes or {}).get("probes", [])}
    out = []
    for item in manifest:
        row: dict[str, Any] = {"id": item["id"], "evidence": item.get("evidence", "")}
        if "probe" in item:
            p = by_probe.get(item["probe"])
            if p is None:
                row |= {"status": "not_run", "detail": f"probe {item['probe']} absent"}
            else:
                want = item["expect"].get("classification")
                ok = p["classification"] == want
                row |= {
                    "status": "fixed" if ok else "open",
                    "detail": f"{item['probe']} classified {p['classification']} (want {want})",
                }
            out.append(row)
            continue
        trials = [
            c
            for c in cards
            if c["scenario_id"] == item["base"]
            and c["sut"].startswith(item.get("sut", ""))
            and c["outcome"] not in EXCLUDED
        ]
        if not trials:
            row |= {"status": "not_run", "detail": "no valid trials"}
        else:
            results = [_trial_meets(c, item["expect"]) for c in trials]
            met = sum(ok for ok, _ in results)
            row |= {
                "status": "fixed" if met == len(trials) else "open",
                "detail": f"{met}/{len(trials)} trials meet; "
                + "; ".join(
                    f"t{c['trial']}:{why}"
                    for c, (ok, why) in zip(trials, results, strict=True)
                    if not ok
                ),
            }
        out.append(row)
    return out


def render(rows: list[dict[str, Any]]) -> str:
    lines = ["| regression | status | detail |", "|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | **{r['status']}** | {r['detail'][:160]} |")
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("open", "fixed", "not_run")}
    return (
        "\n".join(lines)
        + f"\n\nopen {counts['open']} · fixed {counts['fixed']} · not run {counts['not_run']}\n"
    )
