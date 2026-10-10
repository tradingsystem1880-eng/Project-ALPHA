# Project ALPHA — Build Status (delivery history)

**2026-10-02 crypto provider and archive hygiene work (in progress):** Added DefiLlama public
reference data for protocol TVL, stablecoin supply, current yield-pool snapshots, and exact-pool
history across parser, qualification, CLI acquisition, typed API, and Data Manager surfaces. The
archive's immutable artifact verifier did not complete in the prior audit; no immutable artifacts
were removed. Existing provider adapters remain reachable in current route/use mapping. Focused
DefiLlama parser/acquisition/API tests pass; aggregate gates and full archive verification remain
unverified for this exact shared tree. On 2026-10-02, live acquisitions for Aave TVL (2,328 rows),
stablecoin id `1` supply (3,230), yield-pool snapshot (17,061), and an Aave/Ethereum pool history
(902) all qualified and passed recursive manifest/raw-lineage verification. `cache-clean` removed
2,190 explicitly disposable bytes and zero immutable artifacts. Backend and frontend full component
gates passed, as did Atlas and eval component checks after Atlas regeneration. The full aggregate
command must still be rerun on that regenerated tree; a full archive inventory also remains open.

Relocated from `CLAUDE.md` on 2026-08-18; CLAUDE.md keeps only the governing
current-status paragraph, which is maintained there and may be newer than the copy
below. With ADR-0027/0028, that paragraph takes precedence over the dated narratives
below wherever they conflict. Append new delivery records HERE.

**Current research-program status (2026-08-11):** R1–R6 are implemented and integrated, and the
scientific-authority hardening in ADR-0027 is complete. The private local implementation is
complete; production, distribution, sale, hosting, and multi-user readiness are permanently out of
scope. The owner real-case pilot remains an empirical-validation action, not a software release gate.
Python is the sole readiness authority; the temporary D1/D2 admission flags and duplicate
TypeScript scorecard/checklist derivations are retired. Research now lives in the fixed six-screen
Workstation, the MCP surface remains pinned at 62 tools, and immutable D1 chart/table evidence is
rendered through the server figure system. ADR-0028's modeling capabilities are implemented:
immutable `MarketStateV1`, validation-frozen Kronos calibration and `kronos_calibrated` candidate
assessments, additive Qlib `rank_ensemble_v1` exchanges, and six server-rendered modeling
diagnostics. These remain research-only capabilities, not evidence of profitable improvement; the
candidate-promotion gates still apply. The dated implementation
narratives below are retained as historical delivery records; where they conflict, this paragraph
and ADR-0027/0028 govern.

