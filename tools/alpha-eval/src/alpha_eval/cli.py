"""alpha-eval command line."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from alpha_eval.models import Scenario
from alpha_eval.platform import tool_root
from alpha_eval.provenance import revision_path


def revision_scenarios(base: Path, revision: str) -> dict[str, Scenario]:
    from alpha_eval.scenarios import load_all

    if revision:
        manifest = json.loads((revision_path(base, revision) / "manifest.json").read_text())
        return {sid: Scenario.model_validate(sc) for sid, sc in manifest["scenarios"].items()}
    return {s.id: s for s in load_all()}


def write_text_once(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8") as f:
        f.write(text)


def _cmd_probe(args: argparse.Namespace) -> int:
    from alpha_eval.probes import ProbeContext, run_probes

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    ctx = ProbeContext(workdir=work, seeds=args.seeds, parallel=args.parallel)
    started = time.time()
    results = run_probes(ctx, args.ids.split(",") if args.ids else None)
    payload = {
        "layer": "A",
        "seeds": args.seeds,
        "seconds": round(time.time() - started, 1),
        "probes": [r.to_json() for r in results],
    }
    (out / "probes.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    for r in results:
        print(f"{r.id:5} {r.classification:26} {r.title}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from alpha_eval.runner import DEFAULT_HOME, run_trials
    from alpha_eval.scenarios import load_all, select

    scenarios = select(load_all(), args.ids, args.tiers)
    if not scenarios:
        print("no scenarios selected", file=sys.stderr)
        return 2
    base = Path(args.base) if args.base else DEFAULT_HOME / args.name
    print(f"running {len(scenarios)} scenarios x {args.trials} trials x {args.suts} into {base}")
    run_trials(
        scenarios, args.suts.split(","), args.trials, base, args.parallel, resume=args.resume
    )
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    from alpha_eval.runner import DEFAULT_HOME, score_all
    from alpha_eval.scenarios import load_all

    base = Path(args.base) if args.base else DEFAULT_HOME / args.name
    scenarios = {s.id: s for s in load_all()}
    tiers = {t for t in args.second_judge_tiers.split(",") if t}
    out = score_all(
        base,
        scenarios,
        args.parallel,
        tiers,
        args.judge_model,
        revision=args.revision,
        effort=args.effort,
        resume=args.resume,
        reuse_revision=args.reuse_revision,
    )
    print(f"score cards -> {out}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from alpha_eval.report import _load_cards, fingerprint, render_markdown, summarize
    from alpha_eval.runner import DEFAULT_HOME
    from alpha_eval.scenarios import SCENARIO_DIR

    base = Path(args.base) if args.base else DEFAULT_HOME / args.name
    scenarios = revision_scenarios(base, args.revision)
    summary = summarize(
        _load_cards(
            (revision_path(base, args.revision) if args.revision else base) / "scorecards.jsonl"
        ),
        scenarios,
        fingerprint(revision_path(base, args.revision) if args.revision else base, SCENARIO_DIR),
    )
    probes = json.loads(Path(args.probes).read_text(encoding="utf-8")) if args.probes else None
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_text_once(out / "summary.json", json.dumps(summary, indent=1, default=str))
    write_text_once(out / "report.md", render_markdown(summary, probes))
    if probes:
        (out / "probes.json").write_text(json.dumps(probes, indent=1), encoding="utf-8")
    print(f"summary -> {out}")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    from alpha_eval.analysis import analyze, render
    from alpha_eval.report import _load_cards
    from alpha_eval.runner import DEFAULT_HOME

    base = Path(args.base) if args.base else DEFAULT_HOME / args.name
    scenarios = revision_scenarios(base, args.revision)
    controlled = (
        _load_cards(DEFAULT_HOME / args.controlled / "scorecards.jsonl")
        if args.controlled
        else None
    )
    result = analyze(
        _load_cards(
            (revision_path(base, args.revision) if args.revision else base) / "scorecards.jsonl"
        ),
        scenarios,
        controlled,
        args.reference_sut,
        args.comparator_sut,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_text_once(out / "analysis.json", json.dumps(result, indent=1, default=str))
    write_text_once(out / "analysis.md", render(result))
    print(f"analysis -> {out}")
    return 0


def _cmd_regress(args: argparse.Namespace) -> int:
    from alpha_eval.regression import evaluate, load_manifest, render
    from alpha_eval.report import _load_cards
    from alpha_eval.runner import DEFAULT_HOME

    base = Path(args.base) if args.base else DEFAULT_HOME / args.name
    card_path = (revision_path(base, args.revision) if args.revision else base) / "scorecards.jsonl"
    cards = _load_cards(card_path) if card_path.exists() else []
    probes = json.loads(Path(args.probes).read_text(encoding="utf-8")) if args.probes else None
    rows = evaluate(load_manifest(), cards, probes)
    text = render(rows)
    print(text)
    if args.out:
        write_text_once(Path(args.out), text)
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    from alpha_eval.report import compare

    old = json.loads(Path(args.old).read_text(encoding="utf-8"))
    new = json.loads(Path(args.new).read_text(encoding="utf-8"))
    print(json.dumps(compare(old, new), indent=1))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from alpha_eval.scenarios import load_all

    for s in load_all():
        print(f"{s.id:32} {s.tier:12} turns={len(s.turns):2} world={s.world or '-':8} {s.title}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alpha-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)
    probe = sub.add_parser("probe", help="Layer A deterministic platform probes")
    probe.add_argument("--out", default=str(tool_root() / "results" / "probes-latest"))
    probe.add_argument("--seeds", type=int, default=20)
    probe.add_argument("--parallel", type=int, default=6)
    probe.add_argument("--ids", default="")
    probe.set_defaults(func=_cmd_probe)
    lst = sub.add_parser("list", help="list scenarios")
    lst.set_defaults(func=_cmd_list)
    run = sub.add_parser("run", help="Layer B: run SUT trials")
    run.add_argument("--suts", default="codex:gpt-6-astra")
    run.add_argument("--ids", default="")
    run.add_argument("--tiers", default="")
    run.add_argument("--trials", type=int, default=3)
    run.add_argument("--parallel", type=int, default=2)
    run.add_argument("--name", default="latest")
    run.add_argument("--base", default="")
    run.add_argument(
        "--resume", action="store_true", help="re-run only missing or harness-invalid trials"
    )
    run.set_defaults(func=_cmd_run)
    score = sub.add_parser("score", help="judge + score all trajectories under a run base")
    score.add_argument("--name", default="latest")
    score.add_argument("--base", default="")
    score.add_argument("--parallel", type=int, default=2)
    score.add_argument("--judge-model", default="gpt-6-astra")
    score.add_argument("--second-judge-tiers", default="")
    score.add_argument("--revision", required=True)
    score.add_argument("--effort", default="medium")
    score.add_argument("--resume", action="store_true")
    score.add_argument(
        "--reuse-revision", default="", help="reuse exact matching primary judgments"
    )
    score.set_defaults(func=_cmd_score)
    rep = sub.add_parser("report", help="aggregate score cards into summary.json + report.md")
    rep.add_argument("--name", default="latest")
    rep.add_argument("--base", default="")
    rep.add_argument("--probes", default="")
    rep.add_argument("--out", required=True)
    rep.add_argument("--revision", default="")
    rep.set_defaults(func=_cmd_report)
    ana = sub.add_parser("analyze", help="objective-level analysis of realistic scenarios")
    ana.add_argument("--name", default="latest")
    ana.add_argument("--base", default="")
    ana.add_argument("--controlled", default="", help="run name of the controlled-suite baseline")
    ana.add_argument("--out", required=True)
    ana.add_argument("--revision", default="")
    ana.add_argument("--reference-sut", default="codex:gpt-6-astra")
    ana.add_argument("--comparator-sut", default="")
    ana.set_defaults(func=_cmd_analyze)
    reg = sub.add_parser("regress", help="check the regression manifest against a run")
    reg.add_argument("--name", default="latest")
    reg.add_argument("--base", default="")
    reg.add_argument("--probes", default="")
    reg.add_argument("--out", default="")
    reg.add_argument("--revision", default="")
    reg.set_defaults(func=_cmd_regress)
    cmp_ = sub.add_parser("compare", help="diff two summary.json files")
    cmp_.add_argument("old")
    cmp_.add_argument("new")
    cmp_.set_defaults(func=_cmd_compare)
    args = parser.parse_args(argv)
    code: int = args.func(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
