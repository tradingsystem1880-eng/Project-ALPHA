#!/usr/bin/env python3
"""Codex second-model seam for Project ALPHA (optional, graceful, read-only).

    python3 scripts/codex_bridge.py probe
    python3 scripts/codex_bridge.py review  (--uncommitted | --diff FILE) [--model M] [--effort E]
    python3 scripts/codex_bridge.py research --question "..." [--model M] [--effort E]

Runs the ChatGPT-authenticated ``codex`` CLI non-interactively (``codex exec`` with a
read-only sandbox, ephemeral session, an output JSON schema and a wall-clock cap) and prints
ONE JSON object shaped like ``harness_models.CodexReview`` / ``CodexResearch``. Codex is a
second opinion only: every failure mode (no binary, not logged in, model missing from the
models cache, quota/rate limit, timeout, malformed output) yields ``available: false`` with an
``unavailable:<reason>`` and exit code 0 — a gate must never depend on this script.

Model resolution: ``--model`` > ``ALPHA_CODEX_MODEL`` > ``gpt-5.3-codex-spark``; the model must
be present in ``$CODEX_HOME/models_cache.json``. Effort defaults to ``xhigh``. Every call is
audited as ``codex_call``. Stdlib only (runs from any agent's sandbox); output fields are
coerced to the schema here and re-validated by the SubagentStop hook.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402  (sibling module: repo_root, append_audit, codex_probe)

DEFAULT_MODEL = "gpt-5.3-codex-spark"
MODEL_ENV = "ALPHA_CODEX_MODEL"
DEFAULT_EFFORT = "xhigh"
REVIEW_TIMEOUT = 900.0
RESEARCH_TIMEOUT = 600.0
MAX_DIFF_BYTES = 200_000
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

_REVIEW_PROMPT = """You are a second-opinion code reviewer for a Python quantitative-research repo.
Review ONLY the diff below. Return findings, never fixes, never praise.
Axes: (1) correctness, (2) tests (failing-first, would they catch the regression),
(3) fail-loud discipline (typed errors, no swallowed exceptions, degenerate inputs rejected),
(4) conventions (Polars-default, mypy --strict typing), (5) security/authority (no new paths
around owner-authority verbs, no credentials, no network in offline paths), (6) BLOAT (lines that
do not trace to the request, speculative abstractions, unrequested knobs), (7) statistical
semantics (seed derivation, threshold direction >= vs >, estimator conventions, annualization,
look-ahead: data must flow only through the point-in-time `as_of` seam; decide at close of t,
fill at open of t+1).
Each finding: severity high|medium|low, file, line (or null), one-sentence summary, axis.
Respond with the JSON object the schema describes and nothing else.

<diff>
{diff}
</diff>
"""

_RESEARCH_PROMPT = """You are a research assistant checking claims against PRIMARY sources
(peer-reviewed papers, official documentation, standards). Question:

{question}

