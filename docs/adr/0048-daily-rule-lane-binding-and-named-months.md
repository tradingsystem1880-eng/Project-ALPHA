# ADR-0048: Daily-rule approvals bind every module the lane runs through; the daily price query reads named months

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** Project ALPHA owner (both changes, 2026-11-14) and AI build agents (the mechanism)

## Context

A daily-rule owner approval freezes `hashes.code`, the structural digest
([ADR-0045](0045-approvals-bind-code-structure.md)) of the worker files and of the `alpha_cli`
files named in `DAILY_GUARD_FILES` (`_native_rule_environment.py`). The list was written by hand.
Tracing the imports of the listed files on 2026-11-14 found fifteen `alpha_cli` files that the
lane loads or runs and that no approval bound: the three the
[control-store split plan](../roadmap/refactors/control-store-split.md) already named
(`_control_schema.py`, `_native_daily_rule_history.py`, `_ml_observation_store.py`), six found
while planning (`_native_rule_economics.py`, whose `validate_costed_result` runs at daily
admission; `_native_rule_study.py`; `job_capacity.py`; `paper_resources.py`; `run_store.py`;
`run_context.py`), and six found by the independent review (`_native_tearsheet.py`, which daily
artifacts run through `_artifacts.write_run_sidecars`; `research_readiness.py`, imported at
`control_store.py`'s module level; `research_runtime.py`, imported by the D0 launch reservation
the daily pilot uses; `_native_stock_launch.py` and `native_stock_fixture.py`, imported for type
checks on every daily launch; and the package `__init__.py`). A change to any of them could change
what an approved study does while its approval stayed valid: the dangerous failure.

Separately, a governed crypto snapshot may hold many months of many coins
([ADR-0046](0046-crypto-snapshot-members-are-content-addressed.md)), but the daily price query
(`crypto_price_snapshot_query.py`) required exactly one member and accepted only Binance REST
captures. Every real crypto bar on the Dell is a Binance monthly archive, one normalized manifest
per month, so no daily-rule study could be drafted on real data.

Both changes edit approval-bound files; doing them in one change invalidates pending daily-rule
approvals once.

## Decision

### The binding boundary

- `DAILY_GUARD_FILES` adds the fifteen files (25 to 40). They bind under ADR-0045's automatic
  rule: thirteen by structure; `_native_stock_launch.py` and `native_stock_fixture.py`, which read
  their own file paths, by bytes (any edit to them invalidates); `_native_rule_environment.py`
  itself stays bound by its bytes.
- **Rule:** every `alpha_cli` module that a bound module imports, at module level or inside a
  function, is bound, or is listed with a reason in
  `tests/unit/test_daily_guard_boundary.py::REVIEWED_OUTSIDE` as an `(importer, imported)` edge the
  daily lane does not run (for example research-lane evidence checks that rule contracts leave
  before reaching, or W09 types). An exemption is valid only when the import statement itself
  never executes on a daily path, because importing runs the imported module's top level. Imports
  under `if TYPE_CHECKING:` do not count; any `alpha_cli` import also runs the bound package
  `__init__.py`; an import of a subpackage cannot be traced and fails the test. A bound module
  may not import dynamically or relatively. A listed edge that no longer exists fails the test, so
  the list cannot rot.
- **Outside the rule, an open owner decision:** packages below `alpha_cli`. The costed rule
  profile binds the source bytes of alpha-core, alpha-patterns, alpha-strategies, alpha-backtest
  and alpha-data through `hashes.environment`. `alpha_research` and `alpha_validation` are not
  bound by daily approvals although the lane loads them (`_native_rule_protocol.py`,
  `_native_rule_study.py`, `_artifacts.py`) and runs some of their code: the daily run's tearsheet
  files come from `alpha_validation.native_tearsheet`. Nor is the command module
  `research_cmds.py`, which dispatches into the lane (draft, the pilot with its drift check, the
  deep run). Binding them would make every behavioural edit to those large shared modules
  invalidate daily-rule approvals; with no daily-rule approval existing on 2026-11-14, deciding
  later costs nothing extra today.

### The daily price query reads named months

- The caller names one retained normalized manifest per month member
  (`normalized_manifest_ids`; `alpha research draft-daily --normalized-manifest-id`, repeatable).
  Names stay explicit, as before: resolving each member with the ADR-0046 rule would let a later
  honest recapture with a smaller id change the query of an already approved study.
- One name gives exactly the previous `BinanceDailyPriceSnapshotQueryV1` document (pinned by a
  content hash in the tests). Two or more give `BinanceDailyPriceSnapshotQueryV2`: the shared
  fields with the same values, plus `members` (each manifest id, artifact key and hash, quality
  version, observed range and receipt ids) in canonical observed-start order, so the caller's order
  does not matter.
- Refused, loudly: a name given twice or two names for one member; members of different datasets
  or not the exact Binance BTCUSDT spot daily identity; members that overlap; a named member with
  no day in the range; a snapshot member of the same dataset whose observed range meets the range
  but is not named; any missing day (the existing day-by-day coverage check). Members of other
  coins in the snapshot are ignored. The 8 MiB raw and 32 MiB normalized ceilings apply to the
  whole query.
- Point in time, per member: every raw receipt of a member must have been fetched after each of
  its candles completed, and each candle must lie inside one of its member's receipts. A Binance
  monthly archive receipt (`binance-public-archive-v1`, parser `binance-archive-v1`, request
  exactly `family=klines`, `interval=1d`, `market=spot`, `period=YYYY-MM`, the instrument) bounds
  the candles of its month; the REST rule is unchanged. Mixed archive-and-REST captures and daily
  archive files are still refused.
- The daily study accepts either document; its chart lineage for a V2 query is
  `DailyRuleChartLineageV2`, listing every member. The RD-Agent worker reads only rows and is
  unchanged.

## Consequences

- **Every pending daily-rule approval is invalidated once** and must be re-drafted and
  re-approved by the owner. On 2026-11-14 none existed: the default data folder has no control
  store, and the Dell's data folder's control store (created that evening by another session)
  holds one generic research contract, not a daily-rule one, with no review events. Synthetic fixed-rule approvals bind only worker files and
  research approvals bind the `alpha_research` tree and four research modules, none of which
  change, so they stay valid.
- Later edits that change behaviour in any of the fifteen files now invalidate daily-rule
  approvals, as edits to `control_store.py` already did; comments and formatting stay free
  (except for the two byte-bound files). `research_runtime.py` edits now invalidate both research
  and daily-rule approvals.
- The daily query no longer refuses a snapshot just because it holds other members: members of
  other coins are ignored (the snapshot id still binds them); same-coin members are checked.
- A multi-year daily-rule study can be drafted on monthly Binance archives; a read-only proof on a
  copy of the Dell's data folder is recorded in
  `docs/work/archive/2026-11/2026-11-14-daily-rule-binding-and-months/04-verify.md`.

Tests: `tests/unit/test_daily_guard_boundary.py`, `tests/unit/test_daily_guard_binding.py`,
`tests/unit/test_crypto_price_snapshot_months.py`, `tests/unit/test_daily_rule_months_study.py`,
`tests/bias_guards/test_daily_price_months_future_poison.py`.
