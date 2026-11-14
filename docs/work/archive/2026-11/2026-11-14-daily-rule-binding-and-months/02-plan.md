# Daily-rule approval binding gap, and the daily price reader over many months

**Delivery state:** Completed — owner agreed both changes on 2026-11-14; built, reviewed and verified on branch `m6/daily-rule-binding-and-months`, done when its pull request merges (filed under the archive because of the work-in-progress limit).
**Build class:** hard — approval-bound daily-rule files (protected tier), a new data read path (bias guard) and more than eight files.

Filed straight into the archive, as `2026-11-14-crypto-snapshot-duplicates` was: the
work-in-progress ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- Every program file the daily rule study runs through is now tied to your approval of that
  study; before, nine were not (three known, six found here). A test now fails if a new one
  appears untied without a written reason.
- A daily-rule study can now be drafted on a snapshot of many monthly Binance files (the kind on
  the Dell): name one stored copy per month. Missing, overlapping or repeated months, and other
  coins, are refused loudly. A one-month snapshot gives exactly the same result as before.
- Cost: every pending daily-rule approval stops verifying once and must be re-drafted and
  re-approved. None exists today (checked). Research-lane and synthetic-rule approvals are not
  affected.
- Not done here, for you to decide later: the `research` command file and the `alpha_research` /
  `alpha_validation` packages that the lane also touches are still not tied to daily approvals.