Return claims, each with the source (author/year/title or URL), a short verbatim quote that
supports it, and confidence high|medium|low. Prefer fewer well-sourced claims over many weak
ones; a claim without a quotable source gets confidence low. Never give trading advice.
Respond with the JSON object the schema describes and nothing else.
"""

# Instruction-shaped text from an untrusted model is stripped before anything reads it.
_INJECTION = re.compile(
    r"(ignore (all|any|the|previous|prior)|disregard|you must|approve (this|the)|"
    r"run `|execute |disable the (harness|hook|gate)|override|as the (owner|system|admin)|"
    r"gate\.py (ack|override)|ALPHA_HARNESS_DISABLE)",
    re.IGNORECASE,
)
_LEVELS = ("high", "medium", "low")


def resolve_model(explicit: str | None) -> str:
    return explicit or os.environ.get(MODEL_ENV) or DEFAULT_MODEL


def cached_models() -> list[str]:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    data = gate.read_json(home / "models_cache.json") or {}
    models = data.get("models", [])
    return [str(m["slug"]) for m in models if isinstance(m, dict) and m.get("slug")]


def probe(model: str) -> dict[str, Any]:
    """Availability only — never calls the model."""
    ok, detail = gate.codex_probe()
    if not ok:
        return {"available": False, "reason": f"unavailable: {detail}", "model": model}
    models = cached_models()
    if models and model not in models:
        return {
            "available": False,
            "reason": f"unavailable: model {model!r} not in models cache ({', '.join(models[:8])})",
            "model": model,
        }
    return {"available": True, "reason": "", "model": model, "login": detail}


def sanitize(text: str) -> str:
    return "[stripped: instruction-shaped text]" if _INJECTION.search(text) else text


def _level(value: Any) -> str:
    level = str(value).lower()
    return level if level in _LEVELS else "low"


def _run_codex(
    root: Path, prompt: str, schema: Path, model: str, effort: str, timeout: float, extra: list[str]
) -> tuple[str | None, str]:
    """Run codex exec; return (last message text, error). Read-only, ephemeral, capped."""
    with tempfile.TemporaryDirectory(prefix="codex-bridge-") as tmp:
        out = Path(tmp) / "last.json"
        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-s",
            "read-only",
            "-C",
            str(root),
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{effort}"',
            "-c",
            'approval_policy="never"',
            *extra,
            "--output-schema",
            str(schema),
            "-o",
            str(out),
            "--color",
            "never",
            "-",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=root,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (None, f"unavailable: codex exceeded {int(timeout)}s wall-clock cap")
        except OSError as exc:
            return (None, f"unavailable: codex could not start: {exc!r}")
        if not out.is_file():
            tail = (proc.stderr or proc.stdout).strip()[-300:]
            return (None, f"unavailable: codex exit {proc.returncode} without output ({tail})")
        return (out.read_text(), "")


def _parse_object(text: str) -> dict[str, Any] | None:
    body = text.strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(body[start : end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _finding(item: dict[str, Any]) -> dict[str, Any]:
    line = item.get("line")
    return {
        "severity": _level(item.get("severity", "low")),
        "file": str(item.get("file", "")),
        "line": int(line) if isinstance(line, int | float) else None,
        "summary": sanitize(str(item.get("summary", ""))),
        "axis": str(item.get("axis", "unspecified")),
    }


def _claim(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim": sanitize(str(item.get("claim", ""))),
        "source": sanitize(str(item.get("source", ""))),
        "quote": sanitize(str(item.get("quote", ""))),
        "confidence": _level(item.get("confidence", "low")),
    }


# kind -> (schema file, list key, extra codex -c flags, item coercer)
_KINDS: dict[str, tuple[str, str, list[str], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    "review": ("codex_review.json", "findings", [], _finding),
    "research": ("codex_research.json", "claims", ["-c", 'web_search="live"'], _claim),
}


def _unavailable(kind: str, model: str, reason: str, question: str = "") -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "model": model,
        "available": False,
        "unavailable_reason": reason,
        "summary": "",
    }
    if kind == "research":
        base["question"] = question
    base[_KINDS[kind][1]] = []
    return base


def _call(
    kind: str,
    root: Path,
    prompt: str,
    model: str,
    effort: str,
    timeout: float,
    question: str = "",
) -> dict[str, Any]:
    schema_name, list_key, extra, coerce = _KINDS[kind]
    text, error = _run_codex(root, prompt, SCHEMA_DIR / schema_name, model, effort, timeout, extra)
    if text is None:
        return _unavailable(kind, model, error, question)
    raw = _parse_object(text)
    if raw is None or not isinstance(raw.get(list_key), list):
        return _unavailable(
            kind, model, f"unavailable: codex output was not the {kind} schema", question
        )
    result: dict[str, Any] = {
        "schema_version": 1,
        "model": model,
        "available": True,
        "unavailable_reason": None,
    }
    if kind == "research":
        result["question"] = question
    result[list_key] = [coerce(item) for item in raw[list_key] if isinstance(item, dict)]
    result["summary"] = sanitize(str(raw.get("summary", "")))
    return result


def review(
    root: Path, *, diff: str, model: str, effort: str, timeout: float = REVIEW_TIMEOUT
) -> dict[str, Any]:
    if not diff.strip():
        return _unavailable("review", model, "unavailable: empty diff — nothing to review")
    if len(diff.encode()) > MAX_DIFF_BYTES:
        diff = diff.encode()[:MAX_DIFF_BYTES].decode(errors="ignore") + "\n[diff truncated]\n"
    return _call("review", root, _REVIEW_PROMPT.format(diff=diff), model, effort, timeout)


def research(
    root: Path, *, question: str, model: str, effort: str, timeout: float = RESEARCH_TIMEOUT
) -> dict[str, Any]:
    if not question.strip():
        return _unavailable("research", model, "unavailable: empty question", question)
    prompt = _RESEARCH_PROMPT.format(question=question)
    return _call("research", root, prompt, model, effort, timeout, question)


def _audit(root: Path, kind: str, model: str, result: dict[str, Any]) -> None:
    detail = f"{kind} model={model} available={result.get('available')}"
    if not result.get("available"):
        detail += f" reason={str(result.get('unavailable_reason'))[:120]}"
    try:
        gate.append_audit(root, "codex_call", detail)
    except Exception as exc:  # noqa: BLE001 - the audit never breaks the optional seam
        print(f"[codex-bridge] audit append failed: {exc!r}", file=sys.stderr)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="codex_bridge.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe").add_argument("--model", default=None)
    for name, default_timeout in (("review", REVIEW_TIMEOUT), ("research", RESEARCH_TIMEOUT)):
        p = sub.add_parser(name)
        p.add_argument("--model", default=None)
        p.add_argument("--effort", default=DEFAULT_EFFORT)
        p.add_argument("--timeout", type=float, default=default_timeout)
        if name == "review":
            p.add_argument("--uncommitted", action="store_true")
            p.add_argument("--diff", default=None, help="file holding the diff to review")
        else:
            p.add_argument("--question", required=True)
    args = parser.parse_args(argv)
    model = resolve_model(args.model)
    root = gate.repo_root()

    if args.cmd == "probe":
        print(json.dumps(probe(model), indent=2))
        return 0

    avail = probe(model)
    if not avail["available"]:
        result = _unavailable(args.cmd, model, avail["reason"], getattr(args, "question", ""))
    elif args.cmd == "review":
        if args.diff:
            diff = Path(args.diff).read_text()
        elif args.uncommitted:
            diff = gate._git(root, "diff", "HEAD", check=False)
        else:
            parser.error("review needs --uncommitted or --diff FILE")
        result = review(root, diff=diff, model=model, effort=args.effort, timeout=args.timeout)
    else:
        result = research(
            root, question=args.question, model=model, effort=args.effort, timeout=args.timeout
        )
    _audit(root, args.cmd, model, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