Phase 0 (rails) ✅ · Phase 1 (data spine) ✅ · Phase 2 (backtest core + strategy) ✅ · Phase 3 (validation gauntlet) ✅ · Phase 5 (tear sheet + CLI) ✅.
**Live data spine verified against real markets** ✅ (yfinance + ccxt/coinbase end-to-end; gauntlet correctly rejects single-name `ts_momentum` on AAPL and accepts a diversified basket. Stooq is anti-bot-gated → fails loud).
Phase 6 shipped scope — complete and professionally hardened: strategy registry + 3 more strategies ✅ · institutional gauntlet ✅ · overfitting-aware optimization ✅ · basket portfolio ✅ · returns-level cross-sectional momentum ✅ · Stooq adapter ✅ · prop-firm Monte Carlo ✅. Explicitly deferred product expansion: full-engine cross-sectional execution, FRED/non-OHLCV macro data, and model fine-tuning.
**2026-07 institutional audit** ✅ — 38 verified findings fixed on main (see `docs/audit/2026-07-05-institutional-audit.md`): yfinance raw-price reconstruction (PARSER_VERSION=2), allow-short-by-account fail-loud, honest two-tier nulls (+ convention-divergence guard), verified `--snapshot` reads, causal portfolio weights, dividend cash crediting at `pay_date`, opt-in `--size-on-equity`/`--halt-drawdown`, crypto instruments, web/MCP hardening, schema-v2 manifests.
Kronos foundation-model track (spec `docs/superpowers/specs/2026-07-04-kronos-forecast-integration-design.md`, ADRs 0008/0009/0010) — COMPLETE, landed on main via the 2026-07 cleanup: `alpha_forecast` package (vendored pinned model @ `67b630e6`, typed facade, FakeForecaster, torch-cpu CI index) ✅ · `alpha forecast run` (outcome cones, leakage warn, MCP) ✅ · web fan chart ✅ · `alpha forecast eval` (CRPS/coverage vs RW+bootstrap baselines, pre/post-cutoff split) ✅ · `kronos` strategy via content-addressed signal caches through backtest/validate/optim (+ `--tier2-mode replay|model`) ✅ · fully-local weights: Kronos-base (largest released; Kronos-large is closed) cached at `data/models`, hash-pinned + offline-loaded via `.env` (`ALPHA_FORECAST_HUB_CACHE`/`_LOCAL_ONLY`, ADR-0010) ✅. Deferred: kronos through portfolio/propfirm-fresh paths (build fails loud with guidance), tearsheet caveat note, fine-tuning (zero-shot only per spec).
**Four-family Monte Carlo validation (2026-08-12)** ✅ — ADR-0029 and the dedicated design spec add a required `monte_carlo` stage after robustness and before optimization: 10,000 IID empirical, causal calm/volatile Markov, and Student-t paths over canonical OOS account returns plus 128 exact-calendar Kronos OHLCV tails replayed through fresh canonical engines. Immutable v3 evidence, independent ALPHA risk grades, derived Workstation figures, fail-closed non-estimability/tamper checks, and CLI-only exact-hash owner warning review are implemented. This evidence measures scenario/path risk only; the randomized-price gate, holdout, paper, and execution authorities are unchanged.
Phase 4 (paper trading) — **offline implementation extended and verified 2026-08-04**: the original public-Binance-data/local-Nautilus-Sandbox path remains; Tiingo EOD now supplies strict receipt-backed authoritative stock/ETF candidates, quality/quarantine/correction/promotion recovery, raw-receipt re-verification, and versioned provenance; an exchange-calendar launchd tick creates verified snapshots, resumes an already-published exact snapshot after repair, runs real Nautilus simulations, and emits exact immutable order intents; native pinned Nautilus IB clients add a paper-only loopback/DU-account boundary with dual flags, allowlists, one-shot cross-process intent claims, reconciliation that seeds overnight units, hard risk, exact fresh-quote/cutoff enforcement, intent-as-client-order-ID, cancellation/expiration journaling, and safe stop without flattening. Journal schema v2 distinguishes `local_sandbox`/`ibkr_paper` while preserving v1 reads; the Workstation shows provenance, paper markers, mode, reconciliation, and machine readiness. The standalone R-14 public Binance quote smoke passed locally on 2026-08-04, but durable readiness evidence and R-24 UTC rollover remain pending alongside current-universe Tiingo cross-source qualification and every real IBKR Paper equity/futures scenario. No live-capital route exists; futures remain micro-contract connectivity probes and research-unsupported. “Paper passed” remains machine-pending until all scenarios are recorded without blockers.
**QuantPad external research access (2026-08-04)** — project-scoped Codex MCP registration is documented for symbol/schema/coverage discovery and bounded bar previews; the official REST/Python API is the only approved bulk bars/ticks/L1/L2 route. QuantPad remains historical research scratch data, not canonical authority or paper evidence, until a receipt-backed adapter, qualification suite, and retention/license evidence are approved (ADR-0018).
**2026-08-04 release-candidate network evidence** — Binance public quotes, CCXT history, Kronos, Yahoo, and a short AAPL Tiingo receipt→promotion→snapshot→candle cycle passed locally; Stooq returned its documented anti-bot skip. Durable Binance readiness evidence, R-24 UTC rollover, Tiingo-universe qualification, and every real IBKR scenario remain pending.
QuantPad-parity track (separate from the internal phase numbers above): A–F Verdict + tail-risk ✅ · prop-firm Monte Carlo ✅ · conversational agent = MCP server (`alpha_mcp`, subprocesses the CLI; `uv run alpha-mcp` / repo `.mcp.json`) ✅ · local web IDE (`alpha_web`; now the Workstation SPA) ✅. All four QuantPad-parity surfaces shipped.
**ALPHA Workstation** ✅ (spec `docs/superpowers/specs/2026-07-16-alpha-workstation-design.md`) — this historical delivery introduced the FastAPI/Vite application. Its current form is the fixed six-screen Research · Build · Results · Compare · Studios · Operate shell: Research contains the guided case, evidence, price, backlog, literature, research-data, market-data, and Codex Research surfaces; Build keeps governed development separate from the permanently unqualified Standalone Sandbox. The browser holds no vendor or broker secrets, derives no research authority, and uses the same Python gates in Guided and Advanced modes. SPA source lives under `apps/alpha-web/frontend`; built assets are committed and CI verifies frontend lint, coverage, generated types, build, and asset freshness.
**Workstation v2 — the real trading terminal** ✅ (2026-07-18) — the 10x pass: **live desk** (`/api/activity/stream` SSE store/job diffs; Activity Feed + Job Monitor panels, toasts, live Run Browser — Claude-launched CLI/MCP runs surface without reload) · **explanation engine** (`frontend/src/explain/`: dual-voice gate/verdict narratives drift-guarded against `verdict.py`, next-step suggestions, expanded glossary + Term tooltips + Glossary panel) · **run story** (tabbed kind-aware Run Detail: gates w/ null histograms + CI bar, fold-shaded synced equity/drawdown w/ trade markers, optim param heatmap + per-trial curves, propfirm funnel + outcome histograms, forecast 50/90% fan + spaghetti, forecast-eval CRPS-per-origin) · **shell v2** (working SYM/ASOF, palette v2 w/ symbol/run/action/workspace pages, density + narrative/terse toggles, first-run desk preset, `#run=` deep links, per-panel error boundaries, self-hosted fonts, full A–F verdict colors) · **Pipeline panel** (guided loop w/ prefilled next steps) · TanStack sortable/virtualized blotters · Phase-6 deterministic artifacts (nulls/trials/propfirm-paths/portfolio-equity parquet) + typed projections serving them. Frontend vitest (node-env, local-only) guards the band mirror.
**Workstation v3 — professional strategy-development program** (implementation and offline release gates verified 2026-07-19; paper/data surfaces extended 2026-08-03) — **Implemented; offline release gate passed.** The program includes manifest/run-identity/artifact-contract v3 with immutable causal chart traces and v1/v2 readers; fresh-state OOS/holdout execution with matching scoped evidence; six curated linked desks with atomic v2→v3 layout migration; bounded native dark Python-authored tear sheets plus deterministic QuantStats-Lumi audit export; complete-path Kronos K-line/cone/distribution/calibration; a governed SQLite project/version/experiment/14-stage/attempt/holdout/job/evidence control plane; versioned bounded REST projections; the then-current bounded MCP surface with `AgentBrief`; and a separately locked Qlib/LightGBM worker whose close-stamped predictions are validated and synchronously replayed across the frozen universe through ALPHA's canonical engine. Qlib replay metrics are authoritative for that execution, but full counterfactual model-refit validation remains explicitly unimplemented. The browser has no vendor/broker credentials or direct streams, displays source/snapshot/quality provenance and low-volume paper journal markers, and never constructs orders. Holdout reveal and paper enabling remain unavailable to unattended agents. R-22 is retired under the permanent private/local-only scope; all real-network paper acceptance listed above remains pending.
**2026-08-03 live-UI hardening** ✅ — capability-scoped desks, dormant hidden tabs, bounded causal marker layers/payloads, explicit artifact-unavailability states, suite-managed Qlib lineage, and single-pass vector annotation rendering were verified against representative v3 portfolio, Kronos, trace, development, evidence, and real isolated-Qlib artifacts. The full offline Python and frontend gates remain green. Its research-decision scope remains sandbox-only; operational broker paper is the separately governed Phase-4 boundary above.
**Research Scientist program (2026-08-06)** — **Gate 0 and the deterministic Gate 1/D0 walking skeleton implemented.** The authoritative spec, ADR-0019/0020, risk/dependency decisions, and Research Scientist/adversarial-reviewer skills define the finite owner workflow. Schema v2 adds a research-required governance marker, immutable source packs/contracts, independent phase, execution, D2, attempt, and decision histories, and append-only launch reservations with one-to-one terminal-attempt links; project/case capture is one restart-idempotent SQLite transaction, normal APIs cannot forge migrated grandfathering, and v1 rollback backups are logically bound to the migrated source. `alpha research` locally captures an intake preview, materializes an approval-ready draft, records trusted-local owner review, runs/verifies the one contract-bound canonical double-bottom D0 operator, projects status, exports/verifies the canonical `data_dir/research/projects/<project_id>/` dossier, supports audited pre-D2 close/revision, and emits a content-addressed terminal ResearchGatePacket that says `NOT_TESTED` when typed D1/D2 evidence is absent. The only approval-ready Gate 1 operator uses the exact `alpha_synthetic_fixture`/`SYNTHETIC_SPY`/UTC 60-minute plus 240-minute-window fingerprint; other material choices remain explicit unavailable drafts. D0 completion requires one artifact-complete v3 run whose ID is derived from the frozen contract, fixture, and execution fingerprint plus a canonical hashed `ResearchD0AcceptanceV1` artifact containing raw measurements only. Admission mechanically reruns the frozen detector, null, four-observation topology-embargo, and prospective-power criteria; producer-supplied pass flags are not authority. A launch also fails before compute when the approved code, dependency-lock, evaluator, or environment fingerprint has drifted. Each queued D0 launch atomically enters `running` and reserves its fixed budget and one of three lifetime launch slots before compute; a process crash consumes that reservation permanently, while a linked terminal attempt cannot debit it again. Successful D0 moves directly to owner-owned `research_decision`, cannot admit typed D1 evidence, cannot claim `CONTRADICTED`, and cannot enter the generic corroborated-evidence ledger. The default evidence commitment allocates indivisible chronological eligible date/session/dependency groups 60/20/20; any alternative must be event-blind, owner-approved before D1, and retain D3 at 20% or more. The bounded MCP and matching strict REST/Cockpit operations can capture/get/propose/launch allowed approved D0 work/read status/report but cannot approve, reject, decide, consume D2, or run deep research; the generic REST job console also rejects governed research commands. Gate 1 uses synthetic 60-minute proxy data only. At that initial slice, production empirical D1/D2 was hard-disabled. ADR-0024 through ADR-0028 later admitted isolated source acquisition, qualified daily research data, governed D1/D2, tiered readiness, connected evidence views, and research-only modeling diagnostics. Licensed real intraday data, verified owner-presence authentication, the real-case pilot, and paper/order authority remain evidence-dependent; production, distribution, hosting, and multi-user readiness are out of scope.
**Research-first workstation program (2026-08-07)** — **design approved; R1-R5 implemented 2026-08-09; R6a-R6i implemented 2026-08-10 — the implementation scope is integrated and ADR-0021..0026 are Accepted; the private local implementation is complete; production, distribution, hosting, and multi-user readiness are out of scope.** R6i landed the program acceptance suite (`tests/integration/test_research_program_acceptance.py`): three spec-§17 composite end-to-end stories through the public CLI — the golden path (raw sentence with wording preserved → honest all-not_tested fresh scorecard/hub → governed D1 → one-shot sealed D2 → SUPPORTED → advance_to_strategy → terminal packet + passed gate → exactly one byte-identically retrievable promotion dossier → linked strategy version → AgentBrief embedding the exact recorded packet/gate-packet identities, with an unlinked version still refused after passing), SUPPORTED-with-reject closing honestly without any promotion dossier (gate stays open; both version paths refused), and a pre-D2 park that cannot claim SUPPORTED and closes with an honest NOT_TESTED terminal packet — plus the 2026-08-06 spec Gate-2/3/6 delivery-state updates (the owner pilot remains empirical validation; R-22 is retired for the permanent private/local-only scope). R6h landed the spec-§15 UI gate: while the linked project's recorded `research_gate_state` is `open`, the Develop desk disables immutable-version/experiment creation, stage prep/launch, and the Strategy Lab launch (`researchGateModel.strategyGateLock` + `useLinkedProjectGate`; the SPA relays the Python-authoritative state and never derives it, a failed projection read fails open because the CLI/store are the enforcing authority, and the Pipeline Data stage stays enabled — pulling point-in-time history is research work); every `ResearchGateLockNotice` states the reason and deep-links to the research case through a one-shot cross-desk signal (`context/researchCase.ts`) that switches to the research preset and focuses the cockpit; e2e covers gated vs grandfathered projects across all three surfaces plus the case link. R6g landed the recorded research-gate override plane (spec §15, ADR-0026): `ControlStore` derives `research_gate_state ∈ {not_required, open, passed, overridden}` strictly from governance, decision, and append-only override records (`record_research_gate_override` appends actor+reason events — never a mutable boolean — fails closed on grandfathered or already-passed gates, and a later pass supersedes and re-locks the override); an overridden gate is the only unlinked path through `create_strategy_version`; `alpha project override-research-gate` / `research-gate-overrides` are the trusted-local owner surface; project projections across CLI/REST/typed-MCP carry the state plus the bounded per-project override ledger (the generated matrix now owns the count); every strategy-run-producing command (`backtest run/oos/holdout/portfolio/cross-sectional`, `validate`, `optim grid`) accepts `--research-gate-override`, records manifest `research_gate {state: overridden, watermark: "EXPLORATORY / RESEARCH GATE NOT COMPLETED"}`, and includes the marker in run identity so a watermarked run can never collide with an unmarked identity-matched run; suite plans over an overridden project inject the flag mechanically and record `governance["research_gate"]`; `alpha report`, the web run index/detail (`research_gate_watermark`), the RunBrowser row chip, the run-story banner, and the native tear-sheet banner all render it (an e2e test asserts the ≥3-surface requirement on one desk), and the Operations desk lists active overrides via `GET /api/research-gate-overrides`; the SPA `researchGateModel.ts` relays the Python-authoritative string and never derives gate state. R6e landed the owner decision plane: `derive_research_checklist` answers the fourteen spec-§10.1 edge-validation questions strictly from recorded typed finding statuses (each row binds one evidence class; regime and economic-hurdle rungs stay honestly NOT_TESTED until their evidence classes exist; never a numeric aggregate), `research_decision_view_projection` + `ControlStore.list_research_decisions` assemble checklist + full scorecard + terminal gate packet (closed cases only) + append-only decision history behind `alpha research decision-view --json`, a read-only GET `/api/research/cases/{id}/decision-view` REST route (mutation-verb pin extended), and the ResearchCockpit Decision tab rendering all four blocks with the `researchChecklistModel.ts` TS twin drift-pinned by `__fixtures__/researchChecklist.json` asserted in BOTH pytest and vitest (same six scenario inputs as the scorecard fixture; e2e covers the closed-case tab). R6a-R6d (ADR-0026) landed the empirical confirmation lane: R6a registered the Gate-4 daily empirical exploration boundary (the `empirical_dataset` boundary authority binds the registered `rd_` dataset's exact content hash and seals the indivisible 60/20/20 session-group topology at draft time); R6b ran governed empirical D1 deep research on the registered daily lane; R6c landed `draft-confirmation` — the one-shot D2 contract is frozen MECHANICALLY from admitted clearing D1 evidence (one-variant primary event-study family, direction, minimum effect, frozen 0.05 familywise alpha / 0.90 target power; degenerate discovery intervals fail loud; the boundary hash must equal the exploration parent's); R6d admitted the live one-shot D2 after ADR-0026 acceptance: owner `approve confirmation` authorizes the sealed share (d2 sealed→authorized) and enters `sealed_confirmation`; the deterministic sealed executor (`research_d2.py`) re-verifies contract/boundary/data-hash alignment, materializes ONLY the confirmation share (a bias guard proves D3 rewrites never change a measurement), reads it exactly once with the protocol-frozen seed-7 weekday-matched cluster bootstrap, and publishes raw measurements plus mechanically derived `ResearchGateEvidenceV1` under a REGISTERED CONFIRMATORY watermark (ONE classifier serves write, store admission, and every read; producer flags never authority; INVALID is unreachable from evidence and exists only through contamination); success consumes D2 and routes to the owner decision bound to the mechanical classification (`advance_to_strategy` requires SUPPORTED); failures checkpoint honestly (initial attempt + two safe retries → blocked) and kill-and-resume recovers the identical immutable run; implementation drift or sealed-dataset integrity failure contaminates the share pre-read — registered snapshot payload files are fully re-hashed at every load (typed `DataError`, never a raw parquet crash) — leaving owner INVALID with revise/park/reject as the only exit. R6f landed the promotion plane: `build_strategy_promotion_payload` assembles the lossless spec-§11 dossier purely from authoritative records (decision row, HypothesisCard over the confirmation contract, terminal gate-packet id+hash, registered `rd_` dataset views with latest audits, latest-revision SCREENED literature claims, confounder ledger, falsification/stability/negative-control findings, known failure conditions, assumptions/limitations, exact content-addressed chart-data references from verified immutable runs, honest negative-attempt summary, open questions); `ControlStore._record_strategy_promotion_packet` commits it as a content-addressed `strategy_promotion` context packet INSIDE the `transition_research_phase(closed)` write transaction (the terminal packet exists only at close; decide-then-crash recovery replays decide idempotently and the single legal close records exactly one dossier; closed→closed is unreachable), packet inputs now bind only the immutable project identity (project_id/name/hypothesis/falsification_criterion/created_at) so post-promotion strategy-plane mutations can never drift the recorded terminal packet id/hash, `get_agent_brief_context` + `alpha project agent-brief` embed the as-of-filtered `research_promotion` reference (additive `AgentBrief.research_promotion` on REST + MCP typed models — the generated matrix now owns the count; a linked version without a dossier warns as pre-R6f), and thin Codex `strategy_promotion` packets additionally carry `promotion_packet_id`. R5 (ADR-0025) landed the pre-strategy experiment engine: four pure D1 analysis-family modules with future-poison bias guards; the `ResearchAnalysisPlanV1` contract section frozen and validated at exploration approval (registered families only, bounded grids capped by the variants budget, exactly one primary, frozen Holm/falsification multiplicity, blanket batteries rejected); the deterministic D1 executor publishing raw measurements + mechanically derived `ResearchGateEvidenceV1` + EXPLORATORY charts strictly from the discovery share (a bias guard proves confirmation/holdout bars are never read); governed `alpha research run deep` durable jobs (reserved `research:event-study` heavyweight capacity via `ControlStore.create_research_job`, heartbeat checkpoints, cancellation, honest failure checkpoints, exact-re-execution resume with identical hashes); store admission that re-verifies D1 evidence by exact recomputation from raw measurements on every write AND read (post-admission rewrites fail closed); acceptance fixtures (planted-pattern recovery, planted-weekday-confounder rejection via exact matched controls, null-stays-null after Holm, honest insufficient-events packets); the Gate-4 Tiingo-daily fallback lane (fail-closed registered-dataset loading with ADR-0020 session/equal-duration acceptance; QuantPad intraday stays licensing-gated); live Evidence Hub/scorecard from admitted D1 evidence (sixth drift-fixture scenario pinning both scorecard twins), the HypothesisCard analysis-plan display, and the six-category headline board; and the scoped admission of `deep_research` attempts only (confirmation approval and all D2 transitions remained behind the later R6 gate). R4 (ADR-0024) landed the source plane: append-only `research_source_claims` (content-addressed `sc_` ids, direction/strength/method/sample/limitations, draft→screened only via owner CLI `sources claim screen`; screening appends a revision, never mutates the draft), typed `doi`/`year`/`authors_json` columns on `research_source_records` (idempotent column heal for pre-R4 stores; identity backward-compatible), token-AND local `sources search`, the isolated **stdlib-only** literature worker (`workers/literature`, own uv.lock, vendored acquisition primitives byte-pinned to `research_acquisition.py` by a repo test, manual-redirect fetch re-validating every hop, content-addressed UNTRUSTED_SOURCE objects, tamper-detecting `verify_object`, and the phase-gating hostile-document suite incl. verbatim-stored prompt-injection text), the owner-invoked `sources fetch` driver, bounded MCP source tools (search/get sources and agent-authored draft_source_claim; screening has NO tool), the scorecard literature dimension now aggregating screened claim directions (supporting/mixed/contradictory/insufficient; drafts never count; TS twin + fifth drift-fixture scenario), and the live Evidence Hub literature section (claims map with SCREENED vs DRAFT—UNSCREENED badges above the bibliography). R3 (ADR-0023) landed the Research Data Hub: `alpha data snapshots --json`; fail-closed `research_dataset_refs` (+`research_dataset_audits`) with content-addressed `rd_` refs bound to exact snapshot-manifest/provenance/receipt bytes; pure `alpha_research.descriptives` (bias-guarded causal regime tags); the bounded `research_data_audit` EXPLORATORY run class whose findings feed only the scorecard/hub data dimension (proved by test); the research-only QuantPad daily adapter sub-slice (pinned wire schema fails loud on drift; provider `research_bars`, never in `data pull`); bounded read-only MCP data-inventory tools (candle previews bounded to ≤500 bars); a `GET /api/research/datasets` read route; and the ResearchDataExplorer panel (refs·receipts·audits·inventory) on the research desk. R1 landed the ADR-0021 read plane (`ControlStore.list_research_cases` + `alpha research list/evidence-hub --json`, additive `hypothesis_card`/`scorecard` status keys, three read-only REST routes with a negative test pinning the research router to exactly the three Gate-1 POSTs), the pure HypothesisCard/scorecard/evidence-hub projections, the dual-implementation readiness scorecard (Python + `researchScorecardModel.ts`, drift-pinned by a fixture asserted in both pytest and vitest), the seventh `research` desk (ResearchBacklog · ResearchCockpit · EvidenceHub) and the New Idea front door with an e2e-asserted absence of trading-rule inputs. R2 (ADR-0022) landed the Codex collaboration surface: append-only `research_context_packets` (content-addressed `cp_<sha256>` over canonical payload bytes, bounded collections with truncation flags, heal-path DDL) and `research_case_notes` (structurally outside `research_gate_packet_inputs` — byte-identical before/after, proven by test), the "Resume with Codex" delta brief with history cursors, the Git-owned 13-protocol library (`.agents/skills/alpha-research-protocols/` + hash-verified `protocols.json`; drift fails loud), CLI `context build|show|list` · `note add|list` · `protocols list|show` · `brief`, bounded MCP collaboration tools (notes forced agent-authored), four read-only REST routes, and the CodexBench panel (packet composer that prepares-but-never-records, byte-identical packet history, notes fenced "CODEX COMMENTARY — NOT EVIDENCE"). Mutation authority and the dossier-embedded summary bytes were unchanged in R2; D1/D2 were admitted only later under ADR-0025/0026. The master spec (`docs/superpowers/specs/2026-08-07-research-first-workstation-design.md`), ADR-0021..0026 (Accepted), and phase plans R1-R6 define the extension: a Research Command Center desk with read-only backlog/evidence-hub/scorecard projections (R1), a Codex context-packet/protocol desk over MCP (R2), MCP data-inventory tools plus research dataset registration and a QuantPad qualification lane (R3), a claim-level literature system with an isolated acquisition worker (R4), preregistered-analysis-plan D1 runners emitting `ResearchGateEvidenceV1` (R5), and one-shot D2 confirmation, readiness scorecard, promotion packets, and a recorded/watermarked exploratory research-gate override (R6). Codex remains the sole in-product research AI (MCP-attached, no API key in-app); owner-only approve/reject/decide stays trusted-local CLI, the generated matrix owns the current MCP count, and every authority flip (empirical D1 at R5, one-shot D2 at R6d) landed only with its phase's ADR.
**2026-08-07 independent audit + hardening** ✅ — a six-reviewer read-only audit of the complete program found 0 critical/high and 7 medium findings; all were fixed test-first on `codex/research-improvements` (PR #36): write-free steady-state store opens with a read-only schema probe, left-pivot-window knowledge time, numeric `confirmation_claim` binding for TESTED D2 evidence, explicit generation-mismatch errors with a documented fixture-version bump policy, a 120s MCP launch-class timeout, ledger-honest attempt recording with an executed resume/re-run recovery, typed 4xx for option-shaped web path values, `low_cluster_count` flags below ten effective clusters, a 10% holdout observation-share floor, an exactly pinned 48-tool MCP surface, golden-pinned content-identity digests and dual canonical-JSON conventions, and byte-neutral deduplication of the revise-reuse/bootstrap/D0-measurement logic. Gates re-verified on the branch head: 1,794 offline tests, 93.03% coverage (93.0% floor), strict mypy across 389 files, 13/13 import contracts, 12-wheel build/import smoke, and the full frontend gate including Playwright e2e.
**Workstation v4 — server-rendered figures + information architecture (2026-08-07)** — the charts became Python, and the shell stopped being furniture. **Figure engine:** a declarative `FigureSpec` in `alpha_research/figures/` that the renderer cannot add to (it draws, it never computes) plus 23 catalogued figures built in `alpha_cli/figures/` from immutable run artifacts — equity/underwater, strategy versus the passive price index, rolling risk as three small multiples rather than a dual axis, monthly heatmap, return distribution and Q-Q, trade P&L, holding periods, exposure/turnover, top-5 drawdown episodes, the causal price/signal chart drawn from `chart_annotations` and `indicator_series`, null distributions, fold strips, CI forests, optim surfaces and trial curves, portfolio weights/correlations/contributions, prop-firm outcomes and funnel, forecast fan/skill/calibration, and ML prediction-versus-realised. Every figure carries the question it answers, its uncertainty and its caveat as required fields, so none ships without the text that makes it readable. Output is byte-stable across fresh processes under a hostile `matplotlibrc`, either `PYTHONHASHSEED`, and three timezones. Figures render to a **derived cache** (`data_dir/figures/`), never into run directories: `ARTIFACT_CONTRACT_VERSION` stays at 3, `verify_manifest_artifacts` still passes after rendering, and a v1 run from months ago renders as well as one produced today. `alpha_web` serves them with a content-addressed ETag and never imports matplotlib or `alpha_research`. **IA:** free-form docking is retired in favour of six purpose-built screens (Explore · Build · Results · Compare · Studios · Operate), a persistent Library rail, and one context chip replacing five top-bar controls; a workspace is now a saved research context rather than saved window positions, and Compare finally calls the run-comparison endpoint that had existed since v3 with no caller. uPlot, Dockview and 14 hand-rolled SVG chart components are gone (bundle 1,200 kB → 730 kB). Contrast is enforced mechanically: `--muted` must clear AA on the lightest surface it can land on, and `--faint` may never colour text.
**Full repair program Stages 0–5 (2026-08-13)** ✅ — every empirical Workstation launch now requires a server-resolved `RunContextV1`: governed projects fail closed on open/unreadable gates and standalone work is identity-bound and manifest-watermarked `STANDALONE_UNQUALIFIED`; missing-context history projects as `LEGACY_CONTEXT_UNKNOWN` without rewrite. Generic jobs reject owner-only research/project/evidence/data-repair/paper commands. REST and SSE entry points share redacted `ApiErrorV1`; comparison never invents a preference for ties, zero-trade, partial, or single results; legacy journal assertions cannot pass paper readiness; and the literature child has a minimal credential-free environment plus fixed argv/host/resource bounds. Stage 1 preserves the real three-question object contract end to end, exposes Python-authoritative atomic proposal bundles/packs/qualified datasets/blockers/revision, makes the recommendation executable by construction without guessing ambiguous ideas, caps and versions AR(1) effective sample size, writes compact exact-membership `ResearchD2BoundaryV2` while preserving V1 bytes, and normalizes/validates arXiv PDF acquisition. Stage 2 keeps the six screen IDs while presenting Research as the front door, defaults to per-project Guided mode, separates the permanently unqualified sandbox, uses one project workspace context with stale-response guards, exposes canonical recovery actions, distinguishes bound/global research data and standalone/legacy run history, and adds a server-authoritative ML preflight. Stage 3 canonicalizes WebAuthn to `http://localhost:8801`, adds exact-backup schema-v3 credential/challenge/receipt persistence, keeps enrollment and recovery behind trusted `alpha owner-auth`, and requires a fresh single-use Touch ID assertion bound to the exact project, artifact, case revision, consequence, reason, and payload for every closed research-lifecycle Workstation action. Stage 4 adds bounded explicit scholarly discovery, direct-PDF acquisition, `pypdf==6.14.2` extraction, immutable `ResearchDocumentTextV1`, reverified `SourceAnchorV1`, cited `ResearchRecommendationV1`, bounded MCP excerpts, and a guided Literature UI. Document text and Codex recommendations remain untrusted/draft-only; Touch ID alone screens claims and freezes packs. Stage 5 separates provider configuration, explicit verification, and granted capability; stores redacted content-addressed `ProviderCheckReceiptV1`; provides a one-item Keychain launcher and owner-clicked Tiingo/QuantPad/IBKR checks; replaces journal assertions with plan-bound hash-chained `PaperAcceptanceV2`; and provides an offline redacted `IBKRWhatIfPlanV2` plus explicit one-shot executor. The executor uses IBKR's required wire `transmit=true` only with `whatIf=true`, verifies no broker order/fill or position change, and grants no paper-readiness credit; V1 plans remain readable but non-executable. Advanced mode, MCP, generic jobs, and excluded gate/holdout/paper/broker/order actions gain no authority. Stage 6 remains pending; this line does not claim the seven-stage program complete.
**Crypto Data House Stages 0–6 (2026-08-15)** ✅; **Stage 7 acceptance** 🚧 — family-scoped authority and the external-bulk/internal-control boundary are governed by ADR-0032. Additive immutable crypto contracts, fail-closed Expansion UUID/capacity publication, native Binance history, and Bybit public derivatives/options are implemented without changing legacy CCXT bytes or execution authority. Stage 4 adds point-in-time network-plus-contract identity (ticker joins prohibited), explicit native BTC/ETH mappings, bounded CoinGecko Demo market/reference ingestion with Keychain-only process injection, separate keyless GeckoTerminal pool/OHLCV/trade ingestion, and reviewed Coin Metrics Community catalog/timeseries ingestion. Contract-capable asset masters are content-addressed over ordered identities and exact qualified CoinGecko/GeckoTerminal source manifests; non-legacy snapshots reverify them before use, while `reviewed-native-v1` remains byte-compatible. The fixed Keychain `catalog` and `reference` actions and guided Workstation flow require no secret or opaque-ID copying. Coverage profiles bind an exact qualified Coin Metrics Community catalog and schedule on-chain metrics only from its point-in-time rows, so unavailable paid metrics cannot be advertised. Stage 5 adds provider-native mechanical qualification, non-substituting Coinbase/Bybit divergence diagnostics, provenance- and availability-bound funding/basis/OI/volatility-surface/liquidity/on-chain features, and exact snapshot research-eligibility revalidation. Stage 6 provides the guided Crypto Data Center and the same fail-closed contracts in Advanced mode. Stage 7 is complete only after the current branch passes every three-viewport, live-provider, offline-replay, tamper, secret-redaction, V1 compatibility, wheel, documentation-truth, and GitHub check on the exact publication SHA. Warning, quarantined, future, uncommitted, missing, or wrong-authority inputs fail closed; CoinGecko metadata/reference data remains supplemental and cannot satisfy validation or execution-price requirements.
**Crypto Data House Bybit live acceptance (2026-08-15)** ✅ — the Expansion UUID verifier now resolves the containing macOS mount point before invoking `diskutil`, preserving the substitution check for nested bulk roots. Bounded credential-free live runs qualified BTCUSDT perpetual funding/OI/holder-ratio/trade/mark/index/premium bars, recent executions, an exact order-book snapshot, complete spot/linear/inverse/option instrument catalogs, and exact-USDT BTC option catalog/chain/historical-volatility datasets. Point-in-time acquisition uses network completion—not request start—as the local knowledge clock. Derivative trades and books require an existing research case, its exact fresh revision, and a bounded reason before any network request; the revision is rechecked after fetch, and the immutable normalized manifest records `CryptoAcquisitionScopeV1`. Legacy unscoped event artifacts stay readable but cannot enter a new or reverified governed snapshot. Catalog snapshot `9befa772…f96e9` and scoped market snapshot `3e07234a…92187a` replayed with provider networking disabled. A fresh post-fix run now requires the truthful `option` category at both CLI and UI boundaries; its 14-member complete-catalog/perpetual/options snapshot `05ab9509…dd98` reverified offline as research-eligible. Live discovery also proved that dated futures may report a zero funding interval, premium-index tuples cannot use ordinary positive-price OHLC assumptions, and point-in-time cross-sections legitimately share an observation timestamp; exact quote filtering prevents USD/USDT relabeling. Earlier wrong-quote, future-clock, or unscoped-event artifacts remain immutable and outside eligible evidence. This grants no execution authority and does not complete Stages 6–7.
**Crypto Data House guided-control checkpoint (2026-08-15)** ✅ — the Workstation now has a typed Crypto Data Center inside Research Data for family-authoritative coverage, bounded estimates/acquisition jobs, mechanical quality, exact qualified snapshot freeze/verification, asset identity, fail-closed storage status, and explicit research-only snapshot registration. Registration re-verifies every external member, derives range/frequency from immutable qualifications, preserves the historical strict research-store schema through `dataset_kind=snapshot` plus `snapshot_schema=CryptoSnapshotV1`, and never makes an incompatible proposal operator available. Guided mode hides opaque manifests and shows one canonical next action; Advanced exposes receipts/commands without gaining authority. Registration refreshes render explicit registered-dataset and stored-symbol loading states instead of briefly presenting empty inventory. Bybit bounded OI and holder-ratio ranges now honor paired ISO timestamps and follow cursors with repeated-cursor and 100-page guards. Every successful page is frozen as separate exact provider bytes before parsing, and the normalized artifact commits to all ordered raw manifests. Non-cursor history fails closed when one bounded response reaches its provider limit, rather than claiming silently truncated coverage. A real two-page BTCUSDT hourly-OI acquisition produced 241 qualified observations across the exact inclusive 2026-08-04 through 2026-08-14 UTC window; its frozen snapshot reverified as research-eligible with all provider networking disabled and registered as `rd_2137ba…60d1`. Three-viewport Playwright coverage holds the guided journey, accessibility, and zero horizontal overflow. Research proposals may bind only an already registered compatible dataset operator; this data subsystem does not invent a strategy or empirical operator.
**Governed BTCUSDT crowding research extension (implemented 2026-08-15; owner pilot pending)** 🚧 — ADR-0033 freezes the registered `bybit_btcusdt_crowding_reversal_v1` research bundle and sandbox-only `hedged_basis_crowding_v1` development candidate. Proposal preflight offers the bundle only for one exactly compatible registered `CryptoSnapshotV1`; submission and launch reverify the snapshot, asset master, qualification versions, case revision, source pack, and evaluator fingerprint. The evaluator preserves exact Bybit linear BTCUSDT/USDT identity, causal funding/OI/premium/mark/index availability, the group-atomic 60/20/20 boundary, one-shot owner-authorized D2, and an `INCONCLUSIVE` result when the effective-event minimum is absent. Deterministic planted, null, confounded, future-poisoned, missing, corrected, and insufficient-sample D0 scenarios are mechanically rerun. The two-venue fixture preserves both legs, funding, 40 bp costs, 365-day annualization, and exact lineage through the complete pre-paper suite; it grants no credential, paper, broker, or order authority and stops at `UNSUPPORTED_MULTI_VENUE_PAPER`. The real owner pilot remains incomplete until lawful literature is anchored and owner-screened, the source pack is frozen, exploration is approved, and any mechanically eligible D2 receives a separate fresh owner action; no agent may perform those actions.
**Crypto branch simplification and local acceptance (2026-08-15)** ✅ / **publication and owner pilot** 🚧 — branch-owned acquisition, analysis/artifact, coverage-batch, Workstation acquisition-view, and candidate-suite hotspots have behavior-preserving private seams; exact V1 bytes, public commands, manifests, errors, and authority boundaries remain stable. The current local gate passed 3,395 non-network tests at 93.02% coverage, 128 bias guards, 6 live-network tests with one documented provider skip, 166 frontend tests, 83/83 Playwright cases with zero skips at all required viewports, 29 literature-worker tests, 14 Qlib-worker tests, all 13 wheel import/version assertions, OpenAPI classification/freshness, and Expansion verification over 372 manifests and 14 snapshots. CoinGecko and Tiingo are verified. On 2026-08-18, the official signed/notarized local IB Gateway was installed, its paper endpoint and a masked DU account were read-only verified; Docker is no longer a prerequisite for that local installation mode. QuantPad REST is separately live-verified and exact-byte archiving is research-only. Publication still requires the Unpaywall contact email, separately checkpointed IBKR what-if/market-data evidence, fresh owner research actions, independent review, and green GitHub checks on the exact publication SHA. See `docs/audit/2026-08-15-crypto-branch-acceptance.md`; this checkpoint grants no gate, holdout, paper, broker, or order authority.
**Crypto Data House final live acceptance (2026-08-15)** ✅ — the scoped Keychain launcher verified CoinGecko and qualified the exact contract catalog plus a 64-page USD market-reference universe after live fixtures exposed and test-first fixes covered provider-null platform fields, lowercase boolean query encoding, mixed numeric wire types, and cross-page asset movement. Asset master `b3e1f270…7b449` rederived 13 identities from exact qualified CoinGecko and GeckoTerminal inputs, including reviewed BTC/ETH native mappings and exact-contract USDC resolution. Multi-provider snapshot `097607bd…79fce` freezes 12 qualified families across Binance, Bybit, Coinbase comparison, CoinGecko, Coin Metrics, and GeckoTerminal; it reverified offline as research-eligible for market bars, funding, OI, options, on-chain, and DEX data while retaining `execution_authority=false`. Exact-input funding, OI-change, basis, volatility-surface, liquidity, and on-chain features were frozen separately. Expansion verification covered 372 immutable manifests, 14 snapshots, one asset master, zero private-path exposure, and zero credential/header/service-name sentinels in manifest JSON. Failed and warning acquisitions remain immutable non-evidence rather than being rewritten.
**Crypto external-storage operational checkpoint (2026-08-15)** ✅ — `storage-inventory` reports immutable kind/byte counts, snapshots, staging, and removable cache without absolute paths; `storage-verify` re-hashes every external artifact and rederives every frozen snapshot membership; `cache-clean` requires `--confirm` and can delete only `bulk/cache`. The guided Storage & Jobs UI provides inventory, full verification, and a two-step cache confirmation with the immutable-exclusion boundary visible. Real Expansion verification passed for 31 manifests and four frozen research-eligible snapshots with zero staged downloads and zero cache bytes; no cleanup was executed because nothing was removable.
**Crypto independent-comparison checkpoint (2026-08-15)** ✅ — `comparison_bars` now has an executable `ccxt:coinbase` acquisition path at 1m/5m/1h/1d and an explicit CLI-only Bybit spot diagnostic path. Both preserve exact venue/base/quote/frequency identity; Bybit diagnostic bars are deliberately rejected from snapshots because Coinbase remains the one declared comparison-family authority. `alpha crypto-data compare` requires an authoritative Binance primary plus exact-identity comparison manifests, retains every venue close, and publishes a content-addressed derived diagnostic with warning/quarantine thresholds, no fallback, and no execution authority. A live BTC/USDT hourly comparison over 2026-08-14 matched 38 observations across Binance, Coinbase, and Bybit with 5.91 bps maximum divergence and froze qualified comparison manifest `5838f82b…243a8`.
**Crypto reference-catalog pagination checkpoint (2026-08-15)** ✅ — `coingecko market_reference all` freezes ordered 250-row Demo pages through the first short terminal page, with a 100-page safety ceiling and no false single-base identity. GeckoTerminal `dex_pools` freezes exactly five 20-row pages for each of Arbitrum, Base, BNB Chain, Ethereum, and Solana; incomplete pages fail before publication. Live breadth exposed public 429s, so the keyless client now applies proactive 2.1-second page pacing plus bounded exponential 429 backoff, while failed batch projections display the safe provider/data blocker and retain completed members for exact resume. The five-network batch then completed without overwriting its earlier pages: Base, BNB Chain, and Ethereum remained warnings; Arbitrum and Solana were quarantined for duplicate/invalid observations. These are honest quality outcomes, not provider-readiness failures or qualified evidence. Remaining Stage-7 gates are still pending.
**Crypto Community-catalog checkpoint (2026-08-15)** ✅ — Coin Metrics coverage no longer trusts a hard-coded metric list. A supplemental `onchain_catalog` family freezes the exact paginated Community catalog, commits to each cursor without recording raw cursor text, and supplies only its point-in-time BTC/ETH daily metric membership to `CryptoCoverageProfileV1`. The live schema required four 1,000-row pages to remain below ALPHA's 16 MiB response bound; the resulting qualified catalog produced a fresh 7,603-task profile. Its exact three-task Community batch qualified the catalog and BTC observations while honestly retaining an ETH `missing_onchain_value` warning. The 16 MiB bound was not weakened, and catalog evidence remains supplemental rather than market-price or execution evidence.
**Crypto default-coverage profile and batch checkpoint (2026-08-15)** — `alpha crypto-data profile-create|profile-show|profiles` freezes and paginates a content-addressed, non-authoritative acquisition plan from exact qualified Bybit linear/inverse/option catalogs, complete option-chain OI sources, and exact qualified Binance spot/USD-M/COIN-M membership. Current profile `79f1c9d5…ee83a` contains 7,602 tasks: 803 active Bybit perpetuals and 1,961 active Binance spot/perpetual markets, plus public reference/catalog, hourly option, and one five-minute BTC option tier. Dated/future contracts are excluded point-in-time; missing option-OI or venue-membership coverage fails profile creation. Binance provider symbols preserve bounded Unicode identity and use percent encoding only at archive URL boundaries. Every daily Binance task requests only the previous complete UTC day; a live profile batch qualified exact BTCUSDT spot membership and its prior-day bar. `liquidity-freeze` refuses incomplete, future, conflicting, cross-quote, or cross-unit inputs; it freezes at most 250 instruments per exact spot-USDT, USD-M-USDT, or COIN-M-USD scope and the next profile uses those receipts for previous-complete-hour tasks. Current live profile truthfully reports all three hourly scopes missing until the 1,961-member prior-day cycle completes. `profile-select-one-minute` separately requires a current research case/revision, bounded reason, and 1–50 exact `category:symbol` daily members; it freezes the selection receipt, rechecks case freshness, and schedules only the previous complete hour. `profile-run|profile-resume|profile-batches` execute explicitly confirmed cadence slices of at most 25 tasks from an immutable plan, checkpoint each completed normalized manifest atomically, reverify frozen sources and exact task membership, reject tampering, and retry only unfinished membership. Fresh Bybit 14-member snapshot `9431f968…c6fa79` reverified as research-eligible with networking forced offline. Profiles and batches grant no research, paper, broker, or order authority.
**Crypto derived-feature persistence checkpoint (2026-08-15)** — the six Stage-5 feature families now publish exact deterministic Parquet bytes through a content-addressed `CryptoFeatureArtifactV1` manifest instead of remaining transient frames. Every create/show/list operation re-verifies the feature bytes, expected named input set and order, top-level lineage IDs, each qualified normalized source and exact artifact hash, availability, and method identity. CLI and REST expose the same closed feature enum. The Guided Crypto Data Center derives inputs only from human-selected compatible qualified datasets, reports missing or cross-identity blockers without requiring opaque IDs, and lists frozen features; Advanced shows the same command and hashes without additional authority. Features remain non-authoritative research inputs beside an exact snapshot and cannot change a gate, paper state, broker, or order path. Stages 6–7 remain pending.
**Crypto guided acquisition-control checkpoint (2026-08-15)** — the Storage & Jobs view now projects immutable profile summaries and filtered 25-task cadence pages through typed REST/TypeScript contracts, starts provider work only after one explicit bounded click, and resumes only failed content-addressed batches. It exposes human-readable task identity, counts, progress, and recovery without requiring manifest or task IDs. The same view freezes an exact prior-day Binance top-liquidity scope and offers paginated selection of at most 50 daily-member markets for a fresh case-revision-bound one-minute profile; cross-paired spot/linear/inverse quote scopes, future profile clocks, stale case revisions, and stale async profile pages fail closed. Critical guided acquisition/feature/snapshot/storage behavior passes at 1280×720, 1440×900, and 1920×1080 with accessibility and horizontal-overflow assertions. This completes the planned Stage-6 control surfaces, but Stage-7 exhaustive acceptance and remaining real-network breadth are still pending.
**QuantPad external research access (updated 2026-08-18)** — the current REST contract is live-verified; owner-attested written permission is the private-retention basis. `alpha quantpad-data archive` streams exact symbol-scoped responses to UUID-pinned external storage and publishes content-addressed internal manifests last. The provider exposes no complete universe export, so coverage is an explicit backlog and never guessed. All artifacts remain research-only—not canonical, validation, paper, or execution authority—until separately qualified (ADR-0018).

**Generic study composition architecture freeze (2026-08-21)** ✅ — ADR-0035 accepts
`alpha-study` only as a future composition/projection layer over the existing governed research
program. The authority map preserves the current ControlStore, immutable D0/D1/D2 artifacts,
owner-only D1 launch, one-shot D2, Touch ID, strategy-promotion firewall, 62-tool MCP pin, existing
Qlib worker, figure engine, and six-screen Workstation. S0/S1 add documentation only; package and
runtime behavior begin in later independently verified slices. Every third-party capability remains
subject to its own ADR-0011 evidence gate, and this checkpoint grants no provider, paper, broker,
order, holdout, or execution authority.

**Generic study composition S2 package seam (2026-08-21)** ✅ — the additive `alpha-study`
workspace package now has versioned metadata, a `py.typed` marker, and no runtime composition
behavior. `alpha-cli` declares the workspace dependency; root isort/coverage awareness and the
15-contract import-linter boundary enforce the approved research-plane inputs and bidirectional
exclusion from lower layers and top surfaces. CI and the canonical gate now build/import 14
wheels. Independent Terra reviews cleared both delivery findings; focused documentation, awareness,
and seam tests pass (`51 passed`), all 15 import contracts are kept, and the canonical full gate
passes the complete non-network suite with coverage, OpenAPI freshness, 14 wheel builds, and exact
wheel import smoke. No canonical contracts, persistence, CLI command, UI, external dependency,
owner/D1/D2, promotion, paper, broker, or order authority was added.

**Generic study composition S3a1 feature-lineage contracts (2026-08-21)** 🚧 —
`alpha-study` now defines strict immutable feature-input/value lineage. Canonical identities
content-bind UTC semantic clocks and non-empty multi-artifact, snapshot, vintage, computation,
provider, family, frequency, and explicit venue references; every lineage is permanently labelled
`unverified_reference` until the existing-authority verifier checks it. Operational timestamps are
absent. Focused seam/lineage tests pass (`12 passed`); event/factor table and cross-process
determinism completion remain pending in S3a2. These projections grant no evidence, approval,
D1/D2, promotion, paper, broker, order, persistence, CLI, MCP, web, or provider authority.

**Generic study composition S3a2 observation tables (2026-08-21)** ✅ — `alpha-study`
adds sealed `EventRowV1`/`EventTableV1` occurrence geometry and a separate
`FactorObservationV1`/`FactorObservationTableV1` cross-sectional geometry. Event clocks,
operator/code/parameter fingerprints, source availability, and factor universe availability are
content-bound; row/table order and IDs are canonical. All lineages remain
`unverified_reference`, every table declares `authority: none`, and event schemas reject realized
outcomes. Focused study tests pass (`22 passed`), the environment-perturbed determinism gate passes,
and the canonical full gate passes complete pytest/coverage, OpenAPI freshness, 14 wheel builds, and
exact wheel import smoke. No authority surface changed.

**Generic study composition S3b authority references (2026-08-21)** ✅ — `alpha-study`
now publishes one closed Git-owned declaration of the existing causal double-bottom operator plus
strict `DetectorValidationV1` and `ExplorationMandateV1` projections. The projections bind current
ControlStore/run identity shapes (`rc_`, `ra_`, 16-hex D0 run, `rl_`, SHA-256 execution
fingerprints, and exact `d0_acceptance.json`) and hash-bind frozen D1 inputs and child references.
They are explicitly `not_checked`/`not_attested`, create no D1 reservation, and expose no launch,
approval, budget mutation, or verdict authority. Focused study tests, strict typing, all 15 import
contracts, perturbed-environment golden determinism, fast gate, and independent Terra review pass;
the canonical full gate passes complete pytest/coverage, OpenAPI freshness, 14 wheel builds, and
exact wheel import smoke.

**Generic study composition S3c derived projections (2026-08-22)** ✅ — `alpha-study`
adds strict content-hashed `FindingV1`, `MechanismGraphV1`, `AdvisorProposalV1`, and
`StudyWorkspaceManifestV1` projections. Findings copy only registered typed D1/D2 fields with
field-specific statuses and exact evidence provenance; graph node and edge vocabularies enforce
source-kind semantics; advisor actions are closed non-executable recommendation codes; workspace
collections enforce exact reference kinds and contain no raw data or mutable authority. All objects
remain `authority: none` and `verification: not_checked`. Focused study tests, strict typing,
perturbed-environment golden determinism, fast gate, and independent Terra review pass; the
canonical full gate passes complete pytest/coverage, OpenAPI freshness, 14 wheel builds, and exact
wheel import smoke.

**Generic study composition S4 double-bottom parity (2026-08-22)** ✅ — the first generic
vertical calls the existing `detect_double_bottom_events` source of truth exactly once and projects
its geometry into content-hashed `EventTableV1` rows. The adapter binds the closed registry, frozen
parameter hash, exact artifact/dataset hash, provider/frequency/venue lineage, and the detector's
full causal availability clock. Tests reproduce the registered 60-minute `d0-planted`,
`d0-monotonic`, and `d0-single-trough` identities and 1/0/0 results; future-append, delayed-input,
must-fail leaky-twin, round-trip, and perturbed-environment golden guards pass. The existing D1
confirmation-bar mapping can precede full causal knowledge under delayed earlier inputs, so an
`EventStudyObservation` bridge is explicitly deferred rather than introducing look-ahead. The
198-test study+bias suite, strict typing, all 15 import contracts, fast gate, and independent Terra
review pass. The canonical full gate passes complete pytest/coverage, OpenAPI freshness, 14 wheel
builds, and exact wheel import smoke.

**Generic study composition S5 scope hardening (2026-08-22)** 🚧 — independent Terra review
found that the combined semantic slice could not truthfully use an “existing” owner semantic action:
the control store remains schema v4 and the CLI, database, and web owner-action vocabularies are
closed without a semantic label/freeze action. ADR-0035 and the FeaturePlan now split delivery into
S5a read-only masking at the mechanically recomputed `d0_acceptance.json` event cutoff after exact
identity/clock agreement with integrity-checked `events.json` and `chart-data.json.events`, S5b
additive exact-backup SQLite v5 semantic definition/review events with action-bound Touch ID receipt
and case-revision binding, and S5c presentation inside the existing Research screen. This hardening
changes no runtime,
schema, owner authority, MCP tool, D1/D2, promotion, paper, broker, or order behavior; S5a remains
the next implementation slice.

**Generic study composition S5a1 blind-read contract (2026-08-22)** 🚧 — `alpha-study` now
publishes a strict byte-bound `BlindSemanticProjectionV1`. The pure builder hashes the complete D0
acceptance, events, and chart artifacts internally; rejects duplicate JSON keys, missing/extra
events, cross-artifact identity/clock disagreements, nonnumeric chart values, inconsistent
dataset/protocol/series lineage, and noncanonical visible-point collections; and emits only points
available by the acceptance-event cutoff plus an aggregate masked count. The cutoff source remains
an explicit acceptance-measurement reference with `lineage_verification: not_checked`: existing CLI
mechanical D0 verification is now composed by the S5a2 read slice; server projection, persistence,
owner semantic actions, and UI are still pending. Focused semantic tests, the study+bias suite, strict typing, all
15 import contracts,
perturbed-environment determinism, fast gate, and independent Terra review pass. S5a remains in
progress until server projection and the later protected persistence/semantic-action slices land.

**Generic study composition S5a2 boundary freeze (2026-08-22)** 🚧 — the next read slice is
split from web delivery. A narrow ControlStore resolver will reuse the existing completed-D0
mechanical verifier, then return only bounded acceptance/events/chart bytes after rechecking their
hashes against the verified manifest. This verifier may recompute the registered synthetic fixture;
the pure `alpha_study` projection still never imports or calls a detector. The CLI response is frozen
as `VerifiedBlindSemanticReadV1`: an outer verified-source envelope around the unchanged inner
`BlindSemanticProjectionV1`, with no operational timestamp or mutation authority. REST delivery is
deferred to S5a3. This planning refinement changes no runtime, database, owner action, MCP, D1/D2,
promotion, paper, broker, or order behavior.

**Generic study composition S5a2 verified semantic read (2026-08-22)** 🚧 — implemented as a
read-only CLI composition. `ControlStore.verified_blind_semantic_artifacts` resolves the active
exploration lineage (including a confirmation parent), requires the single registered
`double_bottom` completed D0 pilot through the existing mechanical verifier, and returns only
bounded `d0_acceptance.json`, `events.json`, and `chart-data.json` bytes after a post-read manifest
recheck. `alpha research semantic-projection PROJECT_ID --json` wraps the unchanged
`BlindSemanticProjectionV1` in the exact seven-key `VerifiedBlindSemanticReadV1` envelope with
`verified_completed_d0_recomputation` and no authority. Focused envelope, integration, future-poison,
leaky-twin, race/tamper, no-write, and MCP-surface tests pass. The D0 runtime now delegates its
existing canonical/identity/mechanical acceptance checks to exact in-memory bytes after binding;
detector, fixture, estimator, power, and other quantitative semantics are unchanged. REST/UI,
semantic writes, and owner actions remain deferred to later S5 slices. Independent Terra review
passes; S5a2 is complete and S5a3 remains pending.

**Generic study composition S5a3 web projection (2026-08-22)** ✅ — the web slice is fixed as
`GET /api/research/cases/{project_id}/semantic-projection`, with no query or body input and only the
existing CLI command as its source. Strict nested server models preserve the exact seven-key outer
envelope, fourteen-key inner projection, and three-key points; the web layer does not recompute
hashes, cutoff, masking, or detector semantics. CLI unavailability maps to 404 and structurally
invalid parsed CLI output to a redacted 502. Only generated OpenAPI/types and operation-governance
records may change; handwritten frontend client/types, presentation, mutations, jobs, owner actions,
MCP, D1/D2, promotion, paper, broker, and order surfaces remain unchanged. The exact-argv
subprocess adapter and strict frozen response models are implemented; malformed parsed output is
redacted at 502 and CLI unavailability at 404.

The S5a2 envelope is now frozen to exactly seven keys (`schema`, `schema_version`,
`source_verification`, `authority`, `run_id`, `projection`, and `content_sha256`), with explicit
`authority: none` and a self-excluding canonical hash. Selection is limited to the unique completed
pilot attempt on the current active exploration lineage; a confirmation case resolves through its
exploration parent. The future-poison invariant compares only cutoff and emitted pre-cutoff point
semantics because the source hash and aggregate masked count are expected to change when future
data is appended. This clarification is planning-only.

**Generic study composition S5b semantic owner-event delivery (2026-08-23)** ✅ — the bounded S5b
implementation is delivered across `5fd3d02`, `07d48bb`, `3f18f4c`, `9ca9377`, `c72b9ee`,
`6804db5`, `40861b6`, and `f935744`.
The CLI-owned ControlStore now opens at schema v5, with the exact v4 backup and lossless
`owner_action_receipts` `CHECK` rebuild, protected append-only `research_semantic_events` DDL,
canonical `sd_`/`sr_`/`sf_` artifacts and `se_` event identities, contiguous definition→review→freeze
transitions, receipt/event bijection, fail-closed persisted reads, and explicit owner-approved
forensic forward recovery after a committed-v5 protected-object failure. The owner-auth seam binds
the server-derived artifact and current case/source/head to one fresh Touch ID assertion and commits
credential counter, challenge consumption, exactly one receipt, and exactly one semantic event in
one transaction; exact response-loss retries are read-only linkage-validated recovery. The existing
owner-auth REST challenge/perform routes accept the single closed `record_semantic_event` literal and
special-dispatch that seam without `_action_argv`, `_run_json`, a subprocess, CLI job, or second
mutator; existing actions retain their behavior. The final Terra review is APPROVE; all six identified
S5b blockers were repaired, including resolver/source-pack parity, the explicit freeze review binding,
canonical semantic text, whitespace-safe recovery, legacy migration proof, and deterministic concurrent
migration setup. Focused ControlStore/owner-auth suites pass (`150 passed`), a deterministic
100-run concurrent v4→v5 migration stress passes with zero failures, and the final canonical full
gate passes pytest/coverage, OpenAPI freshness, 14-wheel build/import smoke, typing, imports, lint,
harness, and semgrep. The verified semantic CLI read and existing semantic GET bytes remain
unfrozen and unchanged in meaning; there is no direct semantic-write CLI command, new REST route,
screen, handwritten frontend or frontend-derived authority, MCP semantic capability, D1/D2 or
promotion authority, holdout access, paper, broker, or order widening. S5c presentation remains
pending.

**Generic study composition S5c/S6 existing-screen delivery (2026-08-30)** ✅ — the existing
ResearchCockpit Study tab now renders the unchanged seven-key server-masked semantic response beside
additive `ResearchStudyStatusV1`. The CLI-owned status projection verifies the append-only ledger,
reads events and their head in one SQLite transaction, projects only the semantic cycle bound to the
current contract and case revision, and marks an older cycle stale instead of pairing it with current
masked points. It links the existing D1 terminal-attempt ledger and live queued/running/paused/failed
execution state, elapsed/remaining budgets, promotion dossier reference/readiness, and
Python-authoritative next-owner action. A real D0→D1 path also closes the second-precision semantic
cutoff compatibility defect without changing the frozen S5a response bytes.

The browser derives neither masking nor authority: a stale or hash-mismatched semantic source hides
the masked read, D1 is labeled `OWNER CLI ONLY`, and no launch affordance exists. CLI/REST parity is
proved on one data directory with a populated Touch-ID-bound semantic event and completed D1 attempt.
The focused Python suite passes (`208 passed`), frontend coverage passes (`167 passed`), the Study-tab
Playwright/accessibility case passes at all three supported viewports, generated OpenAPI/TypeScript and
committed SPA assets are fresh, the MCP surface remains exactly 62 tools, and the fast and canonical
full gates pass on the exact tree. No route, screen, MCP tool, owner action, D2/promotion control,
paper, broker, or order authority was added.

**Crypto operational-readiness C2 project workspaces (2026-08-30)** ✅ — every governed strategy
project now has one deterministic `StrategyProjectWorkspaceV1` reference projection at
`data/strategy-workspaces/<project-slug>--<project-id>/`. Twelve strict category indexes store only
reference identifiers, availability, and hashes; SQLite, research dossiers, datasets, snapshots,
immutable runs, figures, and reports remain in place and authoritative. A complete self-verified
content-addressed revision is durably staged before atomically replacing `current.json`; repeated
sync is byte-idempotent, a failed pointer publication preserves the prior current revision, and
generated-state tamper fails closed until `alpha project workspace recover` quarantines invalid
bytes and rebuilds solely from authority. `sync`, `sync-all`, `show`, and explicit `recover` are
CLI-owned; project creation commits its authoritative transaction before initial materialization.

The existing Development Center renders the same strict REST/CLI projection and one bounded refresh
action. It labels authority `none`, execution disabled, and the non-transmitting sandbox
classification; FastAPI remains a thin CLI relay. Focused unit/integration tests cover deterministic
bytes, stale revisions, missing immutable-run references, raw-byte exclusion, atomic failure,
tamper recovery, two-project backfill, creation failure timing, and exact CLI/REST parity. The
Workstation walkthrough passes at all three supported viewports. No SQLite identity, run ID,
artifact layout, research gate, owner-auth ceremony, MCP tool, D1/D2/promotion action, paper,
broker, or order authority changed.

**Generic study composition S7/S8 closure (2026-08-30)** ✅ — the crypto-readiness release adopts
no new `alpha-study` adapter or dependency. ADR-0035 records an explicit disposition for TA-Lib,
Twelve Data, Alphalens, mplfinance, Qlib, RD-Agent, PyPortfolioOpt, Riskfolio-Lib, `bt`, Zipline
Reloaded, pfhedge, and pybotters. The existing separately locked Qlib diagnostic worker is retained
unchanged; it is not newly adopted into the study layer. Every future candidate still requires a
separate ADR-0011 evidence packet.

S8 acceptance uses the existing common contracts: provider-native BTCUSDT technical and registered
Bybit linear BTCUSDT/USDT crowding events round-trip through `EventTableV1`, while an exact Binance
spot/USDT BTC/ETH universe round-trips through `FactorObservationTableV1`. The fixtures bind causal
availability, input, vintage, universe-snapshot, provider, family, venue, instrument, and quote
identity; future source/universe poison fails closed. The focused study/provider/bias suite passes
(139 tests), the complete bias-guard family passes (158 tests), two perturbed-environment
determinism passes are green, and the canonical full gate passes on the exact tree. No empirical
support, owner decision,
D2, promotion, execution, paper, broker, order, MCP, or new UI authority is introduced; no legacy
or immutable artifact is deleted.

**Crypto operational-readiness C4/C5 checkpoint (2026-08-31)** 🚧 — the release remains blocked,
with exact evidence in `docs/audit/2026-08-30-crypto-operational-readiness-checkpoint.md`. After
enabling iTerm removable-volumes access, the Expansion mount is read-write, UUID-matched, and has
1.949 TB free. The exact-root write/hash/delete probe and ALPHA storage gate pass; full verification
rehashes all 372 manifests and rederives all 14 snapshots, with 13 research-eligible snapshots, one
asset master, zero staging entries, and no private paths exposed. All nine recorded bounded batches
are complete, both asset masters and all 12 feature artifacts verify, and execution authority
remains false. Four scoped public crypto network tests pass. The canonical CoinGecko Keychain check
currently reports its `rate_limited` receipt, which remains an explicit provider blocker rather than
a skipped success. The isolated program acceptance now composes
the public research lifecycle through a matching research-contract-bound experiment, suite-owned
baseline/OOS/validation, disclosed fake-model interface evidence, classical plus Kronos path-risk
Monte Carlo, stored reports, and the non-authoritative project workspace. This exposed and repaired
the missing experiment contract relay and noncanonical Monte Carlo run-output token. The standalone
hedged-basis suite passes and its live preflight remains `UNSUPPORTED_MULTI_VENUE_PAPER` with no
credentials, broker connection, order, fill, or position change. The external-storage blocker is
closed without rewriting historical warning or quarantined evidence. A provider-backed BTC
journey, the connected-browser six-area walkthrough, fresh owner Touch ID ceremonies, C6 gates/CI,
and merge are still pending; no readiness, profitability, paper, broker, or order claim follows from
this checkpoint.

**Trader terminal Phase 1 "Work" (2026-09-02)** ✅ — the owner's crypto walkthrough findings #1–#6 and #13 (`docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md`) are closed on the approved design `docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md` through plan `docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md` (W1–W8, each committed behind the full gate): a failed job now carries the CLI's own error line; `data pull` normalises symbols, rejects reversed ranges and refuses a ccxt start before the pair's first listed bar while naming the retry start; `alpha data first-bar` and `GET /api/data/first-bar` project that listing read-only; the SPA gains a crypto/equities `profile` (data defaults only) and one Data Manager panel replacing Market Data/Research Data (native dates, Estimate + `Start there`, stored pairs, Expansion SSD datasets with an honest unmounted state, reviewed-asset recipe, governed Research Data embedded); `reviewed-native-v2` adds XRP and SOL with v1 bytes pinned and unchanged. Still owner-run: regenerating the cross-provider asset master with the receipted `asset-master-create`, the in-browser acceptance walkthrough, and a `tests/bias_guards/` future-poison guard for `AssetMaster.resolve_native` (protected path; invariants-auditor low finding). No readiness, profitability, paper, broker, or order claim follows.

**Trader terminal Phase 2 "Clean" (2026-09-02)** ✅ — findings #8–#12 of the owner walkthrough (`docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md`) are closed on the approved design (`docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md` §4.4, §4.5, §7) through plan `docs/superpowers/plans/2026-09-02-trader-terminal-phase2-clean.md` (C1–C8, each committed behind the full gate on `feat/trader-terminal-phase1-work`): a server-computed additive `display_name` on every run projection and a Library rail that reads strategy · D1 · symbol · dates (`bfda12a`); the Strategy Performance Report — one window, left tree, Summary table of recorded values only, the outcome band/tabs/banners collapsed into one watermark chip (`c6e5397`); figure maximise with Save PNG / Save SVG / Copy / Esc and prose kept in the DOM in both explain modes (`fecc14d`); a shell-level Governance dialog composed from existing reads that absorbs the five hazard-stripe sentences, the Development Center lock notice and the Operate Glossary foot (`364e655`); one topbar status chip with the research-gate watermark asserted on three surfaces (`d3e424c`); one dense jobs table (`13f2a30`); the Phase 2 acceptance e2e and all twelve baselines (`a2569a0`). Deviations from the plan block are recorded in the plan: Governance is a dialog opened from the topbar button and the status chip, not an Operate pane; the glossary is unfiltered (no entry carries a profile tag); contextual `role=note` notices that name a next action stay on working screens. No API, statistic, figure byte, DAG, MCP, point-in-time reader or authority changed; the watermark remains a server string relayed verbatim. Still owner-run: the in-browser Phase 1/2 acceptance walkthroughs and the Phase 1 follow-ups. Phase 3 "Terminal" needs its own plan. No readiness, profitability, paper, broker, or order claim follows.

**Trader terminal Phase 3 "Terminal" (2026-09-03)** ✅ — finding #12 of the owner walkthrough (`docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md`, workflow-centric navigation) is closed on the approved design (`docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md` §4.1, §4.2, §4.6, §7) through plan `docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md` (T1–T8, each committed behind the full gate on `feat/trader-terminal-phase1-work`): a server-side additive `market` field on run and project projections (`8d49fc9`); static crypto/equities profile manifests that gate windows, docks and provider lists in the browser and are never sent to the server (`eab1a94`); the Option E terminal-classic theme as the default figure theme with the SPA's canvas tokens generated from it and drift-tested, RENDERER_VERSION 3 → 4 (`d8a04c5`, quant and review attestations bound); document and dock registries replacing the six-screen registry (`fc8f577`); pure MDI/menu/toolbar/status-bar models with every served CLI command group assigned to exactly one menu (`c8321f0`, `tests/unit/test_web_menu_groups.py`); Market Watch and Navigator models and panels plus a profile-tagged glossary (`21dd1b7`); the terminal shell itself — title bar, eleven-entry menu bar, toolbar with the symbol · venue · timeframe chip, status chip and Governance button, left Market Watch and Navigator docks, the MDI document area whose bottom tabs mount only the active document, the collapsible Toolbox (Jobs · Trades · Backtests · Data pulls · Log), the right Data Manager dock and the status bar, with Governance now a document and `screens.tsx`/`LibraryRail.tsx` deleted, and the Playwright harness rewritten to documents and docks (`5771447`, one commit rather than the planned two); twenty `*-document-*.png` baselines replacing the twelve screen baselines with `npm run test:e2e` green on all four projects (`f109f90`); and this docs commit (T8). Deviations are recorded in the plan (side panes, unique document titles, one MDI close button plus the Delete key, the Toolbox starting collapsed below an 800px-high window, no Stop button, the watermark's three surfaces proven sequentially). No statistic, point-in-time reader, DAG contract, MCP tool, or authority changed; figure bytes changed deliberately and only through the renderer version. The two pre-v2 manual lines retired by this phase are kept here verbatim for `tests/unit/test_claude_md_relocation.py`:

| `../frontend/src/shell/` | The shell: `screens.tsx` declares **six fixed screens** (Explore · Build · Results · Compare · Studios · Operate) and which panels fill each area — docking is gone, and only the active screen mounts, so nothing polls behind a hidden tab. `LibraryRail.tsx` is the always-present Runs/Symbols/Projects/Workspaces tree; `ContextBar.tsx` is the single symbol/window/project/run editor that replaced five top-bar controls; `PanelHost.tsx` gives a panel its parameter handle without a layout engine | `SCREENS`, `screen`, `areasOf`, `LibraryRail`, `ContextBar`, `PanelHost` |

- **New Workstation panel** → a manifest/artifact read and/or `alpha ... --json` projection + an `alpha_web/api/` router + a `frontend/src/panels/` component placed on a screen in `shell/screens.tsx`. Operational state needs a separately governed public seam (never `RUN_DIRS` by default). Then run the frontend gate and commit `static/app`.

A scripted real-backend smoke of every document in both profiles then fixed four defects the mocked harness could not show (Market Watch reading `—` for pairs whose history ends before a ten-day lookback — now the additive `GET /api/candles/{symbol}?tail=N`; a crypto pair surviving the switch to Equities; MDI tabs overlapping past ten documents; regenerated OpenAPI/TS client). Still owner-run: the acceptance walkthrough in both profiles at 1440×900, the Phase 1/2 walkthroughs, the receipted asset-master regeneration, and the `tests/bias_guards/` guard for `AssetMaster.resolve_native`. The branch is not merged. No readiness, profitability, paper, broker, or order claim follows.

**Trader terminal Phase 4 "Pixel" (2026-09-03/04, `docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md`, branch `feat/trader-terminal-phase1-work`, PR #47)** ✅ The owner rejected the Phase 3 build on three grounds (findings #14–#16 in `docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md`) and decided: one Market Watch row per stored pair with its venue shown, an opt-in live public ticker with the stored close and its date as the fallback, every artboard element reproduced and disabled with a reason where unbacked, and a button on every "owner approval" notice. Delivered behind the full gate: P1 Market Watch venue + Age columns over the existing `?tail=2` candles read (`d823961`); P2 `CCXTAdapter.ticker`, `alpha data ticker`, `GET /api/data/ticker` and the `Live` toggle — display only, never stored, no data authority (`efe3322`); P3a artboard-exact shell models and chrome — window title, icon toolbar with chart controls, dock frames with bottom tabs, document header bar, Toolbox table, status bar (`8d72d3c`, `ab3bda0`); P3b report toolbar/tree, Governance `Item | State | Detail`, full-window figure overlay, twenty baselines re-taken (`fee839e`); P4 `OwnerActionButton` on every owner step (`launch_d1`, `launch_d2`, `revise_exploration`, `record_final_disposition` through the unchanged owner-auth routes), `Copy command` with the ADR reason where a step stays CLI-only, `Enroll Touch ID` link, and `tests/unit/test_web_owner_actions_drift.py` (`7acf3eb`); P5 a scripted real-backend acceptance in both profiles at 1585×991 and 1440×900 (every document and dock tab, no console errors, no horizontal overflow, honest Market Watch rows, Navigator backtest → report toolbar, Live ticker and an XRP/USDT Binance pull over the network) that fixed `unknown`-provenance venues and float32 price noise, plus this docs commit. Touch ID prompts cannot be scripted; the owner completes one real owner step. No statistic, point-in-time reader, DAG contract, MCP tool (62), or authority changed. No readiness, profitability, paper, broker, or order claim follows.

The pre-v2 manual line rewritten by Phase 4 P4 is kept here verbatim for `tests/unit/test_claude_md_relocation.py`:

| `../frontend/src/panels/ResearchCockpit.tsx` | Generated-contract client for the safe Research Case operations plus the ADR-0021 read plane; sticky case header, Python-authoritative HypothesisCard/scorecard, linked-context follow, New Idea focus, the R6e Decision tab, and the S5c existing Study tab for the exact server-masked semantic read plus `ResearchStudyStatusV1` owner-event/D1 guidance | read-only study projection; no source-pack screening, approval, D1 launch, owner decision, D2, promotion, paper, broker, or order authority |

**Trader terminal Phase 5 "Analyst" (2026-09-04/06, `docs/superpowers/plans/2026-09-04-trader-terminal-phase5-analyst.md`, branch `feat/trader-terminal-phase5-analyst`)** ✅ The owner asked for the terminal to be the main surface and "more like TrendSpider"; the AskUserQuestion decisions were chart-first analysis, a no-code strategy builder + tester, a scanner + alerts, and the approved artboard chrome kept. Delivered behind the full gate: S3 `alpha chart overlays` (indicator series and knowable-by-last-bar pattern annotations over the PIT candle window via lazily imported `alpha_patterns`, head-only warm-up nulls), `GET /api/overlays/{symbol}`, the Insert › Indicators… dialog, indicator panes and swing markers on the chart, New chart window + Tile charts (`c405c16`, `e1221b1`, `89a4577`); S4 the `rules` strategy — `alpha_strategies.rules` parses a strict canonical spec of `left op right` state conditions over `alpha_patterns` indicators, `RuleStrategy` runs it in nautilus, the Tier-1 surrogate evaluates the same `rule_signal`, `alpha rules save|list|show|validate|delete`, `--rules NAME` on `backtest run`/`validate` with the spec bytes in run identity and manifests, `/api/rules`, and the Strategy Builder document; the import-linter contract became `alpha_strategies depends only on core and patterns` and `alpha_patterns` joined the execution fingerprint (`875f8ad`…`aa1e0f2`, risk-tier review APPROVE attested); S5 `alpha scan save|list|show|delete|run|check|alerts` over PIT reads with a bias guard, `/api/scans` + `/api/alerts`, the Scanner document and the live Toolbox › Alerts tab that checks every scan on mount and after each pull (`09fa132`…`b8238d2`); S6 the scripted real-backend acceptance extended to overlays, builder → sandbox run, scanner → alerts, which found two defects the mocked harness could not: the SIM account was always denominated in USD so a USDT-quoted pair on MARGIN crashed inside nautilus the first time a netting flip left a position snapshot to convert (fixed in `alpha_backtest.engine`: the account is denominated in the instrument's quote currency; regression test `test_margin_account_settles_in_the_pair_quote_currency_across_a_flip`), and the builder validated with an empty spec name before a file name was typed. The MCP surface stays pinned at 62; no statistic, point-in-time reader, or authority changed; the DAG gained one edge (`alpha_strategies → alpha_patterns`). Rule and scan results are screens of the current state, never evidence; no readiness, profitability, paper, broker, or order claim follows.

The pre-v2 manual line rewritten by Phase 5 S6 is kept here verbatim for `tests/unit/test_claude_md_relocation.py`:

- `alpha_data` → core only. `alpha_strategies` → core only. `alpha_validation` → core only. `alpha_forecast` → core only (only `alpha_cli` may import it). `alpha_options` → core only. `alpha_screener` → core only. `alpha_research` → core only. `alpha_backtest` → core + data only.

**Edge-first Phase A "shorten the loop" (2026-09-10, `docs/superpowers/plans/2026-09-10-edge-first-phase-a-shorten-the-loop.md`, `main`)** — from the audit `docs/audit/2026-09-10-edge-first-system-audit.md`. S1: `pytest-xdist` in the full gate and CI (`-n auto`); the pytest step fell from 609 s to ~200 s on 10 cores with the 93% coverage floor still combined. S2: `platform` marker auto-applied by `tests/conftest.py` from the pure `tests/_tiers.py::classify_platform`; the fast gate now runs the alpha tier (~1,700 tests, ~43 s) where it ran no tests before. S3: surface freeze recorded in `CLAUDE.md` (MCP pinned, REST and Trader Terminal frozen at Phase 5; research capability ships CLI `--json` first). S4: `alpha_options` and `alpha_screener` retired end to end (packages, CLI sub-apps, web relays/models, SPA panels, 15→13 import-linter contracts, 14→12 wheels); the `alpha-analytics.md` rule and its fixture lines were removed (zero-loss fixture refreshed as its docstring permits). Deferred: QuantPad removal (control-store CHECK constraint, ADR-0018/0023, SPA models) and the stale `.claude/worktrees/agent-*` checkout (owner filesystem action). Harness deviation, recorded for the owner: nine protected-path edits in S4 were applied by a python script before their acks armed (a zsh variable-expansion failure silently skipped the ack commands) and retroactive acks were refused by the session permission classifier; the plan doc lists the files.

The pre-v2 manual line rewritten by Phase A S4 is kept here verbatim for `tests/unit/test_claude_md_relocation.py`:

- Contracts live in root `pyproject.toml` `[tool.importlinter]` (15 forbidden contracts, including outbound surface limits). Run `uv run lint-imports` after any cross-package import change.


The pre-v2 manual line rewritten by edge-first Phase B (universe + knowledge-time flag) is kept here verbatim for `tests/unit/test_claude_md_relocation.py`:

| `data_cmds.py` | `alpha data ...` (Tiingo qualification/repair, comparison adapters, CCXT provenance, PIT candles + symbols) | `data_app`; `_ADAPTERS` registry (monkeypatched in tests) |

**neurotrader888 technique port (2026-09-12/14, `docs/superpowers/plans/2026-09-12-neurotrader888-port.md`, PR #50, branch `claude/integrate-trader-github-xy6rxs`)** ✅ — every public technique of github.com/neurotrader888 ported into ALPHA's own layers with provenance (`docs/governance/2026-09-12-neurotrader888-provenance.md`; the owner holds the author's personal approval; IntramarketDifference re-implemented from Masters 2020 because it carries no licence). Stream A (`alpha_patterns`): directional change, PIPs, market structure, trendline fit/breakout meta-label features, harmonics, flags, weighted-KDE market profile, Hawkes volatility, VSA + generic rolling OLS residual, runs z, permutation entropy, visibility graphs, reversibility, CMMA, multi-period RSI matrix — each with exact upstream parity fixtures and a future-poison guard. Stream B (`alpha_research`): PIP cluster miner (k-means++ / silhouette / Martin ratio, label-leak purge), retracement-ratio density, rolling PCA — with oracles, `/verify-quant` and `/review-gate` attestations, mutation kill-rate ≥ 0.90. Stream C: `alpha_validation.bar_permutation` + `mcpt.permutation_test` (Masters 2018 ch. 7; Davison & Hinkley `(1+c)/(1+N)`), `metrics.profit_factor` promoted, `trade_dependence` runs test in the native tear sheet (`trade_runs_z`), gauntlet Tier 3 `bar_permutation` (walk-forward, engine-scored, never rescued, `--tier3-paths`), and `alpha optim mcpt` (in-sample optimisation-overfit test writing `mcpt_null.parquet`; never OOS evidence). Stream D: ADR-0036 `defi_tvl` family with `defillama` as sole authority, keyless provider check receipt, `alpha crypto-data acquire defillama defi_tvl <chain>`, and the `defi_tvl_residual` feature with honest next-day availability (the live endpoint is UNVERIFIED in the build sandbox; the owner's first `alpha provider check defillama` receipt confirms it). Stream E: eight oscillators and six patterns on `alpha chart overlays` (generic sub-pane per indicator, `marker` annotations, per-indicator bar guard, every pattern through its `*_known_by(last)`), the same indicators as rule operands (`hawkes`/`vsa`/`runs_z`/`perm_entropy`/`cmma`/`vg_path`/`reversibility`; `rsi_pc1` excluded because the strategy layer cannot import `alpha_research`; rule specs using them fork run identity by design), the SPA Indicators dialog / Strategy Builder / three-tier null narration, a Python↔TypeScript table drift test, and the figures `trade_runs_test` and `mcpt_null_histogram` (`pip_cluster_examples` / `retracement_density` deliberately not built: no run publishes their artifact and a builder may not compute its own statistic). Not ported: `rolling_window` (≡ `find_swings`), `tree_strat`, the demo strategies. MCP stays pinned at 62; no new import-linter contract; no new third-party dependency. Sandbox limitation recorded in every commit override: the full-gate stamp cannot be written here (torch wheel egress-blocked), so each commit lists its hand-run checks and CI is the authoritative full gate; Playwright e2e ran here only after aliasing the pre-installed Chromium revision. Research-only capabilities: none of this is evidence of a profitable edge, and every candidate-promotion gate still applies.

## 2026-09-16 — Agent-neutral refactor, local discovery and metadata slices

**Delivery state: Implemented locally; aggregate candidate gate passed.** The accepted plan is
[`2026-09-16-agent-neutral-reproducible-research.md`](superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md).
[ADR-0037](adr/0037-agent-neutral-research-engineering.md) changes engineering ceremony only;
application owner authority and scientific controls remain intact.

Implemented locally: `alpha info commands --all --json` discovers all registered leaves without
changing default catalog filtering; `alpha info procedures --json` describes V2 analysis-family,
verified protocol and actual scan-command metadata. The optional Atlas now extracts current
`documents.ts` registrations, resolves imported component paths, and shares computed extraction
with bounded source-only `gate.py orient`. Default orientation was measured at 1,450 bytes and
rejects summaries above 6,000 bytes; it reads no owner store or hidden tests. Atlas outputs were
regenerated and freshness passed in the aggregate gate.

Suite action vocabulary now lives in one lightweight CLI module; MCP still excludes owner-only
holdout reveal. Frontend owner actions derive from generated contracts with semantic-ledger
events explicitly excluded from generic owner buttons. Removed obsolete options/screener safe
classification entries. OpenAPI freshness checked unchanged. Local evidence: 88 targeted Python
suite/MCP/REST tests, 10 CLI/Atlas consistency tests, 43 affected Atlas tests, the owner vocabulary
test and 20 frontend client/type tests passed; targeted mypy, TypeScript, lint and import checks
passed. These incremental checks were followed by focused independent reviews and the aggregate gate.

The root operating instructions are compressed into current invariants and source pointers;
domain details live in [research-platform contracts](operations/research-platform-contracts.md).
The historical prose relocation test is replaced by current link/invariant/size checks.
The shared aggregate gate covers backend, frontend, literature, Qlib and Atlas components;
thin Git guards are now installed locally and old per-edit/Stop/shell-parser hooks are retired.
No commit, merge or live provider acceptance is claimed
by this local delivery record. Historical narratives above remain historical, including obsolete
screen counts and prior operating ceremonies.

### Refactor delivery and verification

Implementation slices 0–5 are locally verified under the
[execution plan](superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md).
New exploration plans use resolved V2 axes and actual finding roles with one primary
horizon. Historical V1 execution/confirmation/read paths remain supported. Screening
freezes inputs/code/lock, records distinct attempts and partial trials, and replays
without discovering new data; optional context-packet references are hash-only and
`authority: none`. Screening does not authorize strategy promotion, paper or execution.

The full gate rejects concurrent tree changes. The Claude adapter is 113 lines;
old audit data remains readable (`audit --legacy`, 833 verified events). Root guidance
is 5,968 bytes. Shared vocabulary, generated owner-action types, schema constants and
bounded planner helpers preserve authorities and transaction ordering.

Independent focused reviews closed observed PIT outcome-censoring, crypto-quality,
V2 approval/primary-role, tree-hash and commit-race defects. Six slow oracles passed;
panel mutation score 94.48% and overfitting 81.38% met their recorded floors.
Twelve built wheels imported from an isolated installation. The full aggregate gate
passed all five components on one stable candidate tree in 709.8 seconds of checks
(2026-09-16). Final hardening also canonicalizes V2 family order so equivalent plans
share fingerprints while V1 remains unchanged. The delivery tree must carry a fresh
`gate.py check --tier full` result after these final source/documentation updates;
receipts live in ignored `.alpha/state/`, not in this historical status narrative.
No owner data or approvals were exercised; changes remain uncommitted.

## 2026-09-17 — Cancellation regression and commit preparation

The [follow-up plan](superpowers/plans/2026-09-17-cancellation-and-research-walkthrough.md)
reproduces a test-deadline defect: two valid, delayed real CLI journal calls exceeded
the old five-second aggregate wait although cancellation completed and capacity was
released. The test now synchronizes on heartbeat startup and budgets the existing
bounded operations; production timeouts and terminal-state assertions are unchanged.
Normal and delayed cases passed independently. Full-tree verification is required
after these changes; the current ignored receipts are authoritative.

Commit review also found and fixed staged-rename classification in the Git guard:
both source and destination paths now participate in review/quant requirements.
Three regressions failed before the fix; eleven guard tests passed afterwards.
Panel documentation now identifies per-function sources versus local conventions;
its non-docstring executable AST is unchanged. The independent quant review passed
117 tests and six spot checks, including a new explicit-trade cost-accounting oracle.

The required private `tests/holdout` suite is absent, so independent commit approval
remains blocked pending restoration or an explicit documented owner exception.
No absent tests are called passing; no commit-hook bypass is authorized. The planned
real-data walkthrough is prepared read-only and awaits the requested commit step.

## 2026-09-17 — Owner exception for unavailable hidden suite

After restoration checks found no copy, the owner explicitly authorized documenting
a one-time missing-suite exception, finishing independent review, committing, then
running the research walkthrough. The [follow-up plan](superpowers/plans/2026-09-17-cancellation-and-research-walkthrough.md)
records the exact scope: the integrated refactor/cancellation commit only. Hidden
tests remain UNVERIFIED, not passed. All other checks, independent review and
installed commit guards remain mandatory. Final commit and walkthrough results are
recorded in the handoff and ignored evidence receipts, not assumed here.

## 2026-09-19 — Walkthrough issue closure implementation

The [closure plan](superpowers/plans/2026-09-19-research-walkthrough-closure.md)
records selective artifact verification and neutral unsupported research intake.
Screening still hash-verifies all discovery metadata, but reads bulk artifact bytes
only for selected inputs and their raw lineage. The full inventory audit and frozen
replay integrity checks are unchanged. The existing 33,534-manifest real-data screen
completed in 7.25 seconds, replay in 1.50 seconds, matching the earlier result digest
without the scoped-inventory workaround. These are observed local timings only.

Generic capture now reports a missing research operator with neutral unresolved
fields instead of inventing a double-bottom thesis. Registered operator paths and
historical immutable contracts are preserved. New context-packet reads were
byte-identical and the linked screening reference was independently reverified;
case review remained pending and execution idle. The original follow-up plan now
records its actual completed commit `b1b7510` and walkthrough evidence.

Final aggregate and review status are receipt-driven. The private hidden suite is
still absent; the prior one-time exception does not extend to this change. That
external review prerequisite remains UNVERIFIED, and no new commit or complete
platform-readiness claim is implied by this implementation record.

## 2026-09-19 — Owner resolution of closure review prerequisite

Following the explicit request for a new missing-suite exception covering this
closure commit, the owner authorized proceeding. The [closure plan](superpowers/plans/2026-09-19-research-walkthrough-closure.md)
records this separate, narrowly scoped exception; the absent private suite remains
UNVERIFIED. No future waiver, failing-test exemption, hook bypass or trading authority
follows. All implementation and runtime checks are complete, with a passing full
aggregate on the pre-exception tree; final delivery requires refreshed exact-tree
verification and independent review. Final receipts and commit outcome are retained
under `.alpha/state/` and in the handoff.

## 2026-09-28 — Codex second-model seam repaired after codex-cli 0.154

Two independent breaks were found while verifying the Claude↔Codex connection. codex-cli
0.154.0 removed the `mcp-server` subcommand that `.mcp.json` launched, so every Claude Code
session reported `codex (CONNECTION_CLOSED)`; the dead entry was removed (no replacement MCP
mode exists in 0.154). The bridge default model `gpt-5.3-codex-spark` was retired from the
models cache, so `scripts/codex_bridge.py probe` returned `available: false`; the default is
now `gpt-6-astra` (the owner's Codex default), still overridable by `--model` and
`ALPHA_CODEX_MODEL`; the owner also set the default reasoning effort to `medium` (was `xhigh`;
`--effort` overrides). Live `research` and `review` round-trips through the bridge were verified
against the real model on this tree. A third fault surfaced during that test: the desktop
Codex apps (bundled codex 0.152.1 / 0.149) rewrite the shared models cache without the new
model, which flipped the probe to a false `unavailable`; the probe now ignores a cache stamped
with a different `client_version`. Runbook, owner checklist and ADR-0034 carry the amendment; plan:
[codex seam repair](superpowers/plans/2026-09-28-codex-seam-repair.md). The hidden holdout
suite is still absent; the owner granted a separate one-time exception for this commit only,
recorded in that plan. Hidden tests remain UNVERIFIED. Codex remains
optional and non-authoritative; no gate, surface or approval authority changed. Protected
control-plane paths were edited, so commit requires the usual independent review and a fresh
full stamp.

## 2026-09-29 — Codex-only research benchmark continuation

Owner approved preservation of all Claude evidence and Codex-only future execution. The
[continuation plan](superpowers/plans/2026-09-29-codex-benchmark-continuation.md) adds non-destructive
attempts/scoring revisions, execution fingerprints, streamed partial traces, per-turn failure checks,
and verified filesystem/MCP boundaries. Original reports and 57,664 inventoried evidence files remain
historical. The [capability audit](audit/2026-09-29-codex-capability-audit.md) records omitted web-search
and truncated-note evidence that made two fabrication allegations unreliable, alongside a confirmed
historical read escape and shared-export writes. These are benchmark findings, not platform fixes.

At this implementation checkpoint, 74 evaluator tests and 44 affected bridge/gate tests passed.
The corrected live smoke reached 62 MCP tools, retrieved seeded candles, and preserved owner control
state. Retained-trace Codex scoring and the 15 missing realistic variants are in progress. A full-gate
stamp, independent final review and complete campaign conclusions are not claimed at this checkpoint.
Concurrent UI work in the same checkout is preserved and excluded from benchmark changes.

## 2026-09-29 — Workflow UI repair (verification in progress)

Owner-authorised replacement of the terminal menu/dock shell with full-width workflow pages is
implemented in the working tree. Existing research and execution authority stays behind the same
CLI and owner-auth seams. Shared asset selection, navigation/history, independent data-status
reads, and stale saved-rule protections are under browser regression testing. The web integration
suite passed 187 tests; this is not a full-gate or live-provider acceptance claim.

Current plan: [workflow UI repair](superpowers/plans/2026-09-29-workflow-ui-repair.md).
Evidence and external limitations: [UI audit](audit/2026-09-29-workflow-ui.md).

## 2026-09-29 — Benchmark final evidence checkpoint

Codex-only continuation implementation, bounded campaign and independent review are complete.
All 57,664 original evidence files, including Claude results, remain byte-identical. The 15 new
isolated variants scored 12 pass / 3 fail; retained realistic V4 covers 132 trajectories and qualifies
all 11 automated critical cards in a separate review ledger. Evaluator tests: 84 passed; strict
source typing: 22 files passed. See the [capability audit](audit/2026-09-29-codex-capability-audit.md).

Aggregate verification remains blocked: frozen-copy backend passed with four workers, but the
concurrent minimum-width UI scan-deletion browser test failed (188 passed, 1 failed, 4 not run).
Frontend assets also changed that snapshot. No full-gate, hidden-suite or live-provider acceptance
is claimed; UI repair remains separate. No benchmark commit or push was made.


## 2026-09-30 — Workflow UI repair verification checkpoint

Workflow pages and searchable stored-asset selection are delivered in the working tree. Repairs
cover download clicks, independent storage/provider status, market switches, stale saved rules,
navigation/history, browser-storage failures and uncertain ML terminal-journal writes. The latter
uses the existing CLI journal, verifies before retrying and preserves unverified capacity.

Final frontend run: **193 browser tests passed**, **312 unit tests passed**, and build/API/SPA
freshness checks passed. Every backend component check passed, including coverage (**93.17%**),
slow oracles and mutation checks. This supersedes the earlier scan-deletion test failure noted in
the benchmark checkpoint; the trace showed successful deletion followed by a slow refresh.
Independent review found no remaining production blocker. The integrated app is available at
localhost:8801; its read-only owner-machine navigation check passed.

Concurrent benchmark documentation/results updates invalidated earlier aggregate stamps despite
passing repair checks. Use `uv run python scripts/gate.py check --tier full` for current whole-tree
acceptance. Live vendors, physical Touch ID, model weights and paper-broker acceptance remain
unverified. Details: [UI audit](audit/2026-09-29-workflow-ui.md) and
[implementation plan](superpowers/plans/2026-09-29-workflow-ui-repair.md).

## 2026-09-30 — Benchmark continuation verification closed

The [Codex-only continuation](superpowers/plans/2026-09-29-codex-benchmark-continuation.md) is delivered.
All six canonical full-gate components passed on one stable tree; the stamp matched the live
checkout before this documentation update. Previous UI deletion and generated-output blockers
are cleared. Independent final benchmark review found no remaining delivery gap. The
[new verification receipt](../tools/alpha-eval/results/2026-09-29-continuation/verification-2026-09-30.json)
preserves the successful run separately from earlier failures. Documentation edits follow the
tested tree; no later exact-tree stamp, commit, push, hidden-suite or live-provider acceptance
is claimed. Existing Claude evidence and benchmark conclusions are unchanged.

## 2026-09-30 — Benchmark-only commit preparation

The benchmark delivery is isolated from concurrent UI changes for exact-tree verification and
independent protected-file review. Its commit includes the evaluator, Codex judge bridge, shared
evaluator gate/CI integration, preserved evidence reports and benchmark documentation. UI code,
UI plans and UI-specific manual changes remain outside this commit. The historical combined-tree
receipts above retain their original scope. Final commit checks require a new full-gate stamp and
independent review on this isolated tree; local receipts are retained in `.alpha/state/`.

Independent delivery review reproduced three offline test failures when Codex was absent from
PATH. The scorer unit tests now mock the client-version lookup as well as judging; production
version fingerprints remain real. The evaluator suite is checked with a Codex-free PATH before
the refreshed aggregate gate.


**2026-09-30 — Terminal usability and external archive charts (implemented; full gate blocked).**
Owner direction restores compact grey Windows-style chrome, chart docks, square controls and a
large candle canvas while preserving workflow routes. ADR-0038 replaces mandatory biometric
ceremonies with explicit bound local confirmation and honest V6 receipts; historical WebAuthn
receipts remain intact. External archive selection now opens exact verified Binance/Bybit OHLCV
windows with explicit market, venue, interval and volume units. Metadata-only ordinary discovery
avoids whole-drive hashing; selected artifacts and raw lineage still require full verification.
A real owner browser loaded 901 AAVEUSDT daily bars; discovery returned 2,178 compatible datasets.

Final application checks: 4,740 Python tests passed (93.11% coverage), 314 frontend unit tests and
all 196 browser scenarios passed; strict typing, import contracts, OpenAPI, scoped lint, semgrep
and wheel smoke passed. Independent UI/backend inspection found no remaining blockers. Global
`gate.py full` remains blocked by 198 ruff errors in the concurrent benchmark session's untracked
PDF scratch script; no full-repository acceptance or universal live-provider readiness is claimed.
See [verification and limitations](audit/2026-09-30-terminal-usability.md) and
[open-source component decisions](audit/2026-09-30-open-source-component-review.md).


**2026-09-30 — Terminal workflow polish.**
F2 function navigation, task-level search with retry, remembered task tabs, keyboard tab navigation,
profile-specific chart layout preferences and a shared comparison grid extend the grey Windows
terminal. Watchlist data scrolls independently of its tabs. Independent review findings on palette
search carryover and duplicate comparisons were corrected. This is workflow inspiration, not a
claim of Bloomberg parity. Current verification and cross-session browser isolation findings are
recorded in [the polish audit](audit/2026-09-30-terminal-workflow-polish.md).

## 2026-09-30 — Connected edge research workspace

Implemented the owner-approved chart/conditions/assistant/results plan. CLI owns condition
semantics and bounded native Codex context; structured drafts require source freshness and rule
validation before opening the existing builder. Docked scans/trades/results, indicator search
and favourites, and case-linked observations connect the research journey. Recorded metrics
retain costs, baseline and OOS limitations. Deferred-response state races and lost-heartbeat ML
cancellation classification were fixed with targeted regressions. Aggregate verification pending;
see [implementation audit](audit/2026-09-30-edge-workspace.md). Separate research branch remains
unmerged, with shared ownership handoff documented.

**2026-09-30 — Connected edge workspace verification completed.**
All six canonical full-gate components passed on one stable implementation tree; the full browser
suite passed all 244 scenarios. Fifty-eight focused assistant tests include exact provider-symbol
compatibility and retained traversal rejection. Independent review closed the findings. A real
supervised Codex smoke returned cited, appropriately limited analysis. The delivery plan is
completed; current-tree acceptance is recorded by the fresh machine gate receipt after documentation
closeout. See [verification evidence and limitations](audit/2026-09-30-edge-workspace.md).

**2026-10-01 — Stored watchlist and context picker.**
Market Watch now omits profile starter pairs absent from stored inventory, preserves exact venue/quote
variants, and opens the selected stored market on Price with stale date/run/snapshot context cleared.
The working-context picker is anchored to its trigger so it stays inside the viewport. Focused unit and
browser checks passed; see the frontend terminal workflow guide.

**2026-10-01 — Crypto data discovery and native chart intervals.**
Crypto Data Center capability discovery now reads immutable manifest metadata rather than hashing the
entire Expansion archive on every open; selecting a dataset and explicit full storage audits still
verify artifact bytes and lineage. Data Manager can search the latest qualified local Binance spot
catalog and distinguishes venue listings from downloaded history. Native Binance spot intervals from
1m through 1w (including 4h and 3d) are stored as separate frequency identities and can be filtered
and opened in the archive chart. This does not change the canonical daily strategy/backtest store.
Focused backend/frontend checks passed; full gate and live browser acceptance remain pending.

**2026-10-02 — Crypto archive and market-discovery verification.**
Verified archive segments with identical native identity are now charted as a single series. Identical
overlap bars at file boundaries are coalesced; conflicting OHLCV values fail closed. The mounted
Expansion catalog exposes 102 chart series, including 50 multi-segment series; a live AAVEUSDT 1h
chart opened 41,113 unique bars across 43 verified segments (2022-01 through 2026-09). A fresh
keyless Binance spot listing catalog was acquired on 2026-10-01 and now marks current results fresh.
Backend full tests passed (4,845; 93.17% coverage); the later catalog-ranking correction passed its
focused regression test. The full frontend component gate passed, including the 256-scenario
Playwright matrix. Backend and frontend component receipts were produced on separate trees because
API types/static assets were synchronized between checks, so no aggregate full-gate stamp is claimed.


**2026-10-02 — Agentic research capability program (planning only).**
The [proposed program](superpowers/plans/2026-10-02-agentic-research-capability-program.md)
defines autonomous loss/regime investigation, bounded chart-pattern search, typed evidence,
selective specialist roles, information boundaries, and outcome/cost evaluations. It distinguishes
current-root work from separate delivery at `73fb2a9`; integration must be reconciled first.
Independent planning review sharpened the retrospective/predictive handoff, historical-context
operator, minimal four-action demo, and initiative/ablation metrics. No runtime change, dependency
installation or agent campaign was performed. Next: isolated integration inventory, minimum safe
information boundary, then the three-case drawdown investigation demonstration.


**2026-10-02 DefiLlama review correction and active-data retirement:** The first stablecoin
capture used an incorrect USD supply unit label; parser v2 preserves native USD-pegged token
balances, with no quote asset. That initial capture was revoked from active discovery and new
snapshot/derived admission, preserving its canonical bytes and lineage. A fresh corrected capture
`ba8213d45cbe2bf74575ee519839a4432005eee5449c08c15d83a9529c6bfd65` qualified.
Seven unreferenced quarantined records were also retired after a locked local JSON/SQLite and
manifest reference audit. Fifty-two referenced quarantines and all five warnings remain; four
warnings have retained references. Zero immutable artifacts were deleted. Audit receipt:
`output/data-hygiene/2026-10-02-retirement-applied-audit.json` (sha256
`aa8cae59a5e73daecda4ba28ef50460eed5a8d4f46b9d8fa9ccebaa6c45972fb`).
Atomic hash-bound retirement markers distinguish archive integrity from new admission eligibility.
Current yield-pool search verifies selected catalog and raw lineage before returning bounded
results; browser testing confirms exact UUID selection and native acquisition cadence. Naive
history timestamps are rejected, UUID case is canonicalized, and a future-download bias guard
rejects retroactive availability. Focused tests, typing and independent review passed; the final
aggregate gate is pending at this delivery-record update. Full archive-wide byte integrity remains
unverified; the selected live acquisitions and all 64 flagged candidates were individually verified.


**2026-10-02 Unified crypto asset picker:** Main context and Market Watch selectors now combine
canonical symbols with read-only external-drive chart discovery. The current local inventory
contains 50 coins, 52 grouped pairs and 102 archive series, all represented in the selection model.
BTC-USD/BTC/USD share a display row; exact feeds, quote currencies, native contracts, intervals
and manifests remain distinct. No source bytes were deleted or merged. Archive selection opens
Price from any task with explicit chart identity, preserving canonical strategy context; canonical,
run, project and profile transitions clear that identity. Failed archive reads never substitute
canonical candles. Non-price families remain reachable via the typed crypto data inventory link.
Independent review corrections cover manifest labels, chart heading, supported listbox semantics
and Escape focus restoration. Focused model/browser checks and live inventory grouping verified
the behavior; final canonical aggregate gate is pending at this record update.

**2026-10-03 reference quant workstation:** Classic menus and one active-panel toolbar now expose
existing workflow routes through View/Search, with document tabs/Toolbox below the analytical area.
ChartWorkspace adds validated per-profile independent sources, five layouts, pointer/keyboard
splitters, four-panel presets, individual maximize/Escape and local UTC range/cursor linking.
Lightweight Charts instances persist across options, evidence, selection and composition changes;
recorded line/area plots, scientific SVG/table projections and static figure exports reuse existing
APIs. No backend endpoint, estimator or authority changes were made. Independent review corrections
include source isolation, hidden document retention and asynchronous range application. Frontend
unit coverage: 340 tests, 94.79% lines. Four 25k-bar panels and existing latency/performance budgets
passed; 54 final focused viewport/accessibility regressions passed after the minimum-size report
scroll region gained keyboard focus. Live read-only XRP run 5ca68199f7241db4 showed zero frozen
price bars with snapshot_unavailable, 2,808 equity points and backend rolling window 126; its other
three recorded panels remained usable. Aggregate acceptance is represented only by the current
exact-tree full-gate receipt. See the [delivery report](operations/2026-10-03-reference-quant-workstation.md)
for architecture, review findings, checks and limitations.


**2026-10-03 scientific workstation correction:** Owner retained the classic top bar but corrected the renderer direction: Qbot's actual Bokeh report and Matplotlib integration are scientific references, beyond panel composition. BokehJS now defaults for market observations, recorded series, histograms and QQ plots; optional Lightweight preserves existing market features. The research report preset combines equity, drawdown, diagnostics and genuine backend figures. Visible project selection supports no-project browsing and clears dependent evidence identity while retaining market/archive views. Native-hourly discovery opens an exact venue/market chooser. No backend endpoint, statistical calculation, artifact or domain authority change. Verification is determined by the current exact-tree aggregate receipt; see the [correction report](operations/2026-10-03-scientific-research-workstation.md).

**2026-10-04 workstation performance continuation:** Scientific cursor overlays and a frame-budgeted resize queue preserve real series and chart lifetime; market resizing coalesces while retaining the latest logical range. Revised large-series checks require an actual changed-size settled redraw within the original timing limits. All frontend steps passed; a documentation edit invalidated that component receipt. Current aggregate acceptance still requires the exact-tree canonical full receipt. See the correction report for the methodology and evidence.

The following canonical run passed backend and 302 browser tests but failed the scientific p99 limit (35.6 > 34 ms). Two paint frames between relayouts and a correctly settled preflight baseline now pass focused timing checks and 21 viewport regressions; independent scoped review approves them. Current exact-tree full receipt remains mandatory.

### 2026-10-04 — Chart exploration and readability

Scientific charts now expose direct UTC windows, full-returned coverage/null/extrema summaries and expandable native OHLCV cursor data. Recorded tables have shared exact CSV/page counts; sampling is readable while raw provenance remains. Friendly panel/layout labels preserve enums and empty charts guide source selection without a project. No statistical/backend/data/authority changes. Review caught and tests reproduced zero-width date/singleton ranges; fixed with positive-span guards. Focused 359-unit coverage passed; browser/snapshot verification and exact-tree review are recorded in [delivery report](operations/2026-10-04-chart-exploration-usability.md). Intermediate scientific/market performance failures remain explicit there. Current frozen-tree canonical full receipt governs aggregate acceptance; historical passes never authorize changed source.

The first chart-exploration canonical tree (`2be915e…`) passed backend and 311 browser tests but failed the scientific slow-frame allowance by one frame; no aggregate receipt. Cursor updates now reuse the existing text node and avoid redundant tooltip/closed-disclosure DOM work. Both unchanged focused performance tests pass, including actual resize settlement. Full acceptance still requires the subsequent frozen-tree canonical receipt; boundary timing headroom remains limited.

The second chart-exploration canonical run passed backend and 311 browser tests but missed optional market p99 (36.1 > 34 ms). Both renderers now share cancellable staggered resizing, and linked ranges deliver one latest-value peer per frame while cursors stay together. Unchanged focused performance passed both p99 at 26.3 ms with real changed/settled canvases; independent scoped review approves. Historical failures and range-convergence latency remain in the delivery report. Current exact-tree full receipt remains mandatory.

The third frozen chart-exploration full run passed backend and 311 browser tests but scientific p99 missed by 1 ms (35 > 34). Axis dispatch now coordinates resizing and linked ranges; cursor transforms avoid redundant geometry writes. Native painting may still overlap. Acceptance remains dependent on the current exact-tree full receipt; failures are retained in the delivery report.

**2026-10-05 — Aggregate acceptance recorded for the crypto terminal tree.**
The canonical `gate.py full` passed all six components on the frozen shared tree (stamp tree
`54b7f96e5837f47d…`, HEAD `e54aa7a`, 2026-10-04 13:46 UTC, 969 s). That pass supersedes the
"aggregate receipt pending" and "full gate blocked" statements in the 2026-09-30 through 2026-10-04
records above, which remain as history. The 198-error ruff blocker was the benchmark session's
scratch script; it and the benchmark PDFs are archived outside the repository and `tmp/` is now
ignored. The DefiLlama retirement-audit receipts under `output/data-hygiene/` are committed so the
sha256 citation above resolves in the repository. Five July research files deleted without record
(`research/*mizerxbt_eth*`) are restored. ADR numbering is corrected before integration: published
ADR-0036 belongs to the DefiLlama family on origin/main, agent-neutral engineering becomes ADR-0037
and local confirmation/terminal archive charts becomes ADR-0038; every reference and the Atlas
were regenerated. Re-verification on 2026-10-05: pytest 4,879 passed, vitest 361 passed, ruff,
format, 13/13 import contracts and semgrep clean. Full archive-wide byte integrity remains an
unclaimed separate inventory. Reconciliation with origin/main follows under
[the clean-and-reconcile plan](superpowers/plans/2026-10-05-clean-reconcile-main.md).

Performance budgets became an opt-in lane by owner decision on 2026-10-05. Two consecutive frozen-tree
gate runs each failed exactly one different frame-timing spec by a small margin (25k-bar median frame
18.4 ms against 18; four scientific panels p99 39 ms against 34) while all other 311 browser tests
passed. The four `@perf-budget` specs now run only with `ALPHA_PERF_BUDGETS=1`; their thresholds are
unchanged, and the gate and CI keep every functional browser journey.

**2026-10-06 — Lineages reconciled on the integration branch.** `integrate/main-2026-10-05`
starts from PR #51's head (origin/main plus the edge-first lineage with macOS determinism fixes)
and merges `feat/crypto-terminal-ui` (edge-first follow-ups, the eval benchmark and the crypto
terminal commit). Resolutions: `alpha_research` exports are the union of the panel and the
neurotrader888 port (pip_miner, retracements, rolling_pca); the null-family suite builder keeps
the local structure and origin's `--tier3-paths 64`; one `defillama.py` serves all five families
(origin's chain TVL `defi_tvl` and the four protocol/stablecoin/yield families) behind one URL
builder whose unknown endpoints fail as unregistered, and the CLI dispatches chain TVL to its own
acquisition path; the compact CLAUDE.md stands and ADR-0036 (DefiLlama), ADR-0037 and ADR-0038
are all indexed; the chart keeps origin's per-shape swing markers inside the terminal canvas.
OpenAPI, the TypeScript client, `static/app`, the operation ledger and the Atlas were regenerated
rather than hand-merged. The web rule no longer calls the UI frozen at Phase 5.

**2026-10-07 — Per-platform screenshot baselines.** PR #53's CI frontend job failed the Chart and
Strategy Builder document screenshots at 3% pixel difference. About half of that was stale
content: the baselines had been carried over from before the current chart controls landed; the
rest is macOS-versus-Linux font and canvas rendering. By owner decision every document screenshot
now keeps a `-darwin` baseline re-taken on macOS against the current build and a `-linux` baseline
rendered in the `mcr.microsoft.com/playwright:v1.61.1-noble` container (linux/amd64), both under the
unchanged 2% tolerance. The CI frontend job's timeout rose from 15 to 40 minutes for the 308-test
browser suite.


**2026-10-10 mutation sweep durability (isolated publication):** Serial nightly sweeps were
cancelled near six hours. The owner selected weekly exhaustive singleton jobs; nightly Semgrep,
determinism and raise-site coverage remain. Identity-bound atomic checkpoints, persisted logs,
unique staging, bounded matrix/internal workers, deadline process-group cleanup and exact aggregate
validation separate complete infrastructure from report-only hosted scores. Floors, tolerance,
module/test scope, excluded-test audit and local tooling-unavailable semantics are unchanged.
The shared-tree implementation passed 225 focused tests, four Atlas consistency tests and the
six-component canonical full gate. This focused branch requires its own fresh full verification,
independent review and hosted evidence. Private engineering coverage remains UNVERIFIED; main's
review policy must be satisfied before any protected commit. After an explicit question,
the owner answered "yes" to a one-time absent-private-suite exception for the mutation fix
under `docs/superpowers/plans/2026-10-10-mutation-checkpoints.md` only. Its absence remains
UNVERIFIED; the denied private execution will not be retried. No actual failure, public
check, independent review, hosted mutation completeness or Git protection is waived, and
no private-source access or future exception is granted. The isolated pre-exception tree
passed all six full-gate components; the updated tree requires fresh full verification
and independent review before guarded publication.

## 2026-10-10 — Hosted mutation constant-module repair (verification pending)

PR #54 candidate `2c90f008` passed required CI after one documented harness fixture-race
retry. The exhaustive hosted sweep exposed mutmut 3's unsupported constant-only
`alpha_research/figures/version.py`: its failed checkpoint and command logs survived.
Pinned mutmut 2.5.1 measured four actual mutations locally, all killed, with the unchanged
selected tests and audited exclusions. A narrow serial fallback and strict completed-cache
export retain this module, freeze backend identity and reject empty/unfinished records.
Fresh full gate, independent review and complete hosted sweep remain required on the repaired
tree. Mutation baselines, thresholds and private-source boundaries remain unchanged.