```json
{
  "schema_version": 1,
  "title": "Daily-rule approval binding gap, and the daily price reader over many months",
  "context": "The owner agreed on 2026-11-14 to close the daily-rule binding gap named in docs/roadmap/refactors/control-store-split.md and to let the daily price reader read multi-month crypto snapshots (ADR-0046). Both change daily-rule approval-bound files, so they ship together and invalidate pending daily-rule approvals once.",
  "assumptions": [
    {"statement": "DAILY_GUARD_FILES lists 25 flat alpha_cli files; rule_implementation_fingerprints binds them (plus worker files) by structural digest only when a daily study is given; synthetic rule approvals bind worker files only.", "verified_by": "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py lines 21-47 and 122-161"},
    {"statement": "Excluding TYPE_CHECKING imports, bound modules import nine unbound alpha_cli modules on daily paths: _control_schema (control_store top level), _native_daily_rule_history (control_store.daily_rule_history), _ml_observation_store (control_store W09 methods; writes job_events/jobs rows), _native_rule_economics (_native_loop_admission top level; validate_costed_result runs for daily studies; fixed_costed_study in _native_daily_rule_artifacts), _native_rule_study (top level of _native_rule_economics and _native_rule_protocol), job_capacity (control_store._create_job), paper_resources (control_store._validate_research_contract_for_approval), run_store (_artifacts and control_store._verified_run), run_context (_artifacts.write_manifest, called by daily artifacts).", "verified_by": "an AST walk of every bound file's alpha_cli imports, 2026-11-14, and reading each call site"},
    {"statement": "Each of the nine binds by structure (mode structure or structure-with-docstrings) under ADR-0045's automatic rule; none reads its own source or line numbers.", "verified_by": "_structural_digest.file_binding on each file"},
    {"statement": "All real crypto bars on the Dell are Binance monthly archives: raw receipts provider_schema binance-public-archive-v1, parser binance-archive-v1, request {family: klines, interval: 1d, market: spot, period: YYYY-MM, symbol}; one normalized manifest per month.", "verified_by": "reading /home/hunta/alpha-clean-base/data/crypto/manifests (1,426 archive raw receipts, no REST receipts)"},
    {"statement": "The RD-Agent worker probes read only rows from the query document, so the query document may gain a second schema without a worker change.", "verified_by": "workers/rdagent/rule_probe.py and costed_probe.py read query['rows'] only"},
    {"statement": "No control store exists in /home/hunta/alpha-clean-base/data or the default data folder, so no real daily-rule approval is pending.", "verified_by": "find /home/hunta/alpha-clean-base -name workstation.sqlite3 outside tmp/ returns nothing"},
    {"statement": "The current single-member query of the unit fixture (_publish then _query in tests/unit/test_crypto_price_snapshot_query.py) has content_sha256 4498ebb46eac2887ef11509ffd3cee7eb94804282f3e17ed1536d2da6294e3ca, stable across temporary directories.", "verified_by": "computed twice on origin/main f8f687c1"}
  ],
  "alternatives_considered": [
    "Bind only the three named files: rejected, _native_rule_economics.validate_costed_result runs in daily admission and would stay unbound; the one-time invalidation happens anyway.",
    "Bind every module reachable by any import: rejected, control_store's lazy imports reach most research lanes; those edges are reviewed and recorded instead.",
    "Resolve each month's manifest automatically with the ADR-0046 rule: rejected, a later honest recapture with a smaller id would change the query and break an approved study; names stay explicit, as today.",
    "Always emit a new document schema: rejected, the one-month result must stay byte-identical.",
    "Accept only REST captures over many months: rejected, no real data is REST; the reader would still read nothing on the Dell."
  ],
  "pre_mortem": [
    "A reviewed-outside exemption is wrong and lane behaviour stays unbound: each exemption names its call site and why the daily lane does not reach it; the reviewer checks each; a stale exemption fails the test.",
    "The multi-month path silently drops or double-counts a day at a month boundary: per-member ordering, a cross-member overlap refusal, the existing exact day-by-day coverage check, and boundary tests.",
    "The single-month document drifts: a pinned content hash from origin/main and all existing reader tests unchanged except the keyword rename.",
    "Archive acceptance opens a point-in-time hole: archive candles must sit inside their receipt's month, every receipt of a member must be fetched after each of its candles completed, and a bias guard poisons a later month."
  ],
  "slices": [
    {"title": "Bind the lane's control code; boundary and invalidation tests", "verify": "uv run pytest tests/unit/test_daily_guard_boundary.py tests/unit/test_daily_guard_binding.py tests/unit/test_native_launch_fingerprint_contracts.py tests/unit/test_structural_digest.py -q", "expected": "all pass; the boundary test fails on origin/main naming the nine unbound modules", "rollback": "revert the slice's commit", "status": "pending"},
    {"title": "Reader: many named months, archive receipts, V2 document", "verify": "uv run pytest tests/unit/test_crypto_price_snapshot_query.py tests/unit/test_crypto_price_snapshot_months.py tests/bias_guards/test_daily_price_months_future_poison.py -q", "expected": "all pass; the pinned single-month hash holds; multi-month tests fail on origin/main", "rollback": "revert the slice's commit", "status": "pending"},
    {"title": "Lane consumers: study, reopen, chart lineage, draft-daily", "verify": "uv run pytest tests/unit/test_native_daily_rule_study.py tests/unit/test_native_daily_rule_lifecycle.py tests/unit/test_native_daily_rule_artifacts.py tests/unit/test_native_daily_rule_admission.py tests/unit/test_daily_native_cli.py tests/unit/test_crypto_cloud_root_identity.py tests/unit/test_daily_rule_months_study.py tests/integration/test_daily_rule_report.py -q", "expected": "all pass", "rollback": "revert the slice's commit", "status": "pending"},
    {"title": "Documents and the read-only real-data proof", "verify": "uv run python scripts/roadmap_index.py --check", "expected": "index current; fs.py stale run by the orchestrator after the documents shows 0 stale", "rollback": "revert the documents", "status": "pending"}
  ],
  "tier_impact": ["protected", "bias", "determinism"],
  "docs_to_update": [
    "docs/adr/0045-approvals-bind-code-structure.md",
    "docs/adr/0047-daily-rule-lane-binding-and-named-months.md",
    "docs/adr/README.md",
    "docs/reference/invariants/cli-native.md",
    "docs/reference/invariants/cli-crypto-data.md",
    "docs/reference/project/components/data-layer.md",
    "docs/roadmap/refactors/control-store-split.md",
    "docs/roadmap/refactors/alpha-cli-subpackages.md",
    "docs/roadmap/capabilities.toml",
    "docs/reference/commands.md",
    "STATUS.md",
    "docs/roadmap/README.md"
  ],
  "out_of_scope": [
    "workers/rdagent/",
    "packages/alpha-research/src",
    "packages/alpha-validation/src",
    "apps/alpha-cli/src/alpha_cli/research_intake.py",
    "apps/alpha-cli/src/alpha_cli/research_runtime.py",
    "apps/alpha-cli/src/alpha_cli/research_crypto_data.py",
    "apps/alpha-cli/src/alpha_cli/research_crypto_runtime.py",
    "apps/alpha-cli/src/alpha_cli/_structural_digest.py",
    "apps/alpha-cli/src/alpha_cli/control_store.py",
    ".claude/code-size-baseline.json",
    "stored data under /home/hunta/alpha-clean-base/data",
    "approving or promoting anything"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py",
    "apps/alpha-cli/src/alpha_cli/crypto_price_snapshot_query.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_study.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_protocol.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_projection.py",
    "apps/alpha-cli/src/alpha_cli/daily_native_cmds.py",
    "apps/alpha-cli/src/alpha_cli/research_cmds.py",
    "tests/unit/test_daily_guard_boundary.py",
    "tests/unit/test_daily_guard_binding.py",
    "tests/unit/test_crypto_price_snapshot_query.py",
    "tests/unit/test_crypto_price_snapshot_months.py",
    "tests/unit/test_daily_rule_months_study.py",
    "tests/fixtures/daily_price_months.py",
    "tests/bias_guards/test_daily_price_months_future_poison.py",
    "tests/unit/test_native_daily_rule_study.py",
    "tests/unit/test_native_daily_rule_lifecycle.py",
    "tests/unit/test_native_daily_rule_artifacts.py",
    "tests/unit/test_native_daily_rule_admission.py",
    "tests/unit/test_daily_native_cli.py",
    "tests/unit/test_crypto_cloud_root_identity.py",
    "tests/unit/test_native_launch_fingerprint_contracts.py",
    "tests/unit/test_daily_native_dispatch_contracts.py",
    "tests/unit/test_daily_rule_recovery_contracts.py",
    "tests/unit/test_native_rule_authority.py",
    "tests/integration/test_daily_rule_report.py",
    "docs/adr/0045-approvals-bind-code-structure.md",
    "docs/adr/0047-daily-rule-lane-binding-and-named-months.md",
    "docs/adr/README.md",
    "docs/reference/invariants/cli-native.md",
    "docs/reference/invariants/cli-crypto-data.md",
    "docs/reference/project/components/data-layer.md",
    "docs/roadmap/refactors/control-store-split.md",
    "docs/roadmap/refactors/alpha-cli-subpackages.md",
    "docs/roadmap/capabilities.toml",
    "docs/reference/commands.md",
    "STATUS.md",
    "docs/roadmap/README.md",
    "docs/work/archive/2026-11/2026-11-14-daily-rule-binding-and-months/"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [command line native](../../../../reference/invariants/cli-native.md) | Approval fingerprints | always |
| [command line crypto data](../../../../reference/invariants/cli-crypto-data.md) | Read-only queries | slices 2 and 3 |
| [ADR-0045](../../../../adr/0045-approvals-bind-code-structure.md) | Decision: The digest | slice 1 |
| [ADR-0046](../../../../adr/0046-crypto-snapshot-members-are-content-addressed.md) | Decision | slice 2 |
| `apps/alpha-cli/src/alpha_cli/_native_rule_environment.py` | whole file | slice 1 |
| `apps/alpha-cli/src/alpha_cli/crypto_price_snapshot_query.py` | whole file | slice 2 |
| `tests/unit/test_crypto_price_snapshot_query.py` | `_store`, `_publish`, `_query`, `_full_discovery_fixture` | slice 2 |
| `tests/integration/test_crypto_snapshot_duplicates_cli.py` | the zipped month fixture (lines 55-80) | slice 2: synthetic archive months |
| `apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py` | `_fetch_binance` archive branch, lines 2380-2445 | slice 2: how an archive month is ingested |
| `apps/alpha-cli/src/alpha_cli/_native_daily_rule_study.py` | `DailyRuleStudyV1.exact_bindings`, `bind_daily_study` | slice 3 |
| `apps/alpha-cli/src/alpha_cli/_native_daily_rule_protocol.py` | `reopen_daily_study` | slice 3 |
| `apps/alpha-cli/src/alpha_cli/_native_daily_rule_projection.py` | `chart_snapshot` | slice 3 |

## Slices

The orchestrator writes the documents (slice 4); Codex builds slices 1-3 in one build. Never
edit `control_store.py`, `workers/rdagent/` or `.claude/code-size-baseline.json`. Size
ratchet (`tests/unit/test_code_size.py`): every new file stays under 1,500 lines and every new or
changed function at or under 150; a file already in the baseline (`research_cmds.py`, 3,539
lines) must keep exactly its line count, so its edit below is line-neutral.

### Slice 1 — bind the lane's control code

1. In `DAILY_GUARD_FILES` append, after `"daily_native_cmds.py"`, in this order:
   `"_control_schema.py"`, `"_native_daily_rule_history.py"`, `"_ml_observation_store.py"`,
   `"_native_rule_economics.py"`, `"_native_rule_study.py"`, `"job_capacity.py"`,
   `"paper_resources.py"`, `"run_store.py"`, `"run_context.py"` (25 to 34 names). No other
   change to that file.
2. New `tests/unit/test_daily_guard_boundary.py`. Its module docstring states the boundary:
   *every `alpha_cli` module that a bound module imports, at module level or inside a function,
   is itself bound or is listed in `REVIEWED_OUTSIDE` with the reason the daily lane does not
   run it; imports under `if TYPE_CHECKING:` do not count; packages below `alpha_cli` are
   outside this test (the costed rule profile binds alpha-core, alpha-patterns,
   alpha-strategies, alpha-backtest and alpha-data source bytes through `hashes.environment`);
   the worker side is bound by `WORKER_FILES`, `COSTED_FILES` and `daily_container_entry.py`.*
   - An AST helper returns, for one file, the set of `alpha_cli` module file names it imports:
     `from alpha_cli.X[.…] import …` and `import alpha_cli.X` give `X.py`; `from alpha_cli import
     a, b` gives each name that is a module file next to `_native_rule_environment.py`. Skip any
     statement nested in an `if` whose test is the name `TYPE_CHECKING` or an attribute
     `….TYPE_CHECKING` (its `else` branch still counts). A relative import, an `import importlib`,
     `from importlib import …`, or any call to `import_module` or `__import__` in a bound file
     fails the test (static tracing would be incomplete).
   - `REVIEWED_OUTSIDE: dict[tuple[str, str], str]`, keyed `(importer, imported)`, exactly these
     18 edges, each with a one-line reason naming the call site:
     `_artifacts.py → _native_tearsheet.py` (only `write_native_tearsheet` uses it; daily
     artifacts call `publish_artifact`, `run_dir`, `write_manifest`, `read_manifest`);
     `_ml_observation_store.py → ml_contract.py`, `_ml_observation_store.py → ml_native_plan.py`,
     `control_store.py → ml_native_plan.py` (W09 types; `_ml_observation_store._scope`, bound,
     refuses rule and native-owner records);
     `control_store.py → research_readiness.py` (only `record_research_decision`'s D2
     confirmation branch; the daily lane is D1 discovery only);
     `_native_fixture_store.py → _native_stock_launch.py`, `native_supervisor.py →
     _native_stock_launch.py` (type identity checks; a daily launch is `NativeLaunch`);
     `_native_rule_artifacts.py → _native_rule_projection.py` (synthetic branch; `publish_rule_run`
     returns through `publish_daily_rule_run` for daily contracts first);
     `_native_rule_environment.py → _structural_digest.py` (the digest binds its own bytes as
     `rules_sha256`);
     `control_store.py → _runner.py` (strategy candidate freeze and suite results);
     `control_store.py → research_crypto_binding.py`, `research_crypto_runtime.py`,
     `research_d1.py`, `research_crypto_d2.py`, `research_d2.py` (research-lane D0/D1/D2 evidence;
     rule contracts return earlier through `is_rule_contract`);
     `control_store.py → research_gate_packet.py` (strategy promotion packets);
     `control_store.py → study_semantic.py` (blind semantic resolver);
     `control_store.py → research_runtime.py` (`reserve_d0_research_launch` calls
     `validate_d0_pilot_contract`, which hands rule contracts to the bound
     `_native_rule_protocol.validate_rule_contract` first; research_runtime is bound by research
     approvals). If the AST helper finds a different edge set, stop and report it as a question.
   - Tests: every edge from a `.py` name in `DAILY_GUARD_FILES` goes to a bound name or a
     `REVIEWED_OUTSIDE` key (the failure lists the offending edges); every `REVIEWED_OUTSIDE` key
     is a live edge whose target is not bound (no stale exemption); every name in
     `DAILY_GUARD_FILES` is unique and is a regular, non-symlink file next to
     `_native_rule_environment.py`; the helper itself is checked on a small synthetic source
     (top-level, function-level, TYPE_CHECKING-only and `from alpha_cli import` forms).
3. New `tests/unit/test_daily_guard_binding.py`: copy every `DAILY_GUARD_FILES` file into a
   temporary directory, point `_native_rule_environment.__file__` at the copy of itself there
   (monkeypatch), stub `measure_rule_environment` to a fixed value, and pass a stand-in
   daily study (any object with `query_sha256`, cast for typing). For each of the nine new
   names, parametrised: (a) a pinned, real logic edit (one exact substring replaced exactly once,
   for example a numeric limit or a comparison operator; assert the substring occurs once)
   changes `rule_implementation_fingerprints(True, daily_study=…)["code"]`; (b) appending a
   comment line and inserting a blank line leaves it unchanged; (c) `file_binding` reports a
   structural mode (`structure` or `structure-with-docstrings`) for the real file. Also assert
   `_native_rule_environment.py` itself stays `bytes`.
4. Update any existing test that pins the 25-name list or count.

### Slice 2 — the reader over many named months

In `crypto_price_snapshot_query.py`:

- Keep `_SCHEMA`, `BinanceDailyPriceRowV1`, `BinanceDailyPriceSnapshotQueryV1` (fields and
  `to_dict` unchanged) and `validate_binance_daily_price_identity` (unchanged).
- Add `BinanceDailyPriceMemberV1` (frozen): `normalized_manifest_id`, `artifact_key`,
  `artifact_sha256`, `quality_method_version`, `observed_start`, `observed_end`,
  `source_receipts`. `to_dict` gives those keys with ISO times and `source_receipt_ids`
  (the receipts' ids, in order) instead of the receipts.
- Add `BinanceDailyPriceSnapshotQueryV2` (frozen): `snapshot_id`, `dataset`, `members` (tuple,
  canonical order), `start`, `end`, `available_by`, `rows`; property `source_receipts` = every
  member's receipts concatenated in member order; `content_sha256` as V1. `to_dict`: `schema`
  `"BinanceDailyPriceSnapshotQueryV2"`, `snapshot_id`, `dataset`, `dataset_sha256`, `members`,
  `source_receipts` (full receipt dicts, member order), then exactly V1's remaining keys and
  literal values (`start`, `end_exclusive`, `available_by`, `requested_row_count`,
  `returned_row_count`, `coverage`, `availability_basis`, `availability_semantics`,
  `raw_capture_after_available_by`, `point_in_time_claim`, `claim_scope`, `execution_authority`,
  `rows`).
- `query_binance_daily_price_snapshot(snapshot, store, *, normalized_manifest_ids, start, end,
  available_by)` replaces the `normalized_manifest_id` keyword. It returns V1 when one id is
  named and V2 when two or more are. Fail loud (`DataError`) in this order:
  1. `normalized_manifest_ids` is a `tuple` or `list` (a `str` is refused) of 1 to 200 lowercase
     SHA-256 strings, all distinct ("names a normalized manifest more than once").
  2. The existing `start`/`end`/`available_by` checks, unchanged.
  3. `store.verify_readable()`, then one `metadata_inventory()`.
  4. Per id: exactly one inventory entry with that `manifest_id` and `artifact_kind`
     `normalized`; the snapshot members with that entry's `artifact_key` and `artifact_sha256`
     must be exactly one; validate that member's dataset with
     `validate_binance_daily_price_identity` (so a forged member still fails "exact Binance");
     then require the entry's `dataset` equal to it (else the existing "binding differs"
     message). Two ids binding one member, or named members of different datasets, are refused.
  5. Per member: `_sources` and `_frame` as today, with the 8 MiB raw ceiling and 32 MiB
     normalized ceiling counted across all members together (raw size preflight of every member
     before any raw hashing, as today); quality method version in
     `snapshot.qualification_versions`.
  6. Order members by observed start; each member's observed end must be strictly before the
     next member's observed start ("price query members overlap"). Each named member must
     contribute at least one row inside `[start, end)` ("lies outside the requested range").
  7. Every other snapshot member with the same dataset must not overlap `[start, end)`: find its
     retained normalized manifests in the inventory (same dataset, key, hash; at least one, all
     with equal non-null observed ranges, else refuse) and refuse when its closed observed range
     meets `[start, end)` ("is not named"). Members of other datasets are ignored.
  8. Row checks exactly as today, per member: strict order, Binance close clock, numeric and OHLCV
     invariants, completed-day filter, every receipt of that member fetched at or after each of
     its candles' completion, and the candle inside one of that member's receipts' bounds. Then
     the existing exact day-by-day coverage check over all rows.
- `_sources` accepts, per raw receipt, either the existing REST rule unchanged, or the archive
  rule: `provider_schema == "binance-public-archive-v1"`, `parser_version ==
  "binance-archive-v1"`, request keys exactly `family`, `interval`, `market`, `period`, `symbol`
  with `klines`, `1d`, `spot`, `YYYY-MM` (month 01-12), the dataset instrument. An archive
  receipt bounds a candle when the candle's UTC year-month equals its `period`. Anything else
  keeps the existing "identity/schema differs" refusal.
- Tests. Rename the keyword in `tests/unit/test_crypto_price_snapshot_query.py` (only that; every
  assertion stays) and add a test pinning
  `_query(*_publish(store)).content_sha256 == "4498ebb46eac2887ef11509ffd3cee7eb94804282f3e17ed1536d2da6294e3ca"`
  and the V1 document key list. New `tests/fixtures/daily_price_months.py`: synthetic Binance
  monthly archive months (zipped CSV as in the duplicates CLI test, ingested like
  `crypto_data_cmds` does) for any instrument, plus snapshot creation. New
  `tests/unit/test_crypto_price_snapshot_months.py`: three and thirty-six months give contiguous
  rows identical to the per-month rows; caller order of ids does not change the document; a
  range starting and ending inside months, and at exact month boundaries (31 Jan to 1 Feb,
  29 Feb 2020, 31 Dec to 1 Jan); overlap (two members sharing a day, and a REST capture covering
  an archive month) refused; a missing month inside the range refused (as unnamed when in the
  snapshot, as incomplete coverage when absent); a duplicate id and two ids for one member
  refused; a named member outside the range refused; BTC and ETH months in one snapshot: naming
  the BTC months works and ignores ETH, naming an ETH month fails "exact Binance"; a forged
  archive request (daily `period`, wrong symbol, extra key) refused; a candle outside its
  receipt's month refused; aggregate raw ceiling refused before any payload hashing; the V2
  document deterministic across two stores.
- New bias guard `tests/bias_guards/test_daily_price_months_future_poison.py`: a January-March
  snapshot and a twin whose March month has poisoned prices; a January-February query (ids for
  January and February, `available_by` 1 March) returns identical rows from both; a February
  receipt fetched before 29 February's candle completed is refused.

### Slice 3 — the lane's consumers

- `_native_daily_rule_study.py`: `exact_bindings` accepts query schema V1 or V2. Shared checks
  unchanged. Receipts may be REST (`binance-public-rest-v1`, `binance-archive-rest-v1`) or
  archive (`binance-public-archive-v1`, `binance-archive-v1`); still 1 to 100 receipts. For V2:
  `members` is a list of 2 to 100 objects with exactly the V2 member keys, distinct lowercase
  SHA-256 manifest ids, observed ranges strictly increasing, and the members' `source_receipt_ids`
  concatenated equal the receipts' ids in order. Keep the function under 150 lines (move the V2
  checks to a helper). `bind_daily_study` accepts either typed query class.
- `_native_daily_rule_protocol.reopen_daily_study`: pass `normalized_manifest_ids` from the
  frozen document (V1: its one id; V2: the members' ids in order). Nothing else changes.
- `_native_daily_rule_projection.chart_snapshot`: V1 lineage unchanged. For V2 the lineage
  `schema` is `"DailyRuleChartLineageV2"` and `normalized_manifest_id` /
  `normalized_artifact_sha256` are replaced by `normalized_members`, a list of
  `{"normalized_manifest_id", "normalized_artifact_sha256"}` in member order; all other keys and
  values as V1.
- `daily_native_cmds.draft_daily_request(..., normalized_manifest_ids: Sequence[str])` passes them
  through as a tuple. `research_cmds.draft_daily`, line-neutral: the parameter line becomes
  `normalized_manifest_id: list[str] = typer.Option(...),  # noqa: B008` (same flag, now
  repeatable, one per month member) and the call passes
  `normalized_manifest_ids=tuple(normalized_manifest_id),`; no other line in that file changes.
