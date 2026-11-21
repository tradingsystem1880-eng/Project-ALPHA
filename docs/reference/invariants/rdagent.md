---
owner: isolated workers
sources:
  - workers/rdagent/**
  - apps/alpha-cli/src/alpha_cli/_native_rule_environment.py
  - scripts/gate_components.py
verified: 9caaba5ecf2b6203
---

# RD-Agent worker invariants

Rules for the pinned RD-Agent worker in `workers/rdagent/`. The other workers are in [workers.md](workers.md).

## Boundary and authority

- Funding inputs and eligibility: [funding policy](../../../workers/rdagent/judge-rules.md#futures-funding); thirds and ties:
  [rule and do-not-change list](../../../workers/rdagent/judge-rules.md#thirds-and-ties).
- A development-only probe of pinned RD-Agent native loops on fixed synthetic inputs, plus the ALPHA-judged factor
  loop below. It has no public research command or production route, and no ALPHA package imports it. Every result stays synthetic,
  `not_admitted`; no scientific run id or completed D1 attempt is invented.
- Upstream source stays external at commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`; point
  `ALPHA_RDAGENT_SOURCE` at a byte-identical `rdagent/` copy. `source_pin.py` verifies the tree digest before
  any upstream import, and the source root is never put on `sys.path`. Never vendor upstream code here.
- The native fixture loop (`native_fixture.py::NativeFixtureLoop`) is a `LoopMeta` subclass of upstream
  `LoopBase` that never overrides `run`, `_run_step`, `dump` or `load`, so upstream's own loop drives it.
  Every executed stage is charged to the fixture owner; interrupted work stays charged (`conformance.py`).
- There is no gate component or CI job (`scripts/gate_components.py` lists none). Its checks are root tests
  `test_native_loop_conformance.py` and other source-dependent tests skip without `ALPHA_RDAGENT_SOURCE`; skips confer no qualification.
- Its audit hooks and sanitised subprocesses contain trusted fixture mistakes, not hostile code or same-user access.

## Install and runtimes

- The project is `package = false` with its own `uv.lock`, a focused import subset, not upstream's full
  environment. Rule and economics profiles are fresh-only venvs (`.venv-rule-qualified`,
  `.venv-economics-qualified`) built from hash-pinned requirement locks; list them in the clone's
  `.git/info/exclude` (`.gitignore` already covers `.venv-*/`) and never rerun the installer over a preserved profile.
- `measure_rule_environment` hashes the installed profile, the source and `pyproject.toml` of `alpha-core`,
  `alpha-patterns`, `alpha-strategies` (plus `alpha-backtest`, `alpha-data` for the costed profile), the
  requirement lock and the root `uv.lock`. Any byte change in those raises `DataError` until profiles are
  rebuilt and fingerprints re-approved; old approvals and history are not rewritten.
  [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
- Stock RDLoop runtime: built only by `scripts/setup_rdagent.sh --with-stock-runtime` from the hash-pinned
  `stock-requirements.lock` on CPython 3.11 (`--require-hashes --no-deps`); `install_stock_profile.py` proves the installed
  distributions are exactly the locked ones and records an inventory digest. It measures a runtime and grants no authority.
- Editing `alpha_core`, `alpha_patterns` or `alpha_strategies` source changes the installed rule profiles' measured environment; rebuild them (see the native
  file).

## Model gateway

- Model gateway ([ADR-0044](../../adr/0044-rdagent-model-gateway.md), `model_gateway.py`): the one route from RD-Agent to a
  model. Standard library only; it listens on `127.0.0.1` and imports neither ALPHA nor RD-Agent. Chat is the confined Codex
  program (read-only, no tools, no web search), embeddings are local Ollama, and the paid route is off unless the owner
  configures it (`--chat-route api`; `--api-openrouter` requires every parameter to be honoured and settles on the
  provider's charged cost). A request parameter it cannot honour is refused or recorded as waived, never dropped silently. Call and
  dollar budgets fail closed: 60 counted calls and USD 10 per run, USD 50 per month (not raisable).
  Local and provider embeddings share a 2,000-request guard, exempt from chat call counts; provider tokens cost money.
  Paid inputs batch by 32; exact-text cache hits cost no requests or money. Receipts count inputs, requests and hits.
  Receipts split calls, tokens, cache hits and observed providers; labelled calls add step splits. Missing facts stay null;
  abandoned usage is unknown; booked amounts are reserved estimates. API chat sends `session_id` unless `--no-router-session` is set;
  provider preferences, budget arithmetic and old receipts stay unchanged. Logs hold hashes and lengths, not text or new headers.
  Memory binds model; no auto-switch; paid calls 180 s, one counted retry ([ADR-0055](../../adr/0055-spread-check-family-brief-and-universe-file.md)).
- Gateway embedding backends and accounting live in `gateway_embeddings.py`: local by default, or an explicitly priced provider model. Both share the
  2,000-attempt guard; paid embeddings spend money but no chat calls. Paid memory inputs batch by 32, with per-request receipts. Model-bound memory uses a
  sidecar; `embedding_eval.py` checks retrieval. See the worker invariants for accounting and compatibility.
- Chat cache/provider observations and receipt summaries live in `gateway_usage.py`; API sessions use the run id unless `--no-router-session` is set.
  Contracts: `test_rdagent_gateway_usage.py`.
- RD-Agent reaches every model through ALPHA's local model gateway (`workers/rdagent/model_gateway.py`,
  [ADR-0044](../../adr/0044-rdagent-model-gateway.md)): chat through the signed-in Codex program; embeddings through
  local Ollama by default, or a configured paid provider model with explicit pricing. The gateway holds ALPHA's call
  and dollar budget, refuses or records every setting it cannot honour, and logs each call without its text. Cache and
  serving-provider facts reach the receipt; API calls use a run-only router session, with a comparison-run opt-out.
  Recording details: [worker change notes](../../../workers/rdagent/CHANGE-NOTES.md#model-gateway-2026-11-14).

## Factor loop and judging

- ALPHA-judged factor loop ([ADR-0049](../../adr/0049-alpha-judges-rdagent-factors.md), amended by
  [ADR-0050](../../adr/0050-swing-clocks-in-the-factor-judge.md)): the one model-connected real-data route, started by
  `factor_loop_launch.py` (not yet an `alpha` command). RD-Agent's own factor loop runs unmodified; only the classes
  named in its `QLIB_FACTOR_*` settings are ALPHA's (`alpha_factor_judge.py`, and `alpha_factor_coder.py`, which only
  repairs coding memory and guards the per-factor critic), and they import RD-Agent and pandas, never an ALPHA package: the
  evaluator `alpha_cli.rdagent_factor_eval` runs as a subprocess in ALPHA's environment. The loop is never given data
  on or after 2024-01-01; every factor goes to the append-only cross-run trial ledger (a repeat by code hash is not new
  evidence); `decision` is ALPHA's rule. A declared sign and weekly/monthly primary clock must pass screen, spread, replay
  and deflation. Other choices are diagnostics only. Failed deflation is `DEFLATION_FAIL`; a nonpositive top-minus-bottom spread is
  `SPREAD_FAIL` whatever its replay shows (still replayed and counted as a trial; a stricter gate, never a pass;
  [ADR-0055](../../adr/0055-spread-check-family-brief-and-universe-file.md)); the universe, calendar and year length
  come from a frozen universe file, optionally selecting its own store directory.
  Frozen counts correct stale scenario text; write-offs reach feedback. Identical-input mismatches are `UNSTABLE`, an invalid trial like `LOOKAHEAD`.
  Every record is `exploratory, not admitted, not yet confirmed`, with authority flags false and survivorship disclosed. The runtime is built only by
  `--with-factor-runtime` from `factor-requirements.lock`, recorded by `install_stock_profile.py --profile factor`. Generated factor code has no gateway
  address or token, but runs as the same user: it is not isolated from the run folder, the ledger or other processes (trusted-mistake guard only). A failed
  loop names its exit. Proposal failures close rounds without empty trace entries; critic failures retain execution/value feedback and skip later critics in
  that round; budgets still end the run. Internal coding errors retain completed factors for judging; two consecutive failures stop the run. Restored prompts
  retain up to four full same-panel rounds within the history budget. For memory resume, families, budgets and call counts see the [worker
  change notes](../../../workers/rdagent/CHANGE-NOTES.md#research-memory-2026-11-15). Tests: `tests/unit/test_rdagent_factor_{eval,judge,launch}.py`,
  `test_rdagent_research_memory.py`, `test_rdagent_{restore_and_history,families,budget_and_caps,gateway_usage}.py`.
- Exact-text embedding reuse is process-local; `idea_families.py` parses named inputs and `loop_guard.py` closes exhausted-provider rounds, including
  proposal, without inventing trials. Descriptions declare sign, primary clock and economic reason; past-return sign variants share closure. The code-critic
  guard preserves execution/value feedback and skips later critics in the failed round. Internal coding errors preserve completed factors for judging; two
  consecutive failures stop the run. Proposal history fits a character budget. New factor rows record the family and per-factor critic outcome. Vector rebuild
  receipts identify omitted nodes and causes. Restored panel provenance includes run receipts.
- Runs resume from completed rounds; an unfinished round is recorded as abandoned, never invented as a trial. The
  wrapper refuses proposals from idea families that have already failed repeatedly and asks again. Counts, caps and
  spend are always explicit. The technical rules of each of these are change notes in the [worker change
  notes](../../../workers/rdagent/CHANGE-NOTES.md#change-notes-moved-from-the-project-page-2026-11-18).

## Research memory

  `idea_families.py` reads named inputs (and placeholder values): unfamiliar names keep an `other:` family, symbols none; an unnamed input is unknown.
  Closed or undeclared proposals stop before coding, with two re-asks; sign mirrors share a family and past-return reversal joins momentum.
  [Discussion](../../../workers/rdagent/propose-and-discuss.md) records who selected ideas. Feedback treats a drop as a choice. Only tested ideas count.
  Rank twins (absolute correlation 0.98) repeat same-panel trials; missing values are disclosed. Code failures never close families.
- Human-authored rule families (`alpha_cli.rdagent_rule_family`): a preregistered spec, checked against its sha256,
  is backtested on Nautilus with reads stopping at 2023-12-31; reserved-period data aborts the whole family rather
  than becoming a trial outcome. A family appends one block of `AlphaRuleTrialV1` rows to the same append-only ledger
  (stage `replay`, within-family Benjamini-Hochberg q, the same label and false authority flags). Rule rows count in
  the ledger total (`ledger_trials_all_families` in family results and factor evaluations) but never enter RD-Agent's factor
  family, deflation, distinct-factor count or proposal summary. Tests: `tests/unit/test_rdagent_rule_family.py`.
- Verdict feedback and unknown ledger rows: ALPHA's code-level verdict (`LOOKAHEAD`, `UNSTABLE`, or `FAILED` for a wrong output
  shape; never a check that merely errored) demotes that exact code from RD-Agent's successful coding references and is
  recorded in `coder-verdicts.jsonl`; a demotion failure is recorded and never stops the run (see the memory section of the
  worker README). Ledger rows of a schema the reader does not know never stop a run: the proposer skips them with a
  counted note, and the evaluator counts each as one conservative trial (p = 1.0) and reports `ledger_unknown_rows`.
  Malformed complete lines and malformed known-schema rows still fail loud.
- The [proposal pause and stand-in answers](../../../workers/rdagent/propose-and-discuss.md) (`--discuss`; a stand-in answers with `alpha
  ledger reply --as stand-in`;
  the owner rule is the [stand-in entry](../project/owner-decisions-5.md#2026-11-18-stand-in-user-while-ideas-are-throwaway-tests))
  exchange JSON with the CLI in `discussion.py` after the family guard. Each proposer and re-ask reads choices from this run's decisions.
  Reflections pass on in full, plus drop names. The worker records revision notes, re-ask costs and times from each reply. Tests: `test_rdagent_discussion*`.
- The scenario checks the prepare receipt or HDF columns once. Proposal context, family closure and feedback share one parsed ledger per round, refreshed when
  size or modification time changes. Tests: `test_rdagent_read_once.py`.
- The evaluator appends shortlist and lineage diagnostics; the worker preserves that record. Policy and regression convention:
  [README](../../../workers/rdagent/judge-rules.md#shortlist-bookkeeping); no judging rule changes.
- Source input columns: [README](../../../workers/rdagent/judge-rules.md#futures-funding). Feedback separates global looks from family failures; session
  drift suggestions follow the frozen
  source. Tests: `test_rdagent_funding_columns.py`, `test_rdagent_families.py`.
- RD-Agent remembers across runs; what it keeps and its limits are in the worker's [research
  memory](../../../workers/rdagent/CHANGE-NOTES.md#research-memory-2026-11-15).

## Panels and identity

  New panels rescale redenominations, split reused tickers, join declared renamed successors and refuse unexplained gap jumps;
  old receipts keep their policy. Joins preserve earlier bars, reject overlap and record `identity_joins`.
- Optional futures funding is a separate hash-bound panel table; daily timing, identity joins and factor-specific eligibility:
  [README](../../../workers/rdagent/judge-rules.md#futures-funding). Tests: `test_rdagent_funding_columns.py`.

## Viewer

- Run viewer (`rdagent_viewer.py serve`, `rdagent_ui_entry.py`): RD-Agent's own unmodified Streamlit log viewer on a
  run folder, foreground and local only. It runs in its own hash-pinned Python 3.11 runtime, built only by
  `--with-ui` from `ui-requirements.lock` and recorded by `install_stock_profile.py --profile ui`; the entry
  verifies the pinned source and imports RD-Agent through the same narrow finder as the factor loop. It binds `127.0.0.1`,
  refuses a busy port, runs with an exact environment and a temporary home that is removed on exit, and replaces only
  symlinks it made. It reads run folders and grants no authority. The judge adds the viewer's information-ratio key as NaN,
  never a computed value. Tests: `tests/unit/test_rdagent_viewer.py`.

## Code map

Flat entry scripts and pinned locks that run Microsoft RD-Agent's native loops (synthetic fixtures, rule and costed probes, the stock RDLoop) in their own
environments for the CLI's native job supervisor, plus `model_gateway.py`, the local program through which RD-Agent reaches a model, and the ALPHA-judged
factor loop (`factor_loop_launch.py`, `factor_loop_entry.py`, `alpha_factor_judge.py`, `alpha_factor_coder.py`, `alpha_factor_data.py`; ADR-0049) with its
cross-run research memory (`research_memory.py`) and its universe files (`universes/*.json`, ADR-0055), and RD-Agent's own run viewer (`rdagent_viewer.py`,
`rdagent_ui_entry.py`, `ui-requirements.lock`; local only). The judge leaves human-authored rule trials (`AlphaRuleTrialV1`, written by
`alpha_cli.rdagent_rule_family`) out of RD-Agent's proposal summary. It is a separate uv project (`package = false`) with its own lock; no ALPHA package
imports it, though its probes import ALPHA packages inside qualified profile environments. It has no market, inference or evidence authority.

- Code: the scripts in `workers/rdagent/` and the lock files beside them (`model_gateway.py` is standard library only and imports neither ALPHA nor RD-Agent;
  `install_stock_profile.py` and `stock-requirements.lock` build the Python 3.11 stock runtime; `--profile ui` records the viewer runtime).
- Tests live in the root suite: `tests/unit/test_native_*.py`, `test_rdagent_model_gateway.py`, `test_rdagent_provider_embeddings.py`,
  `test_rdagent_embedding_{cap,eval}.py`, `test_setup_rdagent.py`, `test_rdagent_viewer.py`, `test_rdagent_factor_{eval,judge,launch}.py`,
  `test_rdagent_research_memory.py`, `test_rdagent_{gapped_universe,identity_breaks}.py` (the factor-runtime cases need `ALPHA_FACTOR_PYTHON` as well). Tests
  that need the RD-Agent source skip unless `ALPHA_RDAGENT_SOURCE` (and, for stock lanes, `ALPHA_STOCK_PYTHON`) is set.
- Root tests under `tests/unit/test_native_*.py` and `tests/unit/test_rdagent_model_gateway.py`.
