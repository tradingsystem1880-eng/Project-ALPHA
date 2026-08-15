# Crypto Branch Simplification and Acceptance Report

- **Branch:** `codex/full-repair-program`
- **Baseline:** `origin/main` at `1b256b0`
- **Local verification date:** 2026-08-15
- **Publication status:** **blocked on owner/environment checkpoints; not merged**

## Outcome

The branch-owned crypto and research changes are locally green, including the governed Bybit
crowding operator, the sandbox-only hedged-basis candidate, the guided Workstation flow, immutable
Expansion storage, and the complete deterministic pre-paper lifecycle. No live order, paper entry,
research-gate override, holdout reveal, or owner decision was performed during acceptance.

The real research case reached its next legitimate boundary and stopped: one exact compatible
Bybit snapshot is registered and audited, but the case cannot proceed until lawful literature is
acquired, its claims are owner-screened, and a source pack is frozen. This is a correct fail-closed
result, not a simulated completion.

## Simplification and review

The main crypto CLI facade began at 4,120 lines. Behavior-preserving extraction reduced it to 3,842
lines while keeping Typer commands, private compatibility seams, error text, manifest identities,
and V1 reads stable:

- provider acquisition planning and Bybit dispatch live in `_crypto_acquisition.py`;
- qualification, snapshot membership, features, and comparison projections live in
  `_crypto_analysis.py`;
- immutable coverage-batch hashing, validation, and checkpoint persistence live in
  `_crypto_coverage.py`;
- the Crypto Data Center acquisition controls are separated from its controller and focused views;
- candidate suite actions use one table-driven dispatch path.

The five-axis review found and repaired credential inheritance in MCP, Workstation, ML, Qlib,
candle, and volume-verification child processes; stale owner-authority test setup; Binance checksum
MIME handling; registered-snapshot audit admission; and a Playwright race where three viewport
projects contended for one isolated real-backend writer lock. Every repair has a regression test or
is exercised by the applicable end-to-end gate. No critical or high finding remains open in the
local review. Independent PR review and exact-SHA GitHub checks remain publication gates.

## Public-surface coverage

| Surface | Acceptance class | Current evidence |
|---|---|---|
| Crypto acquisition, catalog, quality, feature, profile, asset-master, and snapshot CLI | Live bounded smokes plus offline fixtures/tamper tests | Passed |
| Governed research proposal, D0/D1/D2 contracts, revision checks, and snapshot binding | Deterministic lifecycle, denial tests, real case stopped before owner authority | Passed locally |
| Sandbox development, validation families, Monte Carlo, optimization, Qlib, Kronos, holdout fixture, and paper preflight | Deterministic supported fixture | Passed; paper preflight is truthfully `UNSUPPORTED_MULTI_VENUE_PAPER` |
| REST and SSE | Generated OpenAPI classification, real-backend Playwright, safe-error and denial tests | Passed |
| MCP | Manifest-derived capability matrix, read/draft fixtures, generic-owner-action denials | Passed |
| Guided and Advanced Workstation | 1280x720, 1440x900, and 1920x1080 Playwright; keyboard and accessibility | 83/83 passed with zero skips |
| Touch ID research actions | WebAuthn fixture/replay/state/action binding tests | Passed mechanically; real owner actions not performed |
| Broker/order routes | Denial and non-crediting preflight tests | Passed; no order or broker event created |

The generated capability/authority matrix remains the authoritative operation and tool inventory;
the browser and MCP do not gain authority from this report.

## Exact local gates

- Root lock/install, Ruff, format, 14 import contracts, and strict mypy over 579 source files:
  passed.
- Full non-network Python suite: **3,395 passed, 1 intentional skip, 7 network deselections**;
  **93.02%** owned-source coverage.
- Bias guards: **128 passed**.
- Live-network suite: **6 passed, 1 documented skip**.
- OpenAPI classification and generated OpenAPI/TypeScript freshness: passed.
- Frontend: 31 files / **166 tests**; 89.27% statements, 76.48% branches, 94.93%
  functions, and 91.81% lines; lint, generated API, production build, and npm audit passed.
- Playwright: **83 passed** across all three required viewports and reference-only performance;
  zero unintended skips.
- Literature worker: Ruff, format, mypy, lock, and **29 tests** passed.
- Qlib worker: Ruff, format, mypy, lock, and **14 tests** passed.
- All 13 wheels built, reinstalled without dependencies, imported, and asserted version `1.0.0`;
  the editable workspace was restored afterward.
- Expansion integrity: **372 manifests, 14 snapshots, 1 asset master, 13 research-eligible
  snapshots**, and no private paths exposed.
- Git diff check and full object verification passed; dangling objects are ordinary recoverable Git
  history, with zero corrupt or garbage objects.

## Current provider and owner checkpoints

The following are intentionally not converted into green software results:

1. **Literature:** the owner must provide the contact email that may be disclosed to Unpaywall.
   Search/acquisition can then produce lawful source bytes and anchored draft claims. Claim
   screening and pack freeze remain fresh Touch ID actions.
2. **QuantPad REST:** the Keychain credential currently returns `authentication_failed`. The owner
   must rotate `project-alpha-quantpad`, then run one new explicit bounded check. OAuth discovery
   does not substitute for REST readiness.
3. **IBKR:** Docker CLI is present, but the daemon/gateway is not running, no reviewed image digest
   or masked paper account is injected, and `127.0.0.1:4002` is unreachable. The owner must manually
   start and log into the reviewed paper gateway. ALPHA will not start Docker.
4. **Owner research decisions:** source screening, pack freeze, exploration approval, any eligible
   one-shot D2 launch, and final disposition each require a fresh owner assertion. The agent cannot
   perform or impersonate them.

CoinGecko and Tiingo explicit Keychain-backed checks are currently verified. Provider receipts are
redacted and content-addressed; their timestamps and limitations remain available through the
Readiness Center rather than being copied into this document.

## Publication gate

Do not open a ready PR or merge until the four checkpoints above are resolved as far as the honest
real case permits, the exact resulting SHA reruns all mandatory gates, independent review returns
ready, and GitHub checks are green. A real result of `SUPPORTED`, `CONTRADICTED`, `INCONCLUSIVE`, or
`INVALID` is acceptable. Profitability, promotion, paper readiness, or order activity is never a
required outcome.
