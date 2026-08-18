---
paths:
  - "docs/**"
---
# Docs rules

- Delivery narratives are appended to `docs/BUILD-STATUS.md`, never rewritten; ADRs are numbered `docs/adr/NNNN-*.md` and every ADR id must be referenced from `CLAUDE.md` or a rule file (`gate.py brief` reports drift).
- Feature plans live at `docs/superpowers/plans/YYYY-MM-DD-<slug>.md` with a fenced JSON `FeaturePlan` block (`gate.py plan-check`); mark finished plans with a `**Delivery state:** Completed` header line.
- Retrospectives live at `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with a `## Watch-outs` section (surfaced by the generated session brief).
