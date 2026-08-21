# Project ALPHA — Agent Operating Manual

Private, single-owner, local quantitative research platform. **Written and operated entirely by AI agents.** This file is authoritative and OVERRIDES default behavior. Be terse, fail loud, never violate the architecture DAG.

- Baseline spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`
- Current post-v2 delta: `docs/superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md`
  + `docs/audit/2026-07-19-post-v2-architecture-audit.md`
- Daily-data/broker-paper extension:
  `docs/superpowers/specs/2026-08-03-daily-data-ibkr-paper-hardening.md` (ADR-0017)
- External QuantPad research-data boundary:
  `docs/adr/0018-quantpad-external-research-data-boundary.md`
- Research Scientist program:
  `docs/superpowers/specs/2026-08-06-research-scientist-program-design.md` (ADRs 0019-0020)
- Research-first workstation program (design approved 2026-08-07; R1-R6 implemented and
  accepted 2026-08-10): `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md`
  (ADRs 0021-0026, Accepted; phase plans `docs/superpowers/plans/2026-08-07-research-first-R1..R6-*.md`)
- Full repair authority additions: `docs/adr/0030-touch-id-owner-presence-for-research-actions.md`
  + `docs/adr/0031-provider-readiness-and-paper-acceptance-v2.md`; the generated current surface
  inventory is `docs/governance/capability-authority-matrix.md`.
- Crypto data house: `docs/adr/0032-governed-crypto-data-house.md`; provider authority is assigned
  per dataset family and existing CCXT/paper bytes remain immutable.
- Generic study composition: `docs/adr/0035-generic-study-composition-and-external-capability-adapters.md`;
  the accepted projection-only boundary adds no authority until its staged implementation lands.
- Workstation v3 program: `docs/superpowers/specs/2026-07-19-workstation-v3-chart-artifacts-design.md`
  + `2026-07-19-workstation-v3-development-control-plane-design.md`
  + `2026-07-19-workstation-v3-evidence-agent-design.md`
  + `2026-07-19-workstation-v3-qlib-worker-design.md` (ADRs 0013-0016)
- Governance: `docs/governance/2026-07-19-dependency-license-matrix.md`
  + `docs/governance/2026-07-19-post-v2-risk-register.md`
- Research: `research/00-SYNTHESIS.md` (+ `research/01..07-*.md`)
- Repository research skills: `.agents/skills/alpha-research-scientist/`
  + `.agents/skills/alpha-adversarial-reviewer/`
- Repository development skills: `.agents/skills/karpathy-guidelines/`
  + `.agents/skills/incremental-implementation/`
  + `.agents/skills/code-simplification/`
  + `.agents/skills/code-review-and-quality/`
  + `.agents/skills/verification-before-completion/`
- Phase plans: `docs/superpowers/plans/2026-*.md`
- Python 3.12, `uv` virtual workspace (root is not a package). Members: `packages/*`, `apps/*`.


## Rules (path-scoped, `.claude/rules/`; load when matching files are touched)
`00-karpathy.md` (always) · `alpha-core.md` · `alpha-data.md` · `alpha-strategies.md` · `alpha-backtest.md` · `alpha-validation.md` · `alpha-research.md` · `alpha-forecast.md` · `alpha-analytics.md` (options/screener) · `alpha-patterns.md` · `alpha-study.md` · `alpha-cli.md` (full CLI surface + module map) · `alpha-mcp.md` · `alpha-web.md` (+ frontend) · `quant.md` (gauntlet gates + oracle duties) · `tests.md` · `docs.md`. The MODULE MAP and CLI surface were relocated there verbatim (`tests/unit/test_claude_md_relocation.py` proves zero loss against `tests/fixtures/claude_md_v1.md`). Generated awareness: `uv run python scripts/gate.py brief` (session brief) and `gate.py index` (`.claude/state/repo-index.json`).
- ADRs: `docs/adr/` holds ADRs 0001-0035 (index `docs/adr/README.md`); ADR-0029 four-family Monte Carlo validation; ADR-0030 Touch ID owner presence; ADR-0031 provider readiness + paper acceptance v2; ADR-0032 governed crypto data house; ADR-0033 governed crypto crowding research + sandbox basis; ADR-0034 agent operating system v2 (harness); latest ADR-0035 generic study composition (projection-only). Every ADR id must be referenced here or in a rule.

## Architecture DAG (import-linter enforced — NEVER violate)
`alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_patterns` → `alpha_core`; `alpha_study` → `alpha_core` + `alpha_data` + `alpha_patterns` + `alpha_research`; `alpha_strategies`, `alpha_validation`, `alpha_forecast`, `alpha_options`, `alpha_screener`, `alpha_research` ← `alpha_core`; `alpha_cli` ← everything; `alpha_mcp`, `alpha_web` ← `alpha_core` + public `alpha_cli` seams (top of DAG).
- `alpha_core` imports nothing internal.
- `alpha_data` → core only. `alpha_strategies` → core only. `alpha_validation` → core only. `alpha_forecast` → core only (only `alpha_cli` may import it). `alpha_options` → core only. `alpha_screener` → core only. `alpha_research` → core only. `alpha_backtest` → core + data only.
- `alpha_patterns` → core only (pure pattern geometry; no app consumer yet — see `.claude/rules/alpha-patterns.md`).
- `alpha_study` → core/data/patterns/research only. It publishes strict immutable feature-lineage, event/factor tables, closed operator registration, existing-authority references, derived finding/mechanism/advisor/workspace projections, one thin registered-double-bottom → `EventTableV1` adapter, and an S5a1 byte-bound blind semantic-read contract. The semantic contract binds the complete D0 acceptance/events/chart bytes, requires exact event agreement, and omits post-cutoff point identity/clocks/values; its cutoff lineage remains `not_checked` until the CLI verifier composes it. Event-study inference and server/UI semantic delivery remain deferred. It owns no persistence, CLI command, UI, approval, D1/D2 transition, promotion, paper, broker, or order authority (see `.claude/rules/alpha-study.md`).
- `alpha_cli` is the ONLY layer allowed to compose the backtest engine with the validation gauntlet.
- `alpha_mcp` and `alpha_web` sit atop the DAG and compose nothing — actions plus provider/system and engine-backed projections subprocess the `alpha` CLI. Their in-process reads are limited to supported public CLI seams (catalog/run store, artifact contract/run projection, job capacity/durable lease, and paper store) plus bounded Polars artifact projection. They never import or execute the engine, gauntlet, Nautilus, Qlib, or Kronos in-process. Nothing imports either surface.
- The MCP surface is consciously **pinned at 62 tools** — adding or removing one is a deliberate governance change that must move `server.py`, the `test_research_mcp.py` pin, and this line together.
- Contracts live in root `pyproject.toml` `[tool.importlinter]` (15 forbidden contracts, including outbound surface limits). Run `uv run lint-imports` after any cross-package import change.

## Golden rules (invariants)
- **Engineering workflow discipline.** Before writing, reviewing, or refactoring code, load
  `karpathy-guidelines`. Also load `incremental-implementation` for multi-file work,
  `code-simplification` for behavior-preserving refactors, `code-review-and-quality` before merge,
  and `verification-before-completion` before claiming work is complete, fixed, or passing. This
  manual takes precedence if any general skill conflicts with a Project ALPHA invariant.
- **TDD.** Failing test → minimal code → green → commit. Small, atomic, conventional commits (`feat(scope):`, `fix(...)`, `test(...)`, `build(...)`, `chore(...)`, `docs:`).
- **No look-ahead, ever.** Strategies/backtests read data ONLY via the point-in-time accessor `as_of`. Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`. Mechanism: `feed.to_execution_feed` emits an open-priced `QuoteTick` (at `bar.ts`) + a close-stamped (+23h) decision `Bar`; venue runs `bar_execution=False` so only quotes fill.
- **No empty `except`.** Raise/propagate typed `AlphaError`/`DataError`/`LookAheadError` with context, or re-raise. Fail loud on data gaps / NaN / inf / disorder / degenerate stats.
- **Polars** is the default dataframe. pandas ONLY at three sanctioned vendor/library edges: the yfinance adapter/parser (`alpha_data.adapters.yfinance_adapter` — the vendor returns DataFrames), the tear-sheet renderer (`alpha_validation.tearsheet`, with `quantstats_lumi`), and the Kronos model facade (`alpha_forecast.kronos` — upstream API speaks DataFrames). `numpy`/`scipy.stats.norm` and deterministic Matplotlib rendering are sanctioned in the `alpha_validation` and pure `alpha_research` layers; numpy/torch also live inside `alpha_forecast` internals (never at its public seam, which is plain floats/tuples).
- **Strong typing.** `mypy --strict` is a CI gate. Overrides (do not "fix"): `nautilus_trader.*`, `scipy.*`, `quantstats_lumi.*` are `ignore_missing_imports` (no loadable stubs); nautilus Cython base classes get `# type: ignore[misc]`.
- **Determinism (spec §11.4 + ADR-0013).** All seeds derive from `AlphaSettings.random_seed` (default 7). New v3 stochastic work derives seeds from stable semantic namespaces (family/tier/fold/iteration), never positional list order. A v3 `run_id` hashes normalized configuration, snapshot hash, seed, and strategy source/execution fingerprint. Manifests, causal traces, and QuantStats-Lumi HTML are byte-stable; a completed run directory is immutable and an identity-matched byte conflict fails loudly.
- **Private local-use scope.** ALPHA is permanently a single-owner application for the owner's local device. It is not a product, service, public project, or distributable package, so a root project license and distribution-release review are out of scope. Keep third-party notices, provider terms, and data-retention restrictions intact; reopen distribution governance only if the owner explicitly changes this scope. See `docs/governance/2026-07-19-dependency-license-matrix.md`.
- **Corporate actions: two clocks.** Knowledge time (`announce_date` else `ex_date`) gates visibility; `ex_date` gates price application (a known-but-future split does NOT rescale prices yet). Splits adjust the price series; dividends are decoupled cash events **credited by the engine at `pay_date`** against the pre-ex holding (shorts debited; never folded into prices; threaded through every run path incl. Tier-2 nulls — Tier-1 stays price-only by design). Yahoo serves split-adjusted OHLCV, so the yfinance parser reconstructs RAW prices from in-window split events (fails loud if the vendor convention drifts). See spec §6.1.
- **Crypto data is family- and venue-specific.** Binance native data owns CEX spot/futures history;
  Bybit owns advanced derivatives/options; CoinGecko owns identity/reference; GeckoTerminal owns
  DEX pool data; Coin Metrics Community owns its frozen catalog and only the reviewed on-chain
  metrics proven available by it; Coinbase/CCXT is comparison.
  Never create a universal crypto price, merge USD/USDT/USDC, join by ticker alone, or automatically
  fall back across venue, market type, units, frequency, or evidence. Existing CCXT snapshots and
  the `ccxt:binance` paper warmup contract remain byte-compatible (ADR-0032).
- **Research before strategy.** A raw market observation uses the `alpha-research-scientist` skill to preserve the idea, draft competing explanations, inspect source/data feasibility, and freeze a bounded falsifiable contract before strategy code or hypothesis-specific sweeps. The `alpha-adversarial-reviewer` attacks every gate. Every fresh `alpha project create` automatically captures a research-required case; only pre-launch projects already present at the schema-v2 migration are grandfathered. The deterministic Gate 1 schema/intake/dossier, D0 research primitives, and bounded CLI/MCP/REST/Cockpit walking skeleton grant no autonomous-runner, strategy, holdout, paper, or execution authority. The R5 D1 runner (`alpha research run deep`, ADR-0025) is owner-CLI-launched only, executes the frozen analysis plan strictly on the discovery share, and is mechanically re-verified at admission. The R6d one-shot D2 (`alpha research run confirm`, ADR-0026) is live: owner `approve confirmation` authorizes the sealed share, the frozen primary reads it exactly once, every admission and read re-verifies by exact recomputation, and a pre-flight integrity failure contaminates the share (owner INVALID-only exit). The R6e owner decision view (`alpha research decision-view --json`) assembles the fourteen-question spec-§10.1 edge-validation checklist (typed finding statuses or explicit NOT_TESTED — never a numeric aggregate), the full readiness scorecard, the terminal gate packet (closed cases only), and the append-only decision history. The R6f promotion plane records the lossless spec-§11 `strategy_promotion` dossier atomically inside the closing phase transition whenever the owner decision is `advance_to_strategy` (HypothesisCard, terminal gate-packet id+hash, registered datasets, screened claims, confounder/falsification/stability/attempt ledgers, verified chart references, open questions), and `alpha project agent-brief` embeds the as-of-filtered `research_promotion` reference. The R6g research gate makes spec-§15 anti-premature-backtesting visible and governable: `research_gate_state ∈ {not_required, open, passed, overridden}` is derived strictly from governance/decision/override records (passed supersedes overridden), owner overrides are append-only actor+reason events, an overridden gate is the only unlinked path through `create_strategy_version`, and every run launched under an override is permanently watermarked (manifest `research_gate` block, forked run identity, suite-injected flag, CLI/REST/SPA rendering on ≥3 surfaces plus the Operations overrides list). The R6h SPA gate locks every Develop-desk strategy-creation/optimisation affordance while the linked project's `research_gate_state` is `open` (relay-only — the SPA never derives state; a failed projection read fails open because the CLI/store enforce), surfacing the reason and a one-shot deep link to the research case. The R6i program acceptance suite (`tests/integration/test_research_program_acceptance.py`) proves the spec-§17 composites end-to-end through the public CLI: capture→D1→one-shot D2→SUPPORTED→promotion with the dossier reaching the strategy AgentBrief byte-identically, SUPPORTED-without-advance never promoting (gate stays locked), and honest pre-D2 parks that cannot claim support. The research-first program (R1-R6) is complete; ADR-0021..0026 are Accepted.

- **Research D0 read integrity.** Completed-D0 recovery, status/dossier, phase, and packet
  projections repeat the exact acceptance recomputation and bind the SQLite-stored acceptance
  selector to the current manifest; post-admission artifact/manifest rewrites fail closed.
  Changing ANY registered D0 constant (detector spec, fixture lows, power parameters/seed,
  runtime version) is a breaking generation change that MUST bump `_D0_FIXTURE_VERSION`; a
  well-formed foreign generation fails with an explicit generation-mismatch error, never one
  implying tampering. The D0 power seed is protocol-frozen by design — NEVER derive it from
  `AlphaSettings.random_seed` (acceptance is re-verified by exact recomputation on every reader,
  so a settings-derived seed would break machine-independent verification).
- **Research migration integrity.** The v1→v2 path holds one SQLite writer lock from before the
  exact rollback snapshot through additive DDL and the v2 marker commit; a waiting migrator
  re-reads the version under that lock.

## Commands
- Install: `uv sync`
- Full Python gate (run before every commit; mirrors CI `.github/workflows/ci.yml`):
  `uv lock --check && uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run mypy packages apps tests && uv run pytest -q -m "not network" --cov --cov-report=term-missing && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && uv build --all-packages` followed by reinstall/import smoke for all 14 built wheels (see CI for the exact module assertion).
- Frontend gate: `cd apps/alpha-web/frontend && npm ci && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npx playwright install chromium && npm run test:e2e` (`test:e2e` builds the production SPA; generated contracts and `static/app` must stay clean; Playwright/axe covers six desks, the three required viewport sizes, keyboard use, and serious/critical accessibility failures).
- Isolated literature worker gate: `cd workers/literature && uv lock --check && uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -m "not network"`. Stdlib-only; deliberately not a root workspace member.
- Isolated Qlib worker gate: `cd workers/qlib && uv lock --check && uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q`. It is deliberately not a root workspace member.
- Bias guards only: `uv run pytest -m bias_guard -q`
- Live-network tests (off by default, hit real APIs): `uv run pytest -m network -q`
- CLI smoke: `uv run alpha info`
- Ruff: line-length 100, target py312, rules `E,F,I,B,UP,SIM`. Markers (`--strict-markers` on): `bias_guard` (look-ahead/survivorship guards, gated in CI), `network` (skipped in CI/offline).


## MODULE MAP
Relocated verbatim, one layer per path-scoped rule (`.claude/rules/alpha-*.md`, listed above); `.claude/state/repo-index.json` (`gate.py index`) is the generated symbol-level index.

## Where do I add X?
- **New strategy** → `alpha_strategies`: pure decision fn(s) in a new module + a `nautilus Strategy` subclass; bias-guard test required. Wire defaults via `_runner.RunSpec` / CLI flags.
- **New data source** → `alpha_data/adapters/<name>_adapter.py`: a pure parser fn + a `DataAdapter` class (`name`/`version`/`parser_version`); add one evidence-gated `ProviderDefinition` so `data_cmds` derives it. Live-net code under `@pytest.mark.network`.
- **New validation gate / statistic** → `alpha_validation`: engine-agnostic primitive (numpy/scipy, fail-loud), then wire into `alpha_cli/_gauntlet.py` and extend `tearsheet.build_outcomes`/the report schema.
- **New generic study projection/composition** → `alpha_study`: map to an existing `alpha_research`/`alpha_cli`/control-store authority and keep the seam deterministic and projection-only; new contracts require an accepted ADR/FeaturePlan boundary and must not add persistence, CLI commands, UI, or external dependencies in the package.
- **Anything composing engine + gauntlet / multi-package orchestration** → `alpha_cli` ONLY (the DAG forbids it elsewhere). Keep engine imports lazy.
- **New domain type / error / protocol / setting** → `alpha_core` (export via `__init__.py`).
- **New net-new analytics module** (e.g. options/screener) → a new core-only `packages/alpha-*` + its own import-linter "depends only on core" contract + an `alpha_cli/<x>_cmds.py` sub-app emitting `--json` (register in `main.py`).
- **New Workstation panel** → a manifest/artifact read and/or `alpha ... --json` projection + an `alpha_web/api/` router + a `frontend/src/panels/` component placed on a screen in `shell/screens.tsx`. Operational state needs a separately governed public seam (never `RUN_DIRS` by default). Then run the frontend gate and commit `static/app`.
- **New figure** → a `FigureDefinition` in `alpha_research/figures/catalog.py` (its question, uncertainty and caveat are required, not optional) + one builder in `alpha_cli/figures/_builders.py` that reads declared artifacts and computes nothing the renderer could not have been handed. Never draw in the SPA: an analytical chart the user can export belongs in Python, where it is byte-stable and carries its own title, units and provenance.
- **New trading observation/research idea** → use `.agents/skills/alpha-research-scientist/SKILL.md`; keep it upstream of strategy development and within ADR-0019/0020. If the required Research Scientist gate is unimplemented, return the missing capability instead of creating an ad hoc authoritative path.

## Build status
**Current research-program status (2026-08-19):** R1–R6 and the seven-stage repair program are
implemented. All empirical web launches require a server-verified governed or permanently
unqualified context; generic jobs cannot exercise owner or broker authority. Guided Research is the
default fixed-screen workflow, while Advanced mode adds inspection only. Material-question bundles,
compact D2 boundaries, project context, owner-action Touch ID, isolated literature discovery and
anchored claims, receipted provider readiness, and mechanically reverified PaperAcceptanceV2 are
the current contracts. Legacy runs, claims, boundaries, and paper journals remain readable but gain
no new authority. The private local implementation is complete; production, distribution, sale,
hosting, and multi-user readiness are permanently out of scope. The generated capability/authority
matrix is the source of current REST and MCP counts; never copy its counts into prose. External
provider and broker acceptance remains receipt-driven: a failed or absent live check is an honest
environment state, not a software pass. ADR-0028's modeling capabilities are implemented:
immutable `MarketStateV1`, validation-frozen Kronos calibration and `kronos_calibrated` candidate
assessments, additive Qlib `rank_ensemble_v1` exchanges, and six server-rendered modeling
diagnostics. These remain research-only capabilities, not evidence of profitable improvement; the
candidate-promotion gates still apply. The dated implementation
narratives below are retained in `docs/BUILD-STATUS.md` as historical delivery records; where
they conflict, this paragraph, ADR-0027/0028/0030/0031, and the generated authority matrix
govern. The harness (ADR-0034) and the Codex provider/crypto program (ADR-0030..0033) merged on
2026-08-19; the branch cleanup plan is docs/superpowers/plans/2026-08-19-branch-cleanup-simplify-merge.md.

The full dated delivery history (phases, live-data verification, audits, Kronos,
paper trading, QuantPad, Workstation v1–v4, Research Scientist program, research-first
R1–R6, four-family Monte Carlo) is relocated verbatim to `docs/BUILD-STATUS.md` —
consult it before changing any governed surface; append new delivery records there.

## Claude Code harness (mechanical enforcement)
Claude Code sessions in this repo run under a hard-blocking hook harness (full doc:
`docs/operations/claude-code-harness.md`). The prose rules above stay authoritative; the harness
makes the load-bearing ones mechanical:
- **Gate stamps.** `uv run python scripts/gate.py fast|full` runs the tiered gate and stamps the
  current tree CONTENT (`full` mirrors CI incl. the 14-wheel smoke). Stopping a session after
  source edits requires a fast stamp; any `git commit` requires a full stamp (docs-only commits
  waived). Stamps invalidate on any content change and survive pure commits.
- **Commit guard.** Conventional commit message enforced; >1000 changed non-docs lines blocked;
  staged risk-tier paths (quant paths + `packages/alpha-backtest/src` + the seven `alpha_cli`
  modules `_gauntlet/_optim/_seeds/_identity/_surrogate/_synth/_runner`) additionally require an
  APPROVE `ReviewVerdict` bound to the current tree (`/review-gate`).
- **Quant attestation.** Edits under `packages/alpha-validation/src`, `packages/alpha-research/src`,
  or any dsr/psr/pbo/deflated/bootstrap/reality_check/spa/montecarlo/walkforward/cpcv/
  multiple_testing/overfitting module require a PASS `QuantVerificationReport` (`/verify-quant`;
  primary-source cross-check per `.agents/skills/quant-source-verification/`) before Stop.
- **Protected control plane.** `scripts/{gate,claude_hooks,harness_models,harness_quant,
  harness_awareness,codex_bridge}.py`, `.claude/settings.json`, `.claude/statusline.py`,
  `.claude/{harness,mutation}-baseline.json`, `.mcp.json`, `.semgrep/alpha.yml`,
  `.claude/{skills,agents,commands,rules}/**`, `.codex/**`, `.github/workflows/**`,
  `tests/{bias_guards,holdout,oracles}/**`, `tests/unit/test_claude_harness_*`,
  `tests/unit/test_claude_md_relocation*`, `tests/unit/test_repo_awareness_drift*`, `CLAUDE.md`,
  `AGENTS.md`, and `pyproject.toml` edits touching import-linter/coverage/mypy-strict config each
  need a one-shot audited `gate.py ack` — the harness cannot be silently weakened.
- **Escape hatches (all audited to `.claude/state/harness-audit.jsonl`):**
  `uv run python scripts/gate.py override --reason "..."` (one commit), `ack --reason "..."` (one
  control-plane edit), env `ALPHA_HARNESS_DISABLE=1` (emergencies). `python3 scripts/gate.py doctor`
  verifies the wiring. Subagent team: navigator · test-architect · quant-verifier ·
  invariants-auditor · independent-reviewer · red-team-code · adversarial-reviewer ·
  retrospective · codex-liaison. Commands: `/plan-feature` `/implement` `/gate [full|fast]`
  `/verify-quant` `/review-gate` `/adversarial-review` `/harness-doctor` `/codex-review`
  `/codex-research` `/retrospective` (feature pipeline: `.agents/skills/alpha-feature-workflow/`).
