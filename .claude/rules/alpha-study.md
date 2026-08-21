---
paths:
  - "packages/alpha-study/**"
---
# alpha_study rules

`alpha_study` is an additive research-plane composition seam. S2 contains only the
package boundary and metadata; it owns no canonical contracts, persistence, CLI
commands, UI, external dependencies, approvals, D1/D2 transitions, promotion,
paper, broker, or order authority.

The package may depend only on the approved lower-layer inputs recorded in the root
import-linter contract: `alpha_core`, `alpha_data`, `alpha_patterns`, and
`alpha_research`. The package must not import strategy, backtest, validation,
forecast, options, screener, CLI, MCP, or web surfaces. Lower layers and the two
top-of-DAG surfaces must not import `alpha_study`.

Any future contract or analytical implementation must map to an existing authoritative
research/control-store seam before code is added. D1 remains owner-only, MCP remains
pinned at 62 tools, and external capabilities remain deferred until separately
approved and isolated.
