# Split control_store.py behind the unchanged ControlStore facade

**Risk:** H

## Scope

`apps/alpha-cli/src/alpha_cli/control_store.py`: 14,025 lines (measured with `ast`, 2026-11-14,
main at `89c7706c`). One class, `ControlStore` (lines 2014-13976, 11,963 lines, 221 methods, 95
public), 64 module-level functions, 84 module constants and 19 type aliases. Schema version 7;
DDL lives in `_control_schema.py`. 18 of its methods are over the 150-line limit
(`.claude/code-size-baseline.json`). Ten commits touched it between 2026-10-15 and 2026-11-14.

| Section | Lines | What |
|---|---|---|
| imports, aliases, constants | 1-516 | enums, transition tables, D0/D1 budgets |
| generic helpers | 519-907 | text, uuid, time, content ids, semantic identity, paging |
| backups, schema, migrations | 910-1794 | `_verified_v*_backup`, `_migrate_schema_v1`-`v6`, schema checks |
| research and budget helpers | 1797-2011 | `_enum_value`, D1 budget and spec, D2 topology, `_enable_wal` |
| `ControlStore` | 2014-13976 | the areas below |
| `__all__` | 13979-14025 | 45 names |

`ControlStore` falls into contiguous areas (method lines; public methods in brackets):

| Area | Lines | Methods | Calls into | Called from |
|---|---|---|---|---|
| A connection and transactions | 285 | 7 (0) | none | 12 areas |
| B research-contract lookups, ledger appends, approval validation | 457 | 12 (0) | none | G, J, H, K, F, D, I, M, L |
| C run and evidence gate verification | 721 | 17 (0) | H once | L, J, M, N, E, K, G, I |
| D projects, case capture, gate overrides | 594 | 11 (7) | A, B | L |
| E Monte Carlo review | 170 | 4 (2) | A, C, L | L |
| F literature, sources, PDFs, claims, source packs | 1,324 | 27 (19) | A, two B views | K once |
| G contract lifecycle and phase transitions | 743 | 7 (7) | B (35 calls) | M, I |
| H D0/D1 launch reservations, daily rule history | 496 | 11 (7) | B | M, C, I |
| I semantic events, Touch ID authorisation | 963 | 15 (8) | A, B, C, H | G, O |
| J attempts, decisions, early close, case summary | 867 | 6 (6) | B, C | M |
| K context packets, notes, datasets, briefs, gate inputs | 1,309 | 25 (14) | B, C | F, N |
| L strategy versions, experiments, stages, holdout, decision packets | 1,953 | 30 (14) | A, C, D, B | D, E, K |
| M jobs, cancellation, native fixture, W09 | 680 | 28 (20) | A, C, B | G, H, J, L |
| N evidence | 707 | 13 (4) | A, C | K once |
| O owner enrolment and auth | 419 | 8 (8) | A, one I helper | none |

The shared core is A, B and C (about 1,460 lines); O, F, N, E and the native-fixture part of M are
nearly self-contained. The split pattern already exists: `claim_native_fixture` and W09 delegate
with a lazy import to `_native_fixture_store` and `_ml_observation_store` (`claim(self, ...)`).

## Why

A 14,000-line class cannot be held in one reading; it is the most likely merge-conflict site for
the 34 waiting features, and its 18 oversized methods hold 3,599 of the 21,389 lines in the size baseline's function list.

## The interface that must not change

- 123 import statements in 108 files (24 product files). Names: `ControlStore` (89 files),
  `research_case_revision` (12), `StageState`, `parse_timestamp`, enum aliases, `DATABASE_NAME`,
  `SCHEMA_VERSION`; private names imported by product code: `_at`, `_canonical_json`,
  `_d1_native_spec`, `_d1_native_budget`, `_content_id`, `_canonical_uuid`, `_required_text`,
  `_research_review_state`, `_MAX_OWNER_PDF_BYTES`. All stay importable from `control_store`.
