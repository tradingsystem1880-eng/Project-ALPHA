"""Aggregate score cards into a versioned summary, a readable report, and version diffs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from alpha_eval.models import Scenario
from alpha_eval.stats import mean_ci, pass_hat_k, wilson

EXCLUDED = {"harness_invalid", "ungraded"}  # never in rate denominators


def _load_cards(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def summarize(
    cards: list[dict[str, Any]],
    scenarios: dict[str, Scenario],
    fingerprint: dict[str, Any],
) -> dict[str, Any]:
    by_sut: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cards:
        by_sut[c["sut"]].append(c)
    suts: dict[str, Any] = {}
    for sut, sc_cards in sorted(by_sut.items()):
        per_scn: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for c in sc_cards:
            per_scn[c["scenario_id"]].append(c)
        valid = [c for c in sc_cards if c["outcome"] not in EXCLUDED]
        scen_rows = {}
        p1, pk_vals, k_used = [], [], None
        for sid, cs in sorted(per_scn.items()):
            vs = [c for c in cs if c["outcome"] not in EXCLUDED]
            n, s = len(vs), sum(1 for c in vs if c["outcome"] == "pass")
            dims: dict[str, list[int]] = defaultdict(list)
            for c in vs:
                for d in c["dimensions"]:
                    if d["score"] is not None:
                        dims[d["dimension"]].append(d["score"])
            row: dict[str, Any] = {
                "tier": cs[0]["tier"],
                "n": n,
                "passes": s,
                "outcomes": [c["outcome"] for c in sorted(cs, key=lambda x: x["trial"])],
                "verdicts": [c["verdict"] for c in sorted(cs, key=lambda x: x["trial"])],
                "criticals": sorted({h["cls"] for c in vs for h in c["criticals"]}),
                "failed_checks": sorted(
                    {ch["id"] for c in vs for ch in c["checks"] if ch["core"] and not ch["passed"]}
                ),
                "dimension_means": {d: round(sum(v) / len(v), 2) for d, v in sorted(dims.items())},
                "excluded": len(cs) - n,
            }
            if n:
                row["pass_rate"] = s / n
                p1.append(s / n)
                k = n
                k_used = k if k_used is None else min(k_used, k)
            scen_rows[sid] = row
        if k_used:
            for row in scen_rows.values():
                if row["n"] >= k_used:
                    row[f"pass^{k_used}"] = pass_hat_k(row["passes"], row["n"], k_used)
                    pk_vals.append(row[f"pass^{k_used}"])
        tiers: dict[str, Any] = {}
        for tier in sorted({r["tier"] for r in scen_rows.values()}):
            rates = [
                r["pass_rate"] for r in scen_rows.values() if r["tier"] == tier and "pass_rate" in r
            ]
            tiers[tier] = {
                "scenarios": len(rates),
                "pass^1": round(sum(rates) / len(rates), 3) if rates else None,
            }
        n_valid = len(valid)
        n_crit = sum(1 for c in valid if c["outcome"] == "critical")
        dim_all: dict[str, list[int]] = defaultdict(list)
        grading_failures: Counter[str] = Counter()
        for c in valid:
            for d in c["dimensions"]:
                if d["score"] is not None:
                    dim_all[d["dimension"]].append(d["score"])
            for g in c["grading_failures"]:
                grading_failures[g.split(":")[0] if ":" in g else g] += 1
        false_edge = [c for c in valid if scenarios[c["scenario_id"]].truth.false_edge]
        endorsed = sum(1 for c in false_edge if c["verdict"] == "support")
        real_edge = [
            c for c in valid if "support" in scenarios[c["scenario_id"]].truth.allowed_verdicts
        ]
        missed = sum(1 for c in real_edge if c["verdict"] == "reject")
        pitfalls: Counter[str] = Counter()
        steps: Counter[str] = Counter()
        agree = []
        disagreements = 0
        for c in valid:
            prim = c["judges"].get("primary", {})
            for p in prim.get("pitfalls") or []:
                pitfalls[p["status"]] += 1
            for st in prim.get("next_steps") or []:
                steps["proposed" if st["proposed"] else "missed"] += 1
            sec = c["judges"].get("second")
            if sec and "verdict_agrees" in sec:
                agree.append(sec["verdict_agrees"])
                disagreements += len(sec.get("disagreements", []))
        crit_list = [
            {
                "scenario": c["scenario_id"],
                "trial": c["trial"],
                "cls": h["cls"],
                "source": h["source"],
                "detail": h["detail"][:300],
                "evidence": h["evidence"][:8],
            }
            for c in valid
            for h in c["criticals"]
        ]
        check_fail = Counter(
            ch["id"] for c in valid for ch in c["checks"] if ch["core"] and not ch["passed"]
        )
        suts[sut] = {
            "trials": len(sc_cards),
            "valid_trials": n_valid,
            "harness_invalid": sum(1 for c in sc_cards if c["outcome"] == "harness_invalid"),
            "ungraded": sum(1 for c in sc_cards if c["outcome"] == "ungraded"),
            "outcomes": dict(Counter(c["outcome"] for c in sc_cards)),
            "pass^1": round(sum(p1) / len(p1), 3) if p1 else None,
            f"pass^{k_used}": round(sum(pk_vals) / len(pk_vals), 3) if pk_vals else None,
            "critical_rate": round(n_crit / n_valid, 3) if n_valid else None,
            "critical_rate_wilson": wilson(n_crit, n_valid) if n_valid else None,
            "false_edge_endorsement": {
                "endorsed": endorsed,
                "trials": len(false_edge),
                "wilson": wilson(endorsed, len(false_edge)) if false_edge else None,
            },
            "real_edge_rejected": {"rejected": missed, "trials": len(real_edge)},
            "tiers": tiers,
            "dimensions": {
                d: dict(zip(("mean", "lo", "hi"), (round(x, 2) for x in mean_ci(v)), strict=True))
                | {"n": len(v)}
                for d, v in sorted(dim_all.items())
            },
            "pitfall_coverage": dict(pitfalls),
            "next_steps": dict(steps),
            "judge_verdict_agreement": round(sum(agree) / len(agree), 3) if agree else None,
            "judge_dimension_disagreements_ge2": disagreements,
            "grading_failures": dict(grading_failures),
            "failed_core_checks": dict(check_fail.most_common()),
            "criticals": crit_list,
            "cost_usd": (
                round(sum(float(c["meta"]["cost_usd"]) for c in sc_cards), 2)
                if all(c["meta"].get("cost_usd") is not None for c in sc_cards)
                else None
            ),
            "scenarios": scen_rows,
        }
    return {"schema_version": 1, "fingerprint": fingerprint, "suts": suts}


def fingerprint(base: Path, scenario_dir: Path) -> dict[str, Any]:
    manifest = base / "manifest.json"
    if manifest.exists():
        from alpha_eval.provenance import digest as content_digest

        frozen = json.loads(manifest.read_text())
        return {
            "suite_sha256": content_digest(frozen["scenarios"]),
            "scorer_sha256": content_digest(frozen["scorer"]),
            "scoring-meta": {
                key: frozen.get(key)
                for key in (
                    "judge_model",
                    "effort",
                    "bridge_sha256",
                    "bridge_schema_sha256",
                    "client_version",
                    "second_judge_tiers",
                )
            },
            "manifest_sha256": content_digest(frozen),
            "acquisition_provenance": frozen.get("provenance"),
        }
    info: dict[str, Any] = {
        "suite_sha256": None,
        "scorer_sha256": None,
        "acquisition_provenance": "Legacy suite and scorer fingerprints unavailable",
    }
    for name in ("workspace-info.json", "scoring-meta.json"):
        p = base / name
        if p.exists():
            info[name.removesuffix(".json")] = json.loads(p.read_text(encoding="utf-8"))
    return info


def render_markdown(summary: dict[str, Any], probes: dict[str, Any] | None = None) -> str:
    lines = ["# alpha-eval benchmark summary", ""]
    fp = summary["fingerprint"]
    lines.append(
        f"- suite sha256 `{(fp.get('suite_sha256') or 'unknown')[:16]}` · scorer `{(fp.get('scorer_sha256') or 'unknown')[:16]}`"
        f" · workspace ref `{fp.get('workspace-info', {}).get('ref_sha', '')[:12]}`"
        f" · judge `{fp.get('scoring-meta', {}).get('judge_model', '')}`"
    )
    lines.append("")
    for sut, s in summary["suts"].items():
        k = [key for key in s if key.startswith("pass^") and key != "pass^1"]
        lines += [
            f"## SUT `{sut}`",
            "",
            f"- trials {s['trials']} (valid {s['valid_trials']}, harness-invalid {s['harness_invalid']}, ungraded {s['ungraded']}); cost ${s['cost_usd']}",
            f"- **pass^1 {s['pass^1']}**"
            + (f" · {k[0]} {s[k[0]]}" if k else "")
            + f" · critical rate {s['critical_rate']} (Wilson {tuple(round(x, 3) for x in s['critical_rate_wilson'] or ())})",
            f"- false-edge endorsement {s['false_edge_endorsement']['endorsed']}/{s['false_edge_endorsement']['trials']}"
            f" · real edge rejected {s['real_edge_rejected']['rejected']}/{s['real_edge_rejected']['trials']}",
            f"- pitfalls {s['pitfall_coverage']} · next steps {s['next_steps']}",
            f"- judge verdict agreement {s['judge_verdict_agreement']} · dimension disagreements ≥2: {s['judge_dimension_disagreements_ge2']}"
            f" · grading failures {s['grading_failures']}",
            "",
            "| tier | scenarios | pass^1 |",
            "|---|---|---|",
        ]
        for tier, t in s["tiers"].items():
            lines.append(f"| {tier} | {t['scenarios']} | {t['pass^1']} |")
        lines += ["", "| dimension | mean | 95% CI | n |", "|---|---|---|---|"]
        for d, v in sorted(s["dimensions"].items(), key=lambda kv: kv[1]["mean"]):
            lines.append(f"| {d} | {v['mean']} | [{v['lo']}, {v['hi']}] | {v['n']} |")
        lines += [
            "",
            "| scenario | pass | outcomes | verdicts | failed core checks | criticals |",
            "|---|---|---|---|---|---|",
        ]
        for sid, r in s["scenarios"].items():
            lines.append(
                f"| {sid} | {r['passes']}/{r['n']} | {' '.join(r['outcomes'])} | {' '.join(r['verdicts'])} "
                f"| {', '.join(r['failed_checks'])} | {', '.join(r['criticals'])} |"
            )
        if s["criticals"]:
            lines += ["", "### Critical failures", ""]
            for c in s["criticals"]:
                lines.append(
                    f"- `{c['scenario']}` t{c['trial']} **{c['cls']}** ({c['source']}): {c['detail']}"
                )
        lines.append("")
    if probes:
        lines += [
            "## Layer A platform probes",
            "",
            "| probe | classification | finding |",
            "|---|---|---|",
        ]
        for p in probes["probes"]:
            lines.append(
                f"| {p['id']} {p['title']} | {p['classification']} | {p['detail'][:400]} |"
            )
    return "\n".join(lines) + "\n"


def compare(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Per-SUT, per-scenario pass-rate and per-dimension deltas (new - old) on shared items."""
    out: dict[str, Any] = {"old": old["fingerprint"], "new": new["fingerprint"], "suts": {}}
    keys = ("suite_sha256", "scorer_sha256", "scoring-meta")
    mismatch = [
        k
        for k in keys
        if not old["fingerprint"].get(k) or old["fingerprint"].get(k) != new["fingerprint"].get(k)
    ]
    out["compatible"] = not mismatch
    out["incompatible_fields"] = mismatch
    if mismatch:
        return out
    for sut in sorted(set(old["suts"]) & set(new["suts"])):
        o, n = old["suts"][sut], new["suts"][sut]
        scen = {}
        for sid in sorted(set(o["scenarios"]) & set(n["scenarios"])):
            a, b = o["scenarios"][sid], n["scenarios"][sid]
            if "pass_rate" in a and "pass_rate" in b:
                delta = b["pass_rate"] - a["pass_rate"]
                # Adaptive, sparse diagnostic runs do not establish improvement.
                status = "unchanged" if delta == 0 else "inconclusive"
                scen[sid] = {
                    "old": a["pass_rate"],
                    "new": b["pass_rate"],
                    "delta": round(delta, 3),
                    "status": status,
                    "new_criticals": sorted(set(b["criticals"]) - set(a["criticals"])),
                }
        dims = {}
        for d in sorted(set(o["dimensions"]) & set(n["dimensions"])):
            a, b = o["dimensions"][d], n["dimensions"][d]
            dims[d] = {
                "old": a["mean"],
                "new": b["mean"],
                "delta": round(b["mean"] - a["mean"], 2),
                "status": "unchanged" if b["mean"] == a["mean"] else "inconclusive",
            }
        out["suts"][sut] = {
            "pass^1": {"old": o["pass^1"], "new": n["pass^1"]},
            "critical_rate": {"old": o["critical_rate"], "new": n["critical_rate"]},
            "scenarios": scen,
            "dimensions": dims,
        }
    return out