- Rename the keyword in the existing daily tests listed in `files` (no assertion changes). New
  `tests/unit/test_daily_rule_months_study.py`: a 2020-2022 study bound from a thirty-six-month
  archive snapshot validates, `reopen_daily_study` reproduces it from a restored copy of the
  store, its chart lineage is V2, and tampering with one member id, one receipt id or the member
  order in the frozen document is refused; plus one `draft-daily` CLI call with two
  `--normalized-manifest-id` options reaching `draft_daily_request` with both ids.

## Test plan

Each new behaviour gets a test that fails on `origin/main` first (boundary test, multi-month
reader, archive receipts, V2 study). Existing tests keep every assertion; only the keyword
`normalized_manifest_id=` becomes `normalized_manifest_ids=(…,)`. The pinned hash proves the
one-month output is byte-identical. The orchestrator runs `gate.py check`, the slice commands,
the mutation sweep's fast tier, and a read-only proof on a copy of the Dell data folder (a
thirty-six-month BTCUSDT 2020-2022 snapshot queried end to end), recorded in `04-verify.md`.

## Look-ahead, determinism and import impact

No row is returned before its completed day; per-member receipts must postdate each candle's
completion; a later month never enters an earlier range (bias guard). Members are put in
canonical order, so the document does not depend on the caller's order. No new import edges
between packages; the reader still imports only `alpha_core` and `alpha_data`. Approval impact:
`_native_rule_environment.py` (bound by bytes) and several bound files change, so every daily
rule approval's `code` hash changes once; synthetic rule approvals and research approvals do not.