- Tests: 38 files make 160 calls to private methods (`_transaction` 107); 17 files monkeypatch
  internals. Six module-attribute patches (`_SCHEMA_V2`, `_SCHEMA_V5`, `_execute_static_sql_script`,
  `_logical_database_fingerprint`, `_verified_v1_backup`, `time`) only work while the code that reads
  those names stays in `control_store`'s namespace: moving that code silently disarms the patch.
- Behaviour: schema migrations from every recorded version, the append-only owner-event ledger and
  its triggers, transaction boundaries, stored row bytes and canonical JSON.

## Approvals: what a split invalidates

- `control_store.py` is one of the 40 `DAILY_GUARD_FILES` (`_native_rule_environment.py:21`),
  bound by structure (ADR-0045; it reports mode `structure`, so comments and docstrings are free).
  Any move of code out of it changes its digest: **every pending daily-rule approval is invalidated
  once**. Research-lane approvals are not affected (control_store is not in the research hash).
- Code moved to a new module is no longer covered by that binding, which hashes only the listed
  flat file names (`Path(__file__).with_name(name)`; a subpackage path raises). Each new module must
  be added to `DAILY_GUARD_FILES`, an edit to `_native_rule_environment.py`, which is itself bound
  by exact bytes. That edit also invalidates every daily-rule approval.
- The earlier gap (`_control_schema.py`, `_ml_observation_store.py`,
  `_native_daily_rule_history.py` and twelve more files the lane runs through) was closed on
  2026-11-14 ([ADR-0047](../../adr/0047-daily-rule-lane-binding-and-named-months.md)).
  `tests/unit/test_daily_guard_boundary.py` now fails when a bound module imports an unbound
  `alpha_cli` module without a reviewed reason, so every module this split creates must be added
  to `DAILY_GUARD_FILES` in the same change (the test enforces it).

## Plan: small steps, each its own pull request

0. **Owner decision (prerequisite).** Confirm the one-time renewal of daily-rule approvals, and
   choose the binding: list each new `_control_*.py` module in `DAILY_GUARD_FILES` in the same
   change that creates them (the three formerly uncovered modules are bound since ADR-0047). Without this, stop after step 1.
1. **Characterisation, no product change.** A public-API snapshot test (every `ControlStore`
   public method name and signature, `__all__`, the private names product code imports); a test
   that each of the six patched module attributes is still read through `control_store`.
   Migration tests from versions 1-6 already exist in `tests/unit/test_research_control_store.py`.
2. **Module helpers out** (519-907 and 1797-2011, about 600 lines) to `_control_values.py`,
   re-exported from `control_store` so the seven bound importers keep their import lines. Proof: the
   step 1 tests, `gate.py check --all`, smoke. Invalidates daily approvals (with step 0's edit).
3. **Schema and migrations out** (910-1794, about 880 lines) to `_control_migrations.py`; move the
   six patch targets' tests to patch the new module in the same change (step 1's test fails until
   they do). Proof: migration tests from every version, the backup tests.
4. **Self-contained areas, one per change, delegating like `claim_native_fixture`:** O owner auth,
   F literature, N evidence, E Monte Carlo, M native fixture and W09. The facade keeps each public
   method as a one-line delegate with the same signature. Proof: the API snapshot, the area's tests,
   the ledger append-only tests for O.
5. **The core-dependent areas last** (G, H, I, J, K, L), after A, B and C sit in
   `_control_core.py` with the transaction and append helpers. Split oversized methods while moving
   them (validation prefix, SQL block, projection: see `oversized-functions.md`).

Each step after 1 changes `control_store.py` and so the daily-rule binding; batching steps 2-5 into
one short window costs the owner one renewal instead of several. Target: a facade under 1,500 lines
and no method over 150 lines.

## Recommendation

Do steps 0-1 now, and steps 2-5 as one planned campaign before the feature backlog starts touching
the store, in a window the owner picks when no daily-rule approval is pending. Ten commits a month
already touch the file, and each behavioural change invalidates the same approvals anyway; splitting
first means one renewal and smaller conflicts for every later feature. Splitting piecemeal as
features touch areas would spread the renewals and leave the facade half-split for months.
