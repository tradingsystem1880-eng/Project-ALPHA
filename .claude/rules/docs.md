---
paths:
  - "docs/**"
---
# Docs rules

- Delivery narratives are appended to `docs/BUILD-STATUS.md`, never rewritten; ADRs are numbered `docs/adr/NNNN-*.md` and every ADR id must be referenced from `CLAUDE.md` or a rule file (`tests/unit/test_repo_awareness_drift.py` checks).
- Feature plans live at `docs/superpowers/plans/YYYY-MM-DD-<slug>.md` with a fenced JSON `FeaturePlan` block (`gate.py plan-check`) and exactly one `**Delivery state:** <state> — <evidence>` line in the first 12 lines (under the title, or line 1 above a leading JSON block). States: `Completed` (merged or BUILD-STATUS-accepted work only), `Implemented – qualification pending`, `In progress`, `Blocked`, `Planned`, `Superseded by <relative path>`.
- On `Completed`/`Superseded`, `git mv` the plan to `docs/superpowers/plans/archive/YYYY-MM/` and fix links (pinned exceptions: `archive/README.md`). Unplanned features go in `docs/roadmap/backlog/<slug>.md`, staged refactors in `docs/roadmap/refactors/<slug>.md` (copy an existing file's template). Then run `uv run python scripts/roadmap_index.py`; `tests/unit/test_plan_schema.py` and `test_roadmap_index.py` enforce this.
- Retrospectives live at `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with a `## Watch-outs` section.

The canonical ADR navigation is `docs/adr/README.md`; retain these reference IDs while the legacy
awareness checker still scans instructions: ADR-0001 ADR-0002 ADR-0003 ADR-0004 ADR-0005 ADR-0006
ADR-0007 ADR-0008 ADR-0009 ADR-0010 ADR-0011 ADR-0012 ADR-0013 ADR-0014 ADR-0015 ADR-0016 ADR-0017
ADR-0018 ADR-0019 ADR-0020 ADR-0021 ADR-0022 ADR-0023 ADR-0024 ADR-0025 ADR-0026 ADR-0027 ADR-0028
ADR-0029 ADR-0030 ADR-0031 ADR-0032 ADR-0033 ADR-0034 ADR-0035 ADR-0036 ADR-0037 ADR-0038 ADR-0039
ADR-0040 ADR-0041.
