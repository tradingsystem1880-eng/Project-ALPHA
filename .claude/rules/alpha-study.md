---
paths:
  - "packages/alpha-study/**"
---
# alpha_study rules

`alpha_study` is an additive research-plane composition/projection seam. S3a owns
strict immutable `FeatureInputRefV1`, `FeatureValueV1`, `EventTableV1`, and the
separate `FactorObservationTableV1` contracts. They carry content-bound, explicitly
`unverified_reference` declarations for causal UTC clocks and multi-artifact, snapshot,
vintage, computation, provider, family, frequency, venue, operator, and universe
lineage. Event tables contain no realized outcomes; none contain operational timestamps
or grant evidence or execution authority.

## Module map

- `values.py` — strict, content-hashed `FeatureInputRefV1` and `FeatureValueV1`
  unverified lineage projections.
- `tables.py` — sealed event-occurrence and cross-sectional factor geometries with
  canonical ordering, derived IDs, universe availability, and `authority: none`.

The package owns no persistence, CLI commands, UI, external dependencies, approvals,
D1/D2 transitions, promotion, paper, broker, or order authority. Canonical projections
must remain derived, content-hashed references to existing authoritative records.

The package may depend only on the approved lower-layer inputs recorded in the root
import-linter contract: `alpha_core`, `alpha_data`, `alpha_patterns`, and
`alpha_research`. The package must not import strategy, backtest, validation,
forecast, options, screener, CLI, MCP, or web surfaces. Lower layers and the two
top-of-DAG surfaces must not import `alpha_study`.

Only an existing-authority CLI/ControlStore verifier may upgrade a reference into
usable PIT lineage. Any future analytical or authority-linked implementation must map
to that seam before code is added. D1 remains owner-launched, MCP
remains pinned at 62 tools, and external capabilities remain deferred until separately
approved and isolated.
