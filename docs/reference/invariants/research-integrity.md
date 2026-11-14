---
owner: research integrity
sources:
  - packages/alpha-data/src/alpha_data/pit.py
  - packages/alpha-backtest/src/alpha_backtest/feed.py
  - apps/alpha-cli/src/alpha_cli/_identity.py
  - apps/alpha-cli/src/alpha_cli/_seeds.py
  - apps/alpha-cli/src/alpha_cli/owner_auth.py
  - scripts/claude_hooks.py
  - tests/bias_guards/**
  - tests/oracles/**
verified: cc2e29fdba53
---

# Research integrity

The project-wide rules that keep ALPHA's research honest. They apply in every area; area files
add the mechanics and link back here. Weakening any of these needs an owner decision recorded in
an ADR, never a quiet code change.

## Point-in-time reads

- Every data or strategy read goes through a point-in-time `as_of` accessor with a timezone-aware
  UTC cutoff — a result must only use what was knowable at that moment.
  [ADR-0005](../../adr/0005-point-in-time-firewall.md)
- Every data or strategy unit gets a `@pytest.mark.bias_guard` future-poison test: corrupt the data
  after the cutoff and prove the output does not change. Each guard has a must-fail leaky twin, so a
  guard that tests nothing is itself caught. Pattern: `tests/bias_guards/test_future_poison_pattern.py`.
- Universe membership and survivorship are point-in-time too: a symbol is only in the universe on
  dates it was listed. `tests/bias_guards/test_survivorship.py`.
- Never add a bias guard without its leaky control, and never delete or loosen an existing guard.
- Provider, venue, market type, unit and quote currency are part of a dataset's identity. No fallback or
  join may silently swap one for another ([data § Crypto identity and features](data.md#crypto-identity-and-features)).
- The query-level contracts for these reads are in the
  [research platform contracts](../../operations/research-platform-contracts.md).

## Decide at close, fill at next open

- A decision uses bar `t` up to and including its close; the order fills at the open of bar `t+1`.
  This is modelled in the execution feed, not assumed away.
  [ADR-0003](../../adr/0003-t+1-fill-encoding.md)
- Signals use trailing windows only. A same-bar fill or a centred window is a look-ahead bug.

## Corporate actions: two clocks

- A corporate action has a knowledge time (when it became known) and an application time (ex-date
  or pay date). Knowledge time gates visibility; ex-date gates split application.
  [ADR-0004](../../adr/0004-two-clock-corporate-actions.md)
- Dividends are separate cash events credited at `pay_date`, not price adjustments.

## Invalid data fails loud

- Raise a typed error (`DataError`, `LookAheadError`, both `AlphaError`) with context on gaps,
  NaN or infinite values, out-of-order timestamps, or degenerate statistics. Never return a silent
  default or an empty result in their place.
- A degenerate (flat, zero-variance) series gives a clean, explained FAIL, never an undefined number.
- Code-level rules (no empty `except`, no swallowed errors) are in
  [engineering § Errors](engineering.md#errors).

## Immutable, hash-bound artefacts

- Completed runs, data snapshots, receipts and admitted evidence are immutable. Every artefact's
  hash, size and row count is pinned in a manifest. Never edit one in place; write a new one.
  [ADR-0013](../../adr/0013-run-identity-v3-and-causal-artifacts.md)
- Keep readers and migrations for every stored format. Old results must stay readable.
- Re-verify bytes on read and on copy. Retirement and retries preserve the original bytes.
- Workflow state (projects, jobs, decisions) lives in the CLI's SQLite control store, never written
  into an immutable manifest. [ADR-0014](../../adr/0014-cli-owned-development-control-plane.md)

## Deterministic seeds and identity

- A run's identity hashes its normalised config, data snapshot, seed and the source fingerprint of
  the code that ran. The same inputs give the same run id and the same bytes.
  [ADR-0007](../../adr/0007-deterministic-run-id-and-seeds.md)
- Seeds come from named semantic namespaces, so results do not depend on the order things run in.
- Seeds for the D0 (synthetic pilot) and D1 (registered discovery) research tiers are frozen in
  code, never derived from user settings.
- Machine-local paths, caches and wall-clock times never enter a run id or manifest.
  `uv run python scripts/gate.py determinism` reruns the determinism tests under a perturbed hash
  seed and timezone.

## Research before strategy

- Research comes first and is finite. Every new project gets a governed Research Case; no strategy
  version can bypass its approved confirmation contract.
  [ADR-0019](../../adr/0019-governed-research-cases-before-strategy-development.md)
- Tiers: D0 = synthetic pilot; D1 = registered discovery (discovery only); D2 = one-shot
  confirmation on sealed data, approved by the owner; D3 = the final holdout, never used by research.
  [ADR-0027](../../adr/0027-tiered-research-readiness-semantics.md)
- Promotion to strategy work needs verified evidence and an owner decision. Never infer either.
- Intraday research cannot become daily validation evidence.
  [ADR-0020](../../adr/0020-intraday-event-research-is-not-daily-validation-evidence.md)
- Automated research and self-repair keep every attempt. A same-specification mechanical repair
  stays on the same attempt line; a changed hypothesis, parameter or data choice is new, metered
  research with its own selection and exposure cost, never a clean retry. Neither gives trading authority.

## Statistical evidence

- A backtest is believable only after the validation gauntlet: walk-forward out-of-sample,
  randomized-price nulls, bootstrap confidence intervals, Deflated Sharpe and CPCV. All gates must
  pass. [ADR-0006](../../adr/0006-two-tier-null-model.md)
- Screening results and Monte Carlo path risk are not proof of an edge. Path-risk families report
  independently; there is no majority vote.
  [ADR-0029](../../adr/0029-four-family-monte-carlo-validation.md)
- Every public statistical primitive must be wrong-detectable: an oracle in `tests/oracles/`
  (metamorphic relation, known-truth calibration, or differential check) and a primary-source
  citation in its docstring.
- Never compare floats with `==` in tests; tolerances come from documented statistical bounds.
- A null or permutation test asks whether any edge exists; it is not a feature-importance measure.
  Complexity or a presumed market inefficiency is not evidence of an edge, and compute or job
  capacity is not trading capacity.
- Every tried variant counts: failed, rejected and pruned trials stay in the ordered trial ledger
  (`apps/alpha-cli/src/alpha_cli/_optim.py`). Renaming or re-splitting periods that were already
  inspected never makes them untouched.
- Passing numerical checks gives no research authority by itself.
- Quant work cites primary sources. Edition, licence and page anchors follow the
  [finance-math evidence guide](../../operations/finance-math-evidence.md); book metadata is not book text,
  not governed evidence and not an ingestion.

## Models and isolated workers

- Forecasting-model runs label training-period overlap (`pretrain`), warn loudly, and split metrics
  before and after the model's training cutoff. Leakage is labelled, never silent.
  [ADR-0009](../../adr/0009-forecast-leakage-and-tier2-cost-policy.md)
- Qlib runs only in its isolated worker. Its predictions must pass contract and future-leakage
  checks, and ALPHA's own replay is the authority; worker diagnostics are advisory.
  [ADR-0016](../../adr/0016-isolated-qlib-worker.md)
- External integrations must prove their value first.
  [ADR-0011](../../adr/0011-evidence-gated-external-integrations.md)
- Prefer pinned upstream Qlib, RD-Agent and NautilusTrader capabilities to writing equivalents, but an
  upstream example, demo, default (such as a default fill model) or diagnostic is never ALPHA acceptance.
  ALPHA keeps its clocks, fills, costs, accounting, trial records, provenance and canonical replay.

## Owner authority

- Only the owner approves, decides, promotes or reveals a holdout. Agents, the web app, the MCP
  server, model output, broker or account state and passing checks never carry that authority, and
  approvals are never inferred — not from silence, a past approval, or a green check.
- Owner authority flows only through the existing bounded owner-auth actions
  (`apps/alpha-cli/src/alpha_cli/owner_auth.py`); never add another path. Which surface may do what is
  listed in the generated [capability authority matrix](../../governance/capability-authority-matrix.md).
- Owner actions need explicit local confirmation: an expiring, one-use token bound to the action,
  project, artefact, case revision, consequence and reason. It records local intent, not proof of
  human presence. [ADR-0038](../../adr/0038-local-confirmation-and-terminal-archive-charts.md)
- Agent tools must never call the owner-action routes or start owner credential ceremonies; the
  `pre-owner-action-guard` hook in `scripts/claude_hooks.py` blocks them. Do not weaken it.
- Drafts and advisory output (Codex, assistants, evaluations) confer no authority. Drift or
  monitoring alerts never trigger an automatic refit, promotion or trade.

## No live capital

- No code path places live-capital orders. Crypto execution is the local Sandbox only; IBKR is a
  paper account only, with explicit opt-in flags that default to off.
  [ADR-0017](../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)
- Paper sessions are operational records, not research runs; they never become validation evidence.
  [ADR-0012](../../adr/0012-operational-paper-sessions.md)

## Protected and hidden tests

- There is no hidden test suite ([ADR-0041](../../adr/0041-no-hidden-test-suite.md)); acceptance
  tests are visible in `tests/acceptance/`. The path `tests/holdout/` stays guarded: never read,
  edit or write it.
- `tests/bias_guards/`, `tests/oracles/` and the harness tests are protected: change them only in
  a reviewed pull request, and never to make a failing change pass.
- Owner data, credentials and hidden tests are never inputs to search or discovery indexes.
