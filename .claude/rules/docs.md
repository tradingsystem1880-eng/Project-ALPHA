---
paths:
  - "docs/**"
---
# Docs rules

- Delivery narratives are appended to `docs/BUILD-STATUS.md`, never rewritten; ADRs are numbered `docs/adr/NNNN-*.md` and every ADR id must be referenced from `CLAUDE.md` or a rule file (`gate.py brief` reports drift).
- Feature plans live at `docs/superpowers/plans/YYYY-MM-DD-<slug>.md` with a fenced JSON `FeaturePlan` block (`gate.py plan-check`); mark finished plans with a `**Delivery state:** Completed` header line.
- Retrospectives live at `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with a `## Watch-outs` section (surfaced by the generated session brief).

The canonical ADR navigation is `docs/adr/README.md`; retain these reference IDs while the legacy
awareness checker still scans instructions: ADR-0001 ADR-0002 ADR-0003 ADR-0004 ADR-0005 ADR-0006
ADR-0007 ADR-0008 ADR-0009 ADR-0010 ADR-0011 ADR-0012 ADR-0013 ADR-0014 ADR-0015 ADR-0016 ADR-0017
ADR-0018 ADR-0019 ADR-0020 ADR-0021 ADR-0022 ADR-0023 ADR-0024 ADR-0025 ADR-0026 ADR-0027 ADR-0028
ADR-0029 ADR-0030 ADR-0031 ADR-0032 ADR-0033 ADR-0034 ADR-0035 ADR-0036.
