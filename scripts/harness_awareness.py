"""ADR awareness drift and feature-plan front-block checks, imported lazily by gate.py."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ADR_ID_RE = re.compile(r"^(\d{4})-")


def adr_files(root: Path) -> list[str]:
    """ADR filenames (``NNNN-*.md``) in docs/adr, sorted."""
    adr_dir = root / "docs" / "adr"
    if not adr_dir.is_dir():
        return []
    return sorted(p.name for p in adr_dir.glob("*.md") if _ADR_ID_RE.match(p.name))


_ADR_MENTION_RE = re.compile(r"ADRs?[ -](\d{4})(?:(?:\.\.|-|–)(\d{4}))?")


def referenced_adr_ids(text: str) -> set[int]:
    """ADR numbers a document mentions: ``ADR-0013``, ``ADRs 0013-0016``, ``ADR-0021..0026``."""
    ids: set[int] = set()
    for start, end in _ADR_MENTION_RE.findall(text):
        lo, hi = int(start), int(end or start)
        ids.update(range(lo, hi + 1))
    return ids


_INDEX_LINK_RE = re.compile(r"\]\(\s*(?:\./)?(\d{4}-[^)\s#]+\.md)")


def adr_drift(root: Path) -> list[str]:
    """ADR files that the ADR index ``docs/adr/README.md`` does not link (its one listing)."""
    index = root / "docs" / "adr" / "README.md"
    text = index.read_text(errors="replace") if index.exists() else ""
    linked = set(_INDEX_LINK_RE.findall(text))
    ids: list[str] = []
    for name in adr_files(root):
        if name not in linked:
            match = _ADR_ID_RE.match(name)
            assert match is not None
            ids.append(f"ADR-{match.group(1)}")
    return ids


# ---- feature plans: a machine-checked front block in docs/work/<task>/02-plan.md ------

_PLAN_BLOCK_RE = re.compile(r"^```json[ \t]*\n(.*?)\n```", re.S | re.M)


def plan_front_block(text: str) -> dict[str, Any] | None:
    """The first fenced ```json block of a plan doc as a dict; None if absent/invalid JSON."""
    match = _PLAN_BLOCK_RE.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def plan_check(path: Path) -> tuple[bool, str]:
    """Validate a plan doc's front block against ``FeaturePlan`` (pydantic required)."""
    from harness_models import FeaturePlan
    from pydantic import ValidationError

    try:
        text = path.read_text()
    except OSError as exc:
        return (False, f"cannot read {path}: {exc}")
    name = path.parent.name if path.name == "02-plan.md" else path.name
    block = plan_front_block(text)
    if block is None:
        return (False, f"{name}: no fenced ```json front block (or it is not a JSON object)")
    try:
        plan = FeaturePlan.model_validate(block)
    except ValidationError as exc:
        return (False, f"{name}: FeaturePlan invalid:\n{exc}")
    done = sum(1 for s in plan.slices if s.status == "done")
    return (
        True,
        f"{name}: FeaturePlan ok — {len(plan.slices)} slice(s), {done} done; "
        f"tier impact {', '.join(plan.tier_impact)}; "
        f"{len(plan.assumptions)} assumption(s), {len(plan.pre_mortem)} pre-mortem item(s)",
    )
