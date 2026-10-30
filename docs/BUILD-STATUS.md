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

**2026-10-23 local candidate — unscheduled ML membership guard:** On main `99f2d472dd4511b446e1198ae80201e7207d089d`, schema versions 1 and 2 could accept `point_in_time` without a membership schedule. This local protective slice rejects that declaration at new export/preparation, retains `current_membership` only with its visible warning, and leaves historical artifacts byte-identical and inspectable with a `declared_unverified` status carried through CLI and web result/evaluation/tear-sheet projections. Existing frozen unscheduled PIT inputs cannot be trained or replayed by ALPHA/Qlib. No promotion gate changed; no schedule-v2 or date-varying model support is claimed. Focused synthetic contract, exporter, CLI, worker and web response tests passed; independent review approved the guard and read-only web projection. The full gate was not run, and this patch is not committed or merged.

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

### 2026-09-30 — bounded research diagnostics (verification in progress)

Isolated continuation from e54aa7a adds a non-admitted weekly-close classifier CLI, typed advisory
specialist review contracts and evidence-selector checking, and a bounded baseline-before-variants
procedure. Qlib, research approvals, D2, promotion and the MCP/REST tool surfaces are unchanged.
Versioned benchmark worlds add XNYS calendars and reconciling synthetic MTM; historical scenarios
and model evidence remain retained. The classifier, fixture and contract tests have focused
coverage; aggregate acceptance and the paired diagnostic panel remain pending in the
[delivery plan](superpowers/plans/2026-09-30-research-workflow-completion.md).


## 2026-09-30 — Research workflow paired closeout

Implementation `8d0db28` passed the canonical full gate on tree `7ad880237b475f741c8b19106e58ac8fcc8d139498e299c1210e5ba64a812a7d`, independent APPROVE and quant PASS. New calendar/MTM fixtures, weekly classification diagnostics, typed advisory reviews and bounded workflow guidance are delivered; historical Claude evidence remains unchanged.

The bounded ten-trial Codex-only diagnostic is complete. It supports further work on execution budgets, evidence reconciliation and information boundaries; it does not establish a general model ranking or validate an independent multi-agent architecture. Scenario-specific outcomes and control diagnoses remain in `tools/alpha-eval/results/workflow-v2-20260930/README.md` and the architecture audit, which are excluded from agent workspace exports. This public build record deliberately omits those answers. Closure documentation is committed only after its own exact-tree full gate.


## 2026-09-30 — Bounded baseline execution controller

A CLI-first controller now runs one frozen momentum baseline and validation, preserves durable attempts, reserves reconciliation time and publishes verified execution digests. It makes no model calls, launches no candidate variants, and grants no research admission or owner authority. The digest retains order denials independently of model narrative and checks execution quantities and session coverage. This bounds controller operations; surrounding-agent temporal read isolation and specialist-agent effectiveness remain unverified. Historical benchmark evidence is retained. See the [controller plan](superpowers/plans/2026-09-30-bounded-research-controller.md); exact-tree gate/review receipts determine acceptance.


## 2026-10-01 — Immutable rule execution in the bounded research controller

The isolated research branch adds embedded canonical rule specifications to `BaselineExecutionPlan`.
Both baseline and validation consume one immutable rule file plus its exact byte hash, and the
collector verifies returned rule identity. Existing named-rule behavior, CASH/long-only policy,
validation defaults and two-operation budget remain unchanged. Invalid or altered inputs fail
before engine execution. Default launch forms omit the new local-file options; existing authorized
generic CLI transport can relay them. No new REST schema, MCP tool or approval authority.

This addresses fixed-rule operator coverage, not agent pressure-turn behavior or whole-agent
information isolation. Historical Claude evidence is unchanged; no new model trial is claimed.
See the [plan](superpowers/plans/2026-10-01-immutable-research-rules.md) and
[usage guide](operations/bounded-research-workflow.md). Acceptance is recorded separately in
exact-tree gate and independent-review receipts; combined main/UI integration remains pending.


## 2026-10-02 — Research teammate advisory slice

Implemented in isolated `feat/research-teammate` on `73fb2a9`, preserving concurrent primary
checkout changes and historical Claude evidence. New CLI `research diagnostic suggest` verifies
retained evidence, measures existing drawdown episodes and proposes bounded follow-ups. Typed
external proposals permit novel questions with exact brief binding; no automatic execution.
Exploratory-analysis protocol now explicitly asks for useful unsolicited questions and justified
skips. Focused tests cover corrupt evidence, cutoff, loss diagnosis, reference binding and CLI.
Acceptance requires independent review and a fresh full-gate receipt; this entry is not a receipt.
The broader capability program, isolation and agent-reasoning benchmark uplift remain pending.


## 2026-10-02 — Closed synthetic investigation demo

Next slice after `535a461`, implemented in isolated `feat/research-investigation-demo`.
The evaluator exports neutral cutoff-scoped synthetic panels and dispatches four fixed measurements
from typed model proposals. Input mutation/path escape/network denial are tested by actual worker
preflight. Failed/denied attempts consume bounds; accounting failure blocks interpretation and
synthesis requires an inspection receipt. Fresh tools-disabled Codex turns retain raw evidence.
Designed controls distinguish a planted indicator, a frozen-indicator null and an accounting defect;
they are not engine backtests or evidence of real predictive causality. Model completion and research
quality are separate. The original general harness and historical results are unchanged.
Independent review and a fresh full-gate stamp remain acceptance requirements; this narrative is
not a receipt. Consult the retained development report for live outcomes and limitations.

Retained [synthetic live evidence](../tools/alpha-eval/results/investigation-demo-20261002/README.md)
records three final responses, 12 model calls and nine measurements. The planted indicator and
frozen-indicator null received distinct interpretations; the defect case stopped after inspection.
These observations do not establish benchmark uplift, unrestricted initiative or real trading edge.

Verification infrastructure: `ALPHA_PLAYWRIGHT_PORT` selects a separate test-only backend port
(default 8802, excludes owner port 8801); Playwright refuses reuse of another server. This fixes
observed cross-checkout verification interference without changing application routes or authority.


## 2026-10-02 — Investigation efficiency comparison

Implemented on isolated `feat/research-investigation-efficiency` after `d5f3cd4`. New
`alpha-eval investigate-compare` freezes three policies across the same three synthetic panels:
legacy adaptive, prechecked adaptive and fixed-evidence advisory synthesis. Automatic work
uses the existing attempt budget; lossless compact JSON retains complete evidence. Setup failures
are reserved and retained; missing or malformed usage stays unknown. Defaults and historical
evidence are unchanged. No model, dependency, statistical operator or application authority changed.

[Retained report](../tools/alpha-eval/results/investigation-efficiency-20261002/report.md): all nine
trials completed. Legacy used 12 calls / 127832 input tokens, prechecked 7 / 74126 (42.01% fewer
input tokens), fixed 3 / 32425 (74.63% fewer). A separate reviewer recomputed measurements and
checked all 22 transport usage records; no critical regression was observed in these outputs.
Three designed cases, one trial per cell, do not establish general reliability or real edge.
The simpler fixed-evidence baseline motivates richer task-selection tests before adding teams.
Fresh exact-tree full-gate and code-review receipts remain required for engineering acceptance.


## 2026-10-02 — Research judgment development cases

Implemented in isolated `feat/research-judgment-cases` after `77d6e94`. The optional evaluator
judgment path adds six contrasting cases, explicit missingness, cutoff-safe indicator provenance,
and a labeled measurement outage. It asks for competing explanations, discriminating evidence and
prioritized next work. Existing demo defaults and historical Claude evidence remain unchanged.

[Retained evidence](../tools/alpha-eval/results/research-judgment-20261002/report.md) separates
original A (4/12 finals, provider interruptions), recovery B (local path failure, zero inference),
and recovery C (8/8 finals, 16 calls). Independent review found no critical factual or causal failure
in the available finals. This does not repair A's completion rate or establish general reliability.
New transport metadata distinguishes provider errors from tool events. The production assistant
is not integrated with this optional judgment path; real-run export and independent execution
reconciliation are next. Engineering acceptance requires fresh full-gate and exact-tree review receipts.

## 2026-10-03 — Codex-first recorded-run runtime, first increment

Implemented on isolated `feat/codex-research-runtime` based on the delivered research checkout
`8a00b27`; concurrent primary workstation changes remain untouched. The CLI connects Codex App
Server to three fixed-case MCP tools, verifies actual execution isolation and thread policy,
retains durable tool/model budgets and evidence receipts, and validates final citation bindings.
Completed checkpoint resume revalidates evidence without spending another model turn. Transport
steering/interruption seams exist; workstation controls and chart input are not integrated yet.

Local acceptance used existing MSFT run `8648eedee80cbdc4` at its recorded 2024-12-30 cutoff.
The successful trial invoked execution, loss and follow-up tools and produced three verified
receipts. It preserved unverified coverage, distinguished fills from independent closed bets,
and proposed reconciliation before causal attribution. This is one operational smoke, not a
benchmark win or a claim of reliable trading judgment. Earlier development failures are retained:
initial isolation probe denied launch; first model turn could not discover tools with code-mode
host disabled; second model turn encountered missing per-tool preauthorization. Both unsupported
reports failed admission. The corrected configuration preauthorizes only the three fixed tools.

Raw cases and reports remain private under `/private/tmp/alpha-codex-acceptance-20261003`, outside
Git; they contain conversation history and should not be published. The source run and historical
Claude benchmarks were not edited. [Operation and limits](operations/codex-investigations.md),
[execution plan and remaining roadmap](superpowers/plans/2026-10-03-codex-research-runtime.md).
Engineering acceptance requires the canonical full gate and independent review of the final tree;
this runtime grants no research, confirmation, paper or trading authority.

### First-increment acceptance record

The 65 targeted runtime tests and all six canonical full-gate components passed. Independent
review approved the implementation and reproduced the three live receipts from source. Native
thread resume and CLI checkpoint resume succeeded without another model turn. Full-gate scope
was the 25-file increment against `8a00b2749984f937c994c0b7bc6b261de297cc89`; this is not cumulative
branch-versus-main acceptance. The passing implementation tree and private log are recorded in
the execution plan. Final delivery-record changes must receive a fresh full stamp before commit.
Earlier gate failures were retained and addressed: manual size and coverage were corrected;
two existing cancellation tests failed under concurrent load, passed in isolation, and passed in
the clean aggregate rerun with four workers. No test threshold or authority boundary was waived.


## 2026-10-03 — Frozen comparison evidence for Codex investigations

Continued `feat/codex-research-runtime` from `e111377`. New investigations optionally freeze up to four snapshot series with expected manifest hashes and operator-selected roles. Existing loss inspection reports exact daily endpoint price changes over strategy drawdowns, observed rows, declared instrument/fetch provenance and explicit blockers. Source integrity is reverified on every cached read; schema-v2 identities and completed checkpoints remain compatible. Schema-v3 cases bind the comparison plan, data root and evidence. No new tools, model providers, permissions or dependencies were added.

Forty-eight new tests passed, including actual MCP-to-CLI comparison execution, future-poison controls, sparse/malformed inputs and bounded reads. The fast gate passed after test-typing corrections. Independent review identified an all-member hashing limit gap; pre-hash manifest/member/payload bounds and pre-materialization row/schema limits resolved it. A real Codex session on a labeled synthetic fixture reported the known 40% versus 20% declines with limitations; both its resume and the earlier real MSFT v2 checkpoint preserved findings without another model turn. This confirms operational wiring, not trading reliability or economic benefit.

[Runbook](operations/codex-investigations.md), [scope and acceptance record](superpowers/plans/2026-10-03-codex-comparison-evidence.md). Final-tree full gate and independent review are required before commit. Snapshot provenance is not quality certification or historical-vintage proof; schedule completeness, causality and benchmark suitability remain unverified. Bounded acquisition and existing-contract data qualification remain next. Historical Claude results and concurrent primary UI work were untouched.


## 2026-10-04 — Bounded private comparison acquisition

Continued `feat/codex-research-runtime` from `dd1c745`. An inspected parent investigation can
reserve one explicit batch of up to four daily Tiingo stock/ETF comparisons. The trusted CLI
runs bounded downloads through the existing ingestion checks in a private store, retains emitted
receipts/quarantine, and publishes a snapshot and comparison plan only when all requests pass.
Completed reads reverify hashes and replay raw parsing/quality checks; failed or ambiguous batches
never automatically retry. A separate comparison-data root leaves original run resolution unchanged.
The model retains its three read-only tools. No canonical data, research admission or trading
authority is granted; historical Claude evidence and concurrent workstation edits are preserved.

Fixture tests cover CLI acquisition, private snapshot-to-investigation handoff, unchanged parent
budgets, cached reads without credentials, tampering, failed batches, bounded transport and future
poison with discriminating controls. These are synthetic operational checks, not real-market
findings. Live Tiingo acceptance is **UNVERIFIED**: no provider credential is configured here.
Declared instrument metadata, proxy suitability, historical vintage and independent-source
agreement remain unverified. Final-tree full gate and independent review are required before commit.

[Runbook](operations/codex-investigations.md),
[scope and acceptance plan](superpowers/plans/2026-10-04-bounded-comparison-acquisition.md).
Next: live-provider acceptance when configured and workstation integration after reconciling its
separate active changes; macro attribution, regime learning and strategy engineering remain later
increments, not implied capabilities of this download path.


## 2026-10-04 — Managed recorded-run investigations in the workstation

Continued `feat/codex-research-runtime` from `4b93c97`. The shared run report now starts and
restores CLI-owned investigations, shows evidence separately from hypotheses and proposed tests,
and supports same-case follow-ups, cancellation and refresh recovery within durable budgets.
Explicit comparison previews lead to private acquisition and a linked new exposed case; an
interrupted child publication can finish without another download or duplicate child. Verified
list/show projections do not initialize sessions or acquire data. Ambiguous model reservations
remain blocked. Parent-death/deadline supervision reaps the owned Codex process group.

Browser acceptance passed through actual HTTP, CLI processes and persisted state, using labeled
model/provider doubles. Separate live Codex CLI and web follow-ups passed; active-turn cancellation
left none of four observed descendant processes alive and preserved consumed turn budgets. An
initial cancellation status mismatch was fixed and rechecked against live Codex. Live Tiingo
acceptance remains UNVERIFIED without a configured credential. These are operational checks,
not evidence of trading reliability. The final staged tree requires independent review and the
canonical full gate before commit; its receipt records aggregate acceptance.

[Plan and acceptance scope](superpowers/plans/2026-10-04-workstation-investigations.md),
[operator workflow](operations/codex-investigations.md). Primary checkout's concurrent UI is
untouched; this branch's acceptance does not certify a future combined tree. Codex stays the only
reasoning model; Claude artifacts, research admission and trading authority are unchanged.


**2026-10-10 existing research-runtime reconciliation (local candidate):** The thirteen committed
bounded runtime increments through `b18cf921` are merged without a commit against main `454c940f`
in an isolated checkout. Recorded-run investigations, immutable case budgets, scoped MCP findings,
frozen comparisons and managed acquisition/cancellation/follow-up/handoff coexist with main's
current API, recorded panels and authority controls. Bounded compatibility regressions repair
custom Codex home propagation, fail-closed event handling and disposable backend/test isolation.
Generated OpenAPI, SPA and Atlas describe the combined source. Fresh primary-source quant checks
pass; cumulative public full verification and independent risk acceptance are still pending.
Private-suite, current live Codex isolation and provider acceptance remain unverified. No standing
exception or publication permission is assumed. See the research-runtime reconciliation plan.


**2026-10-07 — Technical chart language (StockCharts Classic/Default grammar).** Owner request:
make the primary analytical chart read as market-analysis software rather than a web component.
The default Bokeh price renderer is replaced by `frontend/src/components/technical/`: one BokehJS
document per chart with an RSI / price + volume underlay / MACD shared-border stack on an
observation-spaced axis (weekdays or intervals without an observation are marked on the date strip), candles
coloured by prior close and filled by open, dense 1/2/2.5/5 right value axes, a weekly date strip
with bold months and years, coloured in-panel legends with values, right-axis value tags, one dense
OHLC/Chg header line, no toolbar, x-only pan/zoom and visible-window autoscale. Classic is the default
`chartStyle`, Default the alternate (workspace toolbar select). The studies template (MA 50/200,
RSI 14, MACD 12/26/9) is offered once to profiles with no studies; the SPA still computes no study —
a study the CLI refuses as longer than the window is dropped by name (the CLI sentence is pinned in
`tests/unit/test_chart_overlays.py`). Recorded equity/drawdown/Sharpe series and histogram/QQ plots
share the chrome; the orphaned Bokeh market path (`ScientificMarketCanvas`) is removed. No backend or
API change. New `e2e/technical-chart.spec.ts` (Classic/Default baselines, hover, x-zoom autoscale,
skipped study, gap marks); chart document and technical-chart baselines taken for darwin and, in the
Playwright 1.61.1 noble container, for Linux (Linux falls back to DejaVu Sans; geometry unchanged).
Recorded series, cartesian plots and the price footnote read the same `--tc-*` tokens, so Default
applies everywhere. The opt-in perf budget spec was
measured against `main` on the same machine: both exceed the 34 ms p99 intermittently there (main
27–35 ms, branch 28–47 ms; medians ~10 ms each). [Plan](superpowers/plans/2026-10-07-technical-chart-language.md).

**2026-10-08 — Technical-chart cleanup review correction (unmerged).** PNG exports now composite the DOM calendar, legends, tags and gaps plus the title/OHLC header over the native Bokeh canvases. Original downloads omitted these layers. Download regression and fresh full verification govern acceptance of this correction; the earlier full stamp is invalid after source edits. Opt-in performance limitations remain recorded in the chart plan.

**2026-10-08 — Repository cleanup checkpoint (in progress).** Outstanding chart and weekly-mutation changes are being completed in their existing worktrees. Initial main regular CI passed; nightly mutation cancelled after six hours while preceding checks passed. Independent review reproduced report-validation holes and a chart PNG export omitting DOM calendar/legend layers. The research import contract omitted the patterns prohibition; a failing regression reproduced it and the corrected boundary passes. Current README and architecture guidance is reconciled to source. No final combined gate, merge, hidden-suite acceptance or scheduled-workflow completion is claimed. [Cleanup plan](superpowers/plans/2026-10-08-repository-hygiene.md).

**2026-10-08 — Expanded repository and GitHub cleanup (in progress).** Three merged clean worktrees, five merged local branches, three merged remote branches and two superseded stash entries were retired after preserving full history, working-tree patches and byte-verified local state. Six undelivered research checkpoints are consolidated under `backlog/research-runtime` with original tips archived. Obsolete draft PR #52 is closed and preserved under a GitHub archive tag. The missing CASH fee-affordability fix is being ported separately; no unfinished research features are promoted. The prior combined tree passed all six canonical components; the expanded tree requires fresh verification and hidden-suite acceptance remains blocked. [Cleanup plan](superpowers/plans/2026-10-08-repository-hygiene.md).

**2026-10-08 — Primary checkout consolidated; final acceptance pending.** The primary integration checkout is the only remaining worktree. Original changed source/workflow paths and the transferred staged Git tree were verified exactly before removing duplicate checkouts. Eight redundant merged/preparation local branches, four obsolete/merged remote branches, six research checkpoint branch names and two superseded stash entries are retired with recovery refs/archives; the unique research lineage remains under `backlog/research-runtime`. GitHub has no open PRs. The recovered CASH affordability fix reproduced seven failures before the port and passes 41 focused tests plus one existing expected failure afterward, including a deliberately leaky bias control. A fresh primary aggregate gate and independent risk review remain required; absent hidden tests continue to block final acceptance, commit and merge. [Cleanup plan](superpowers/plans/2026-10-08-repository-hygiene.md).

**2026-10-08 — Exact viewport volume mask and orphan recovery.** The volume renderer now restricts painting to every original bar rectangle intersecting the observation-index viewport, including partial edge bars, while preserving the full native source and colors. Four failing-first geometry tests are covered by 23 passing model tests; seven focused browser tests pass with unchanged screenshots and actual PNG export. An isolated timing run passed at 28.5 ms p99; repeats were 26.3/26.2/43.0 ms, so intermittent timing remains unresolved under unchanged limits. A discovered unregistered worktree folder was retired after byte-verifying an archive of all 181 noncache files; its partial source is preserved, not assumed delivered. Final aggregate and hidden-suite acceptance remain required. [Cleanup plan](superpowers/plans/2026-10-08-repository-hygiene.md).


**2026-10-09 — Malformed PIT bar error boundary corrected (unmerged).** Visible malformed bars now raise chained `DataError` with symbol, timestamp and original validation reason instead of leaking Pydantic errors past CLI handlers. Point-in-time filtering remains first; invalid rows are neither dropped nor coerced. Twenty failures were reproduced before the source fix; all 27 focused source/bias/public-seed tests pass, including future exclusion, a deliberately leaky twin, and CLI exit 2 with no run publication. The previous primary tree passed all six canonical components; this changed tree requires fresh aggregate verification and independent review. Hidden-suite acceptance remains UNVERIFIED/BLOCK; no commit, merge or scheduled-workflow deployment is claimed. [Cleanup plan](superpowers/plans/2026-10-08-repository-hygiene.md).


**2026-10-09 — Exact volume color views (unmerged).** Post-mask profiling exposed full-source CSS color materialization on every view update. Complementary up/down views now share the full native x/volume source with scalar style colors, retaining previous-close classification, equal-close bars, partial viewport intersections, width, scales, cursor and exports. Three failing-first partition tests are covered by 26 passing model tests; seven focused browser tests pass with unchanged screenshots and PNG export. The new profile recorded zero `_from_css_array` samples, versus about 165.5 ms directly before the change. Profiled/ordinary p99 passed at 27.2/27.3 ms; a fixed three-repeat run passed at 27.2/27.3/27.2 ms against the unchanged 34 ms limit. This evidence improves the previously intermittent timing lane without promising every future machine/run will pass. Fresh final aggregate and independent acceptance remain required; hidden-suite execution stays UNVERIFIED/BLOCK. [Cleanup plan](superpowers/plans/2026-10-08-repository-hygiene.md).


**2026-10-10 — Preserved feature reconciliation (local, unaccepted).** Recovered intended technical charts, exact PNG layers and volume views, CASH fee-affordability rejection evidence, typed PIT errors and core-only research import hygiene into an isolated checkout. Standing engineering holdout policy and active mutation/maintainability work are excluded. Original index/source bytes remain preserved and unchanged. Focused verification and final aggregate acceptance are pending; no publication or integration is claimed.


**2026-10-10 — Preserved feature focused verification (local).** CASH/PIT/core/artifact/boundary regressions:69 passed. The chart PNG lost its visible outside-window annotation warning and gradient-based volume swatch; two failing browser regressions reproduced both omissions, then eight technical-chart tests passed after sharing the warning text and painting the same three swatch rectangles in DOM/export. Classic/Default screenshots are unchanged. Frontend lint/type/build/unit-coverage and Python import/lint/format checks pass. Packaged SPA rebuilt from this source. Fresh aggregate and independent release acceptance remain pending; no new private-suite exception or standing policy is adopted.


**2026-10-10 — Preserved feature integration corrections (local, unaccepted).** Independent review reproduced a strict chart API response failure for CASH pretrade `execution_rejection` events and a native recorded-series PNG export missing its visible value tag. Backend/OpenAPI/frontend event contracts now include rejection events; an artifact-bound response regression fails before and passes after correction, and all 42 chart API integration tests pass. The native Save export now composites the recorded tag while preserving Save/Copy/Open controls and prompt; its browser regression fails before and passes after repair. Empty export headers retain image dimensions. Independent source review found no remaining issue in those repairs; the pixel placement of the recorded tag is not separately asserted. Type/lint and both lifecycle unit tests pass. Packaged assets are rebuilt. A new exact-tree canonical full run follows these final sources; release acceptance remains blocked by the unchanged absent-private-suite rule. No scoped exception has been extended, no feature committed or published, and the original shared index/source remain byte-identical.


**2026-10-11 — Recovered-work scoped delivery authorized.** The owner approved separate
chart/CASH/PIT/hygiene and existing research-runtime PRs/merges after all available checks,
with the [one-time private-suite exception](operations/2026-10-11-recovered-work-private-suite-exception.md).
Private coverage remains UNVERIFIED; the standing policy is excluded. Recovered feature source
previously passed all six components on f54af6df. Refresh exact-tree validation and independent
review for this delivery record; exact-target hosted CI and legitimate dependency order remain
required. No live-provider acceptance, strategy admission or trading authority is conferred.


**2026-10-11 — Existing research-runtime delivery authorized.** Existing source through b18cf921
previously passed all six components on fefe81cb, with fresh quant verification and no independent
source findings. The owner approved the one-time exception documented above, keeping private
coverage UNVERIFIED. The combined candidate incorporates recovered chart/CASH/PIT/hygiene source
and preserves recorded investigation/report, immutable-rule, budget and authority boundaries.
Regenerate contracts/assets and obtain fresh full/source/quant/independent review plus exact-target
hosted CI before merge. Live Codex0.161/Tiingo acceptance remains UNVERIFIED; no live credentials,
private data, new strategy authority or standing policy is introduced.


**2026-10-11 — Hosted research configuration-test portability repair.** Research PR #56's
first hosted backend gate failed three public configuration tests because their executable
lookup relied on Codex being installed on the test machine. The same failures reproduce locally
with Codex removed from PATH. Those tests now discover a synthetic executable in a fixture-only
PATH, assert its exact launch argv, and retain configuration/auth-reference/isolation assertions.
A new negative test removes the fixture executable and verifies the production unavailable error
before runtime-directory creation. All ten environment tests pass with no installed executable;
production behavior and live-provider acceptance are unchanged. Fresh exact-tree independent
review, canonical full and hosted checks follow this bounded test-only repair.
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

## 2026-10-10 — Hosted mutation deadline repair (verification pending)

PR #54 head `1605b5b` passed fresh local full, independent review, 213 focused tests and all seven
hosted CI checks; its actual hosted constant-only fallback measured four killed of four mutants.
Run `38052927037-1` retained explicit 5400-second failures for data (224/239), boundary (1083/1810)
and crypto crowding (971/1333), with error checkpoints and terminated descendant process groups.
Singleton module jobs therefore cannot establish full hosted completion. Owner-authorized repair
partitions complete pinned-backend canonical mutant inventories into up to four exact-name fragments
per functional module, with exact per-mutant aggregation and unchanged test/floor/verdict semantics.
Up to 205 jobs repeat setup/preflight/statistics at most four times, retaining eight concurrent jobs
and two workers each. Failed and successful evidence is retained; no partial run is acceptance.
The repaired tree still requires real failed-module reproduction, final full/review and a new
complete hosted sweep/required CI. Private engineering coverage remains UNVERIFIED under the same
scoped exception; original shared work and unrelated reconciliation lanes remain untouched.

The same run also retained event-study (233/580) and renderer (651/1778) deadline failures.
`alpha_validation/_atomic.py` failed separately after successful stats collection found no associated tests
for its 30 generated mutants. The scoped adapter adds explicit successful-collection certification
for conservative no-tests accounting, with negative regressions; actual-tool validation is pending.

Actual final-code diagnostics completed locally: data accounted for all 239 canonical mutants
in four disjoint fragments (176 killed, five survived, 58 timeout; 0.7364 score fails its unchanged
0.8182 floor). Complete collection certified the 30 generated `_atomic` mutants as conservative
no-tests, zero kills and score failure at the unchanged 0.90 floor, with 527 real test records.
The first two data fragments used the initial exact-name CLI adapter; the last two and `_atomic`
used the final pinned adapter. These are diagnostic receipts, never full hosted acceptance.
The old hosted head also retained gate-packet timeout progress 2250/3019. New exact-head hosted
completion, final canonical full and fresh bound review remain acceptance requirements.


## 2026-10-11 — bounded WAL negotiation during hosted mutation collection

Final fragment head `31e64420` generated the complete hosted inventory (52 modules, 205 jobs,
21,555 functional mutants), independently validated against commit/run identity and source hashes.
One `_arrays` fragment failed unmutated collection at the existing public concurrent v1 migration
test with `DataError("cannot initialize control store")`; other fragments passed. The initial
assertion omitted the chained cause. A real temporary-database contention reproduction captured
`SQLITE_BUSY` (code 5) at `PRAGMA journal_mode = WAL`, wrapped by the same error.

The bounded follow-up retries only exact `SQLITE_BUSY` outside a transaction, within the existing
configured busy-timeout budget for WAL negotiation (normally five seconds). Each attempt receives
only the remaining budget, and the original timeout is restored. This is not a bound on all of
`_open`; migrations retain their separate existing waits. Non-BUSY errors and exhausted budgets
still fail loudly. Migration ordering, backups, protected schema and owner authority are unchanged.
The existing migration assertions/timeouts/test selection remain; failure-only diagnostics retain
chained traceback, statement and SQLite code. A real contention regression failed before and passed
after the fix; budget exhaustion, read-only failure and timeout restoration also passed.

Fresh public full verification, independent review and new exact-head complete hosted acceptance
remain pending for this follow-up. No partial/stale hosted verdict, score floor or private-suite
exception is reused or broadened. SQLite reference: https://www.sqlite.org/c3ref/busy_handler.html.


### 2026-10-11: measured fragment sizing follow-up

At `da463cee`, hosted sweep `38136100567` failed rendering fragment 46 at the unchanged
5400-second mutation budget: 441 of 444 assigned mutants reached terminal status. The checkpoint
remained an error and strict aggregation did not accept its three unfinished mutants. The run was
explicitly cancelled after retaining its failure and all 69 started checkpoint/log artifacts;
60 fragments completed, eight were interrupted and 136 never started. None is reused for acceptance.

Cross-group sizing considered every started fragment, including event's 5198.5-second completed
phase and conservative elapsed/progress estimates for interrupted leadlag jobs. Balanced sorted
round-robin partitions now cap each fragment at 96 mutants. The same complete 52-module inventory
produces 250 jobs, below the unchanged 256-job hard limit. Exhaustive keys, module/test scopes,
associated tests, worker/concurrency limits, timeouts, floors and report-only score semantics remain
unchanged. More setup and test-statistics runs are the explicit cost. Timing projections are estimates;
never-started groups and a fresh complete hosted sweep remain unverified.

Focused red regressions reproduced the old partition failure before implementation. Fresh focused
checks, canonical full verification, independent review and exact-head hosted CI/complete sweep
are required before this follow-up can be accepted or merged. Private suites remain unverified under
the existing scoped owner exception; standing policy is unchanged.


### 2026-10-12: deterministic signed PIP oracle follow-up

Sweep `38151251890` at `3c3a7760` completed 249 of 250 fragments successfully. PIP-miner
fragment 4 (index 147) failed during clean test statistics; its error checkpoint retained all
94 assigned mutants as unmeasured. Aggregate job `114573250539` correctly rejected the
unfinished record. This was an oracle failure, not a phase deadline: the differential
reference used unmirrored negative-total returns despite the documented symmetric ranking,
and a module-global RNG made inputs depend on selected test order. Seed 11 at normal-draw
offset 4250 reproduces the logged mismatch to float64 precision; the hosted order was not logged.

The bounded test-only repair gives each PIP oracle/unit test its own seeded RNG and checks
positive, negative and zero totals explicitly, retaining the counterexample and running-peak
negative control. Production maths, tolerances, test scope, all mutant identities and score
floors are unchanged. Repeated/reversed execution, applicable static checks, fresh canonical
full, independent review and new exact-head hosted CI/exhaustive acceptance remain required.
Private coverage remains UNVERIFIED under the existing scoped decision. PR #54's description
remains untouched; failed/partial historical verdicts are never reused for acceptance.


### 2026-10-12: post-merge harness-template isolation follow-up

PR #54 merged as `5b0b422d` after exact-head CI and exhaustive sweep `38233472012`
passed. Independent aggregation verified all 52 modules, 250 checkpoints, 252 unique
artifacts and 21,555 functional plus four legacy constant mutants; twelve score misses
remain report-only under unchanged floors. The merged Git tree equals the accepted tree.
PR #54's description remained byte-for-byte unchanged.

Post-merge CI `38272832758` reported 5,321 tests passed and coverage 93.13%, but one
harness fixture setup failed: copying the session template raced Git's removal of
`.git/objects/maintenance.lock`. The bounded follow-up disables automatic maintenance
only in the throwaway template before its initial writes; copied fixture repositories
inherit the setting. Copy failures remain visible, and production/Git user configuration,
mutation source, scope, inventory and baselines remain unchanged. A forced-maintenance
TRACE2 regression fails before the fix and passes after it; its positive control launches
actual foreground maintenance and packing with local suppression removed.

Focused public checks pass; fresh canonical full, independent review and hosted checks
remain required. Private coverage remains UNVERIFIED. This standalone fixture delta has
no risk-tier, quant or protected-path trigger, so the specialized private-suite review rule
does not apply. No exception is inferred or broadened; no private execution has been retried.


### 2026-10-13: combined post-merge fixture and single-wheel resize repair

The standalone fixture follow-up passed ordinary review, but its final full stopped at
`quant-workspace.spec.ts:135`: one trusted wheel left the visible range unchanged. The
failed trace and six isolated diagnostic passes are retained without treating the latter
as acceptance. The chart owner then proved the ordering defect deterministically: after
resize and one trusted wheel, releasing the pending draw restored the old span of 499
in all three viewports.

The bounded frontend correction restores the captured range before a forced resize paint,
so the queued restoration completes before the next input. The actual-component regression
waits for draw completion and asserts a settled contracted span after exactly one trusted
wheel. All eighteen focused original/regression cases pass on the fixed source; the
original quant-workspace test and fifty PNG baselines remain byte-identical. The full
fixed browser and final combined canonical full, fresh review and hosted CI remain
required; their acceptance is not inferred from focused results.

This target combines that two-file correction with the disposable Git-maintenance fixture
repair, its public regression and truthful scope documentation. Frontend build artifacts
are copied only from the hash-verified frozen wheel preparation and will be checked again
by the combined build/freshness gate; Atlas inputs are regenerated for this combined tree.
Private coverage remains UNVERIFIED; these ordinary paths trigger no specialised private
review or new exception. Protected mutation staging, extreme ticks, mutation inventory,
floors, exclusions, policy and PR #54's description are unchanged.

## 2026-10-13 — Bounded maintainability delivery

Integrated the cleanup-only runtime/tests delta on accepted main `d914be9f` (PR54 and PR57). Immutable crypto writes and pure control JSON helpers are separated without changing bytes, limits, facade names, migrations or authority. The accepted WAL busy retry, disposable fixture repair and wheel restoration remain unchanged. Frontend checks build/type-check once before built-only browsers; standalone browser commands still build. Added focused development navigation. Source relocation intentionally changes new execution fingerprints; historical evidence remains untouched. The owner-approved one-time cleanup exception records unavailable private coverage UNVERIFIED; no standing policy change. Fresh target acceptance is recorded externally after public full verification and independent review; prior prototype evidence is not reused.


**2026-10-13 — Recovered feature integration against accepted cleanup (pending).** PR55 is refreshed against accepted main d3043d6c (mutation checkpoints/WAL, disposable Git fixture, chart wheel order and bounded maintainability). Source repairs are retained; historical feature and acceptance records remain intact. Conflicting SPA and Atlas output is regenerated from the combined source. Fresh focused tests, independent review, quant verification, all six canonical components and exact-head/postmerge CI govern final acceptance. Private coverage remains UNVERIFIED under the existing recovered-work scoped exception; protected mutation staging remains separate and unapproved.


**2026-10-13 — Technical price-mount lifecycle repair.** Fresh clean-context review found that a cancelled asynchronous technical-price mount registered its UTC endpoint before the component checked whether its effect was live. If it resolved after its replacement, stale cleanup removed the replacement link. Two actual-renderer unit regressions fail on the old source (premature registration and missing replacement cursor delivery). The renderer now exposes deferred activation, and the component activates only after its live check, matching the recorded-plot protocol. Both completion orders pass; native data, rendering geometry and screenshot baselines are unchanged. Previous 5a855ce4 full/CI evidence is retained as historical evidence; fresh final-tree full, independent review and exact-head CI remain required.

## 2026-10-13 — PR55 accepted feature integration

PR #55 merged as `cf7ce4a3` after the repaired exact candidate passed the six-component canonical
full gate (872.35 seconds), fresh clean-context independent review, all seven required head checks
and all seven post-merge checks. The merged Git tree exactly matches the reviewed and tested tree.
The lifecycle correction defers technical-chart registry activation until the asynchronous component
confirms that its mount is still live; both actual-renderer completion-order regressions pass.
Private coverage remains UNVERIFIED under the existing recovered-work exception; no standing policy
or protected-staging permission was added. The exact acceptance receipt is retained in the external
reconciliation evidence directory.

## 2026-10-13 — PR56 research integration candidate

The preserved research runtime from `b18cf921` is being integrated with accepted main after PR #55.
This candidate retains the bounded `ControlStore` WAL retry, pure control JSON and crypto persistence
helpers, fixture-only Codex executable, deterministic diagnostic oracle and single-wheel range-order
repairs. The supported Atlas generator refreshes the live CLI cache before regenerating its outputs.
The quant review found and the author corrected one docstring: the reported binary score is half
the two-category Brier loss. The first canonical full reached 93.09% coverage (5,717 passed, nine
skipped) but stopped because the combined manuals exceeded the 6,000-byte cap. The manuals are now
6,000 bytes. Acceptance requires fresh exact-tree quant confirmation, independent review, canonical
full, required hosted CI and post-merge checks. Private coverage and live Codex 0.161/Tiingo acceptance
remain UNVERIFIED; no credential access, hosted-provider activation, new strategy authority or
standing policy is added. Protected mutation-staging work remains separate and unapproved.


## 2026-10-13 — Scoped preflight and tooling integration candidate

PR56 was accepted as `31479cad` after seven head and seven post-merge checks with exact tested-tree parity. This isolated followup inserts the existing public 6000-byte manual assertion after locked setup and before backend lint/types/coverage. All former checks and receipt binding remain; failure stops costly steps and old backend definitions cannot reuse receipts. The failing-first regressions reproduce missing ordering, invalid6001 acceptance and stale-receipt acceptance on the unchanged gate. Successful full throughput is not claimed improved.

Compatible development tooling patches align Vitest/coverage at4.1.11, js-yaml4.3.2, brace-expansion2.1.7 and source-map-js1.2.2. The accepted build/type/browser ordering, production Bokeh3.10.0/sprintf1.1.3 and application source remain unchanged. The upstream sprintf advisory remains explicit and unpatched; separately frozen renderer/readiness changes are not included. Current scripts, tests, plans, documentation and generated Atlas are finalized before exact-tree full/review/CI acceptance. The owner-approved four-followup absence-only exception leaves private coverage UNVERIFIED and grants no private access, failed-test waiver or standing policy.


The first frozen source passed all six local components but is retained as superseded evidence: a bounded diagnostic showed the new ordering test falsely rejected the existing required oracle/mutation suffix for quant-source changes and unknown history. The regression now controls those three impact inputs explicitly and checks that the conservative suffix remains. Runtime checks, selectors and floors are unchanged; repaired-source acceptance requires fresh binding, review and full verification.

## 2026-10-13 — Extreme finite chart display candidate

On accepted PR #59 main `2172406c`, the isolated chart follow-up keeps tiny and very large finite
observations visible with bounded scientific tick formats and scientific value labels. The recorded
series path also saturates padded display bounds at finite numeric limits, and a narrow-host browser
regression checks that scientific value tags remain within the clipped plot host. A readiness
docstring now describes the typed overall status without implying that legacy per-requirement rows
are satisfied; those details remain unavailable and fail closed. Ordinary values, observations,
exports, statistical/backend arithmetic and dependency versions are unchanged. The upstream
`sprintf-js` advisory GHSA-hp3w-g68c-fv3c remains unresolved. Focused public checks pass; canonical
full, fresh independent review, hosted checks and post-merge verification remain pending. Private
coverage remains UNVERIFIED under the existing approved scope.

The first hosted run on PR #60 passed six required checks but failed two chart-document screenshot
profiles after explicit initial Bokeh width changed the recorded layout. The follow-up removes that
initial width override while retaining measured width updates on resize. Browser checks now assert
canvas geometry both immediately after mount and after narrowing the host, and all three local chart
document screenshot profiles pass. This exact follow-up still requires a fresh canonical full and
hosted checks; the earlier full and hosted results do not certify it.

Failure-only Linux artifact run 38437838761 showed the ordinary MACD screenshot reserved a 167px
Bokeh right gutter because a histogram residual (`-1.7763568394002505e-15`) was treated as a
genuine scientific label. The Bokeh shadow root confirmed that the plot frame narrowed by about
100px while the host and viewport stayed unchanged. MACD display extents now treat values strictly
below one ULP of the corresponding source close as cancellation noise; labels retain their prior
fixed-decimal form and backend study values remain untouched. A browser regression checks the
shadow-root gutter and signed fixed-decimal label, with PNG export checks retained. Fresh full
verification, independent review, and exact-head hosted checks are pending.


## 2026-10-14 — Existing ML ensemble response compatibility preparation

A synthetic exchange reproduction through actual FastAPI response validation on main `fc6d3b90`
returned HTTP 200 for v1 LightGBM detail/tear-sheet but raised response validation errors for the
already-supported schema-v2 `rank_ensemble_v1` detail and its two-fit fold diagnostics. The CLI and
isolated worker contracts already support those values; the web projection forwarded them unchanged.
The bounded correction extends only the three response literals to the existing supported values.
Regression tests exercise both versions through the real projection/router, preserve complete
projected diagnostics, and reject unsupported schema/model/fit values. OpenAPI and generated client
types follow the corrected responses. Numerical behavior, worker capability, artifact validation,
subprocess isolation, bounds, strict extra-field rejection and protected gates are unchanged.
This was an isolated preparation candidate; its focused evidence did not establish combined full,
hosted CI, private-suite or release acceptance.

### 2026-10-14 — Combined atomic-publication tests and ML response compatibility candidate

The combined candidate adds public contract tests for `alpha_validation._atomic.write_text` and
correctly discriminates existing ML response contracts: schema 1 pairs with LightGBM, while schema 2
pairs with `rank_ensemble_v1`. Prepared exchanges with incompatible pairs fail response validation
even without a result artifact; OpenAPI and generated TypeScript encode the same pairing. The
tear-sheet now describes the actual fit count per fold. Supported Atlas refresh regenerated the live
226-command cache and derived views. The 56 focused backend tests pass. The owner-authorized documented
holdout suite passed 17 tests, and the validation copy passed all six canonical full-gate components;
fresh independent review approved that validated tree. Hosted head and post-merge results are tracked
separately in PR acceptance evidence, and private coverage remains UNVERIFIED. No worker, numerical,
research-authority, or protected-gate behavior changed.


## 2026-10-15 — Current-main documentation and Atlas upkeep preparation

Rechecked the old `d3043d6c` maintenance findings on accepted main `b2c43735`. README already names
all six canonical gate components, the thirteen import contracts match `pyproject.toml`, and the
AGENTS/ADR/plan delivery labels are corrected. The committed CLI cache matches all 226 live command
records with no missing, removed or changed entries; the eight generated Atlas outputs were fresh
before this slice. The ADR's five-component candidate acceptance remains accurate September history
(the original delivered definition had five components); it is not rewritten as a newer receipt.
The remaining harness-guide drift described only three adapter entrypoints and implied that Bash
had no interception. The guide now describes the already-wired fourth owner-action input guard and
its bounded route/credential-reference scan. Runtime, settings, protected instructions, gates and
authority are unchanged. The supported Atlas CLI refresh and regeneration produced byte-identical
cache and generated outputs; this documentation correction does not change the Atlas input set.
This isolated patch is preparation only; no publication, merge or heavy gate is performed, and
final integration acceptance remains with the integration owner.

## 2026-10-15 — Selected theme CSS in isolated mutation staging (in progress)

The staging harness copies the checked-out `index.css` and `theme.generated.css` only when
`tests/unit/test_theme_drift.py` is selected, and includes the minimal `apps` tree in mutmut's
nested execution copy. Both CSS inputs matched accepted base `b2c43735` in this candidate; the
harness intentionally reads working-tree paths. Missing source fixtures fail loudly. PR #62
already supplies the separate public CLI helper; this candidate does not replay that accepted
change. The public staging regression passes 4 tests, the focused staging/sweep/fragment set passes
76, and the selected theme-drift test passes 54 tests from an actual isolated tree. The configured
test selector, mutant inventory, score floor, tolerance, timeout, exclusion rules, concurrency and
acceptance rule are unchanged. Restoring the selected theme cases that previously failed staging
preflight and were deselected can change effective executed cases, denominators and measured
outcomes; no mutation-adequacy claim is made. No exhaustive mutation sweep or private source/data
access was performed; private coverage remains UNVERIFIED.
The standard protected-path review, canonical full, required hosted CI, normal merge and post-merge
CI are evaluated separately against the exact candidate. This entry records the scoped behavior
and local public checks; it does not claim mutation-adequacy scores or protected release acceptance.

## 2026-10-15 — Synchronous cloud root/frontend setup

The installer uses locked root/frontend dependencies, installs pinned Chromium, and runs a bounded
CLI smoke plus a static-page Chromium browser-runtime smoke while preserving original failures. It
does not run frontend app E2E tests. Cache defaults are process-local; the cloud
environment must provide persistent variables to later shells and MCP servers. Linux Chromium
system libraries are a host prerequisite. A separate cold-bootstrap run passed in 62.55 seconds
on source candidate `b2c43735`; its exact receipt and SHA-256 are recorded in the cloud setup plan
and reconciliation evidence. That run does not establish full-gate or release acceptance for the
newer integrated tree. Exact-tree full, independent review, and hosted acceptance are tracked
separately in the delivery receipt.

## 2026-10-15 — Cloud test ownership candidate

The gate now gives Linux pytest commands a separate owning subreaper, preserving command
status, output and every cancellation/disappearance assertion. Non-Linux execution is unchanged.
Synthetic urllib tests isolate their fake opener from inherited proxies; retained subprocess test
finalizers close stdout. The pause/cancel browser test awaits dialog acceptance and the performed
action instead of ending at challenge capture. Setup also supplies a writable Semgrep version-cache
file. All five owner-confirmation browser journeys await dialog acceptance and the perform response.
The recorded-series export test explicitly awaits its filename prompt before the download.
Lease-test PID readiness is atomically published; the doctor fixture includes the owner runner.
Production proxy policy, application cancellation, warnings and coverage thresholds are unchanged.
Original failures and candidate red/green logs are indexed under ignored `.alpha/state/` task evidence.
Independent exact-candidate review and the unchanged full gate remain required for acceptance.

## 2026-10-16 — Four-family Monte Carlo explanation draft

Added an operations overview and separate IID empirical, causal-volatility Markov, Student-t
log-account-return and Kronos replay guides. All four remain required; no algorithm, source
behavior or ADR authority changes. The guides distinguish fitted periods, observed account-return
resampling from fresh market/engine execution, scenario ranges from Wilson intervals, Student-t
moment/numerical limits, and controlled-test evidence from real-model or market acceptance.
Documentation/link checks and independent review are recorded separately in ignored task evidence.
Parent review and required full validation remain pending; this draft is not release acceptance.

## 2026-10-16 — Context stewardship and retrieval, slice-one candidate

The existing context index now links the pilot's artifact stewardship roles and six bounded retrieval
routes. Area maps add existing CLI, crypto-family, D2 and full-gate source/check relationships, and
state missing dedicated relationships and representative coverage limits. Randomized-price-null
navigation remains distinct from all four retained Monte Carlo path-risk families. The inspection
base is accepted main `dd5a924d709b8d60c97492043f2a82dac976105a`; protected links receive metadata
checks only. Source, tests, generated outputs and private research are unchanged.
A repeatable Git/source-review procedure distinguishes link/byte freshness from semantic correctness
and executed acceptance. The reused task-local link checker and synthetic positive/negative cases,
focused checks, independent reviews and exact-tree full-gate receipts are recorded separately under
ignored task evidence. This entry describes the candidate, not a passing receipt or release approval.
Slice one remains in progress pending parent review; historical-reference and test-layout slices are
pending. No test moves, commit, PR or publication are part of this slice.

## 2026-10-17 — Bounded printf input regression candidate

Browser regressions observe actual Bokeh formatter calls for ordinary and extreme finite candle
responses and exercise hostile paper-marker side text through the mocked candles API and native
hover interaction. They retain the existing bounded f/e precision grammar and literal hover values;
production code and dependency locks are unchanged. The transitive sprintf-js advisory remains
unpatched inventory risk. These fixtures cover the exercised local UI paths, not arbitrary inputs,
provider acceptance or a package fix. Focused checks, sensitivity failures, independent review and
the frozen-candidate full-gate result are recorded separately in ignored task evidence; this entry
does not claim aggregate acceptance. Supported GitHub Codex Code Review remains a parent-owned step.

### 2026-10-17 — Bounded semantic-payload test-layout candidate

From accepted main `c1fdba82a32c7aa01bedeb34306a26613e7f7bac`, isolate the two
semantic-payload tests (four cases) and share their three unchanged public
constructors and `PROJECT_ID`. The separate PR69 document is excluded. Baseline
and after-state collection match for 135 module cases and 5,839 public cases;
both module runs passed all 135 cases. ASTs, observed platform markers, actual
fixture bindings/scope groups/parameter indices, within-scope lifecycle order
and per-phase outcomes match under only the four approved node relocations.
Atlas updates must come from its documented producer and receive exact-diff
review. Frozen-candidate focused checks, independent review and a fresh canonical
full gate remain required before acceptance; publication and merge are held.
No product behavior, assertions, fixtures or research decision authority changed.

## 2026-10-18 Foundation status

This is the current navigation record for cleanup, refactor, cloud and documentation
foundations, scoped to accepted main `1d9920238ccaf0e231c90b06eba61f6ab75b7777`.
Historical entries above remain dated evidence, not current acceptance assertions.

- **Verified, bounded deliveries:** [PR68](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/68)
  delivered context stewardship/retrieval; [PR69](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/69)
  annotated an unavailable historical reference without recovering its contents;
  [PR70](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/70) delivered
  bounded sprintf fixture tests; [PR71](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/71)
  delivered semantic-payload test isolation; [PR72](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/72)
  delivered README workstation guidance. The
  [accepted pilot plan](superpowers/plans/2026-10-16-context-ownership-and-test-layout-pilot.md)
  retains historical collection parity for 135 module and 5,839 public cases,
  AST/fixture/lifecycle and outcome parity; these are retained receipts, not a new
  rerun here. [PR73](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/73)
  readiness and [PR74](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/74)
  evidence preservation are accepted, with all seven postmerge jobs passing in
  [39082708982](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39082708982)
  and [39088156452](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39088156452).
- **Pending cleanup:** reconcile the reported owner-side handover count of 144 paths
  against the [broader hygiene plan](superpowers/plans/2026-10-08-repository-hygiene.md).
  The item-level handover is unavailable to this inspection; this count is
  not a verified repository inventory. The
  [maintainability plan](superpowers/plans/2026-10-10-maintainability-cleanup.md)
  describes the completed bounded [PR58](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/58),
  rather than that outstanding handover.
  Preserve the original `454c940f` checkout, 126 status rows and 11 dirty Mac
  worktrees as owner-side preservation obligations. Their current state was not
  inspected here; no deletion, new parallel inventory or completed handover is claimed.
- **Pending refactor evidence:** accepted bounded deliveries do not close private
  or live-provider coverage, current mutation adequacy or cross-platform wheel
  acceptance. Match each future claim to scoped receipts. Canonical Linux wheel
  build/smoke passes apply only to their tested candidates. The upstream sprintf-js
  advisory remains open. No failing foundation check is reproduced in the current
  cited receipts; that is not a repository-wide defect census.
- **Verified cloud operation within dated scope; hardening pending:** the
  [setup plan](superpowers/plans/2026-10-15-cloud-setup.md) and
  [owned-process readiness plan](superpowers/plans/2026-10-15-cloud-readiness-owned-processes.md)
  retain setup/fresh-startup, writable cache, dependency, pinned-browser, CLI,
  static Chromium and backend receipts. No new fresh launch was performed here.
  A current configuration/version record does not establish unavailable per-launch
  configuration binding. The documented bounded 401 procedure is not a new executed
  recovery claim. The old pending-upload CONNECT 403 remains a separate unresolved
  reported platform support case; no service cause
  or fix is claimed.
- **Verified accepted plan annotations:** [PR75](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/75)
  reviewed head `f35f22dee2fa226f4041f3c70137ca6dc6e67b72`, tree
  `cb338a9f31de6ca582c87dd72822ddfe51169b03`, was normally merged at
  `1d9920238ccaf0e231c90b06eba61f6ab75b7777`. Its fresh local full passed all
  49 steps across six components, branch CI passed all seven jobs, and the
  [actual exact-head Codex review](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/75#issuecomment-6245365693)
  completed without findings or unresolved findings. Postmerge
  [CI39097174785](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39097174785)
  attempt 1 passed all seven jobs, completed 2026-10-18T04:53:19Z.
  The original candidate and first review findings remain preserved alongside
  the correction. At the prepublication freeze, this separate five-document
  prevention/status/navigation candidate was local and uncommitted, with publication
  held. It was published as a draft in [PR76](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/76)
  from initial commit `0b90467b80f802ccd26bdc532ee67d424e576b51`. Consult that PR for
  its live head and candidate-specific CI/review state; merge requires separate
  approval. Each corrected tree needs its own frozen-tree validation and independent
  evidence review; accepted PR75 results do not confer this candidate's acceptance.
- **Blocked evidence and next action:** the original chart trace is unavailable;
  later passes cannot establish its original cause. Keep that limit and other
  dated incidents in the [cleanup retrospective](operations/retrospectives/2026-10-17-cleanup-execution.md).
  Use the [evidence/recovery procedure](operations/development-loop.md#evidence-and-recovery)
  for future runs and retries; missing scoped evidence blocks the corresponding claim.
- **Explicitly deferred:** Future Software Team work, a full Qlib product build and
  wholesale restructuring require separately scoped plans and authorization.
  Passing the existing qlib gate component does not establish a full Qlib product build.

Shared acceptance requires an exact commit/tree, unchanged required checks, resolved
actual native review, explicit publication/merge authorization, postmerge CI and
preserved failure/recovery evidence. Engineering acceptance grants no research,
owner, risk, paper, broker or order authority; the existing decision authority and
all four Monte Carlo families remain unchanged.

Navigation rationale (primary sources inspected 2026-10-18): Van Clief and
McDermott's [ICM paper](https://arxiv.org/html/2603.16021v2) describes scoped
orientation, routing and task context. Its [core conventions](https://github.com/RinDig/icm-architect/blob/main/references/core.md)
separate reusable references from run artifacts and favor links to each fact's
owning home. The [system-map guidance](https://github.com/RinDig/icm-architect/blob/main/references/system-map.md)
keeps source authoritative and permits a minimal index. Our adaptation uses the
existing operating manual and [context index](context/README.md), this dated status,
the development-loop procedure and [generated Atlas](atlas/system-map.md).
Deeper routing requires an observed navigation failure; no new hierarchy or
framework is introduced. GitHub source URLs are mutable. The independent route
assessment is informed by prior repository knowledge; no cold-worker experiment
is claimed here.

## 2026-10-19 Mac handover update

The clean isolated `current-main` checkout was fast-forwarded to accepted main
after [PR77](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/77), at
`59b92919a3fb2efcbb2159063d2801c10693e47c` (tree
`c8fdb502cbd59d1ccbcee915073be1cae2d42128`), matching fetched `origin/main`.
Read-only GitHub verification confirmed [post-merge workflow run
39245184680](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39245184680)
completed successfully with all seven jobs passing.
This updates the checkout used for the bounded workstation check; it does not
change the original dirty checkout or resolve its preserved worktree inventory.

A fresh, bounded headless startup and UI smoke passed on that exact tree using an
empty synthetic data directory, isolated HOME, no provider credentials, and paper
and IBKR paper disabled. All twelve workspace package imports resolved inside the
current-main checkout, including `alpha_research.weekly_diagnostic` from
`packages/alpha-research/src`. The Overview page rendered with its main region visible;
all 17 observed HTTP responses were 200, expected startup requests were present,
and no browser console/runtime errors or external host requests were observed. The
normal startup read of `/api/providers` returned the local provider catalog only;
no provider check, acquisition, data pull, broker action, or live readiness check
was run. The browser and server stopped, and their ports were clear afterward.
The read-only local process check found no matching ALPHA/Workstation launch
labels or LaunchAgent filenames, no app/smoke processes, and no listener on the
checked ports; no launch configuration was changed.

The initial rerun failed because its sanitized PATH omitted the existing `alpha`
CLI executable. That attempt and its diagnostics were retained separately; the
successful rerun added the existing venv's `bin` directory without installing or
changing dependencies. The local receipts and screenshot are under the ignored
project state directory `.alpha/state/mac-handover-2026-10-19/`; the run manifest
is the entry point. The earlier Desktop evidence remains preserved at
`/Users/hunternovotny/Desktop/Project-ALPHA-reconciliation-evidence/current-main-browser-rendering-smoke-2026-10-18/`.

This smoke closes only the bounded startup/UI check. Physical handover remains
open: reconcile the saved path/branch/operation records and owner dispositions
before retiring any checkout or branch. No archive, branch, worktree, or unexplained
change was removed. The UI also reported the expansion SSD as blocked; this run
did not inspect physical storage, launch persistence, live providers, broker
connectivity, the full gate, or the Playwright suite. The 2026-10-18 foundation
record above remains the historical basis for items not changed by this update.


## 2026-10-21 — Atomic snapshot and receipt retry corrections

On the isolated branch based on `b2556c0ede016f99dba687187b6e9f501bedd5cb`, synthetic deterministic
controls reproduced mixed-generation snapshots accepted by their own hashes and identical-receipt
retry failures after automatic and explicit rollback. Snapshot copying now holds original peer
file descriptors per symbol and rejects intervening atomic replacements, including rollback that
restores identical bytes. Candidate and backup retries reuse only identical retained artifacts;
conflicts fail through the typed CLI boundary without replacing evidence.

The original 69 focused tests passed before changes. Added controls cover copy boundaries,
rollback during copying, exact-evidence preservation, conflicting candidate/backup/canonical state,
CLI exit 2 without traceback and future poison with a discriminating leaky read. Independent review
found and reproduced the rollback counterexample before the final descriptor-based correction.
The [audit plan](superpowers/plans/2026-10-21-atomic-snapshot-retry.md) records scope and limits.
Final full-gate and exact-tree independent-review outcomes are recorded in separate task receipts;
this entry does not assert those outcomes, private-suite coverage, provider qualification or release
acceptance. No prior missing-suite exemption applies. No commit or publication is part of this work.


The first corrected-tree aggregate attempt passed backend, frontend/browser, literature and Qlib
and passed Atlas tests, then stopped on stale generated Atlas graph/input/unknowns outputs.
Their canonical regeneration is part of this change; the failed attempt remains preserved and is
not aggregate acceptance. Final regenerated-tree results remain in the separate task receipts.

## 2026-10-22 — Technical-chart cursor inspection (unaccepted)

On clean supplied base `99f2d472dd4511b446e1198ae80201e7207d089d` (isolated branch `work`), the
existing Technical · Bokeh chart now supports exact candle/study inspection by hover, touch tap, and
focused Left/Right/Home/End/Escape keys. Selection uses the returned candle index and aligned backend
overlay value, preserves `—` for missing study points, publishes the existing UTC linked cursor, and
clears on chart recomposition so the header returns to the latest returned candle. Classic/Default
grammar and optional Market · Lightweight are preserved. No backend, API, dependency, or research
artifact changes. The deterministic E2E uses mocked synthetic bars and is not research evidence.

Focused evidence: renderer unit tests 3 passed; technical-chart Chromium reference spec 18 passed,
including keyboard/touch value identity, study-change stale clearing, loading/empty/503 states, and
both theme screenshots; TypeScript build check and warning-denying lint passed. The packaged SPA
build passed with existing Vite dependency-eval/chunk-size warnings. Visual captures and exact
candidate/recovery patch are in `/workspace/task-evidence/alpha-chart-inspection/`. Independent
read-only review approved the implementation and scoped evidence. This is not a full repository gate
or feature-release acceptance. No commit, publication, or merge was made.

## 2026-10-23 — Strict alpha-study feature schema versions

`FeatureInputRefV1` and `FeatureValueV1` now reject schema-version values that are not
integers equal to `1`, including JSON booleans and floating-point `1.0`. Public
regressions cover valid round trips with unchanged content hashes, both top-level
readers, nested input references, unsupported and missing versions, semantic tampering,
extra keys, and boolean feature scalars. Valid serialized output and hashes remain
unchanged. No schema migration, dependency, store, or authority change was introduced.
Private external coverage remains **UNVERIFIED**.

## 2026-10-23 — Boolean guard for frozen baseline numeric inputs

`alpha research diagnostic run-plan` previously accepted JSON booleans in numeric plan fields and
`schema_version`: `seed: true` became `1`, `target_vol: true` became `1.0`, and
`schema_version: true` became `1` before plan identity was calculated. Focused regressions reproduce
all three conversions. The existing `BaselineExecutionPlan` now rejects booleans in numeric fields
and `schema_version` while preserving Pydantic's existing numeric-string and integral-float
coercions; a compatibility test verifies equivalent inputs retain the same normalized plan hash.
This is a fail-closed input-contract change only: no metrics, experiment lineage, reservation,
semantic freeze, strategy behavior or authority changed. The focused module passed all 40 tests when
run through `scripts/run_owned_test.py`, and an independent review approved the bounded patch. The
canonical full gate was not run. No commit or publication was made.

## 2026-10-21 — Stooq interrupted-response error boundary candidate

An offline probe through the real Stooq adapter and `data pull` on accepted main
`b2556c0ede016f99dba687187b6e9f501bedd5cb` reproduced connection-reset and truncated-body
exceptions escaping with exit 1 and no diagnostic. Timeout and URL-error controls
already produced typed exit-2 errors. The narrow candidate translates connection
errors and incomplete HTTP reads to chained `DataError`, preserving the existing
HTTP-rejection message. It does not retry, parse partial bytes, fall back to another
provider or publish partial history. Public adapter/CLI regression tests cover the
interrupted reads, original cause, response cleanup and absence of publication.
Fresh focused/full validation and independent exact-diff review remain required;
this offline reproduction establishes neither live-provider acceptance nor release
acceptance. Original probe and failed test attempts remain in private task evidence.

A separate dated correction in the owner-actions register supersedes its preserved
August 19 branch-only harness advice: accepted main tracks the two named harness
files. Their presence does not establish hook installation, trust, permissions or
local readiness. The old inspection date and historical text remain unchanged.

## 2026-10-22 — Empty component gate definitions fail closed

On isolated candidate `codex/gate-empty-steps-fail-closed`, based on accepted main
`99f2d472dd4511b446e1198ae80201e7207d089d`, empty component definitions now return failure
and cannot validate a component receipt or produce a full stamp. The focused
`tests/unit/test_gate_components.py` run passed (34 tests); the two new regressions first
reproduced the fail-open behavior on the base. This is a bounded candidate result only:
the aggregate gate remains outstanding. An independent read-only review found no actionable
issues; the reviewer did not run tests. No commit or publication was performed.

## 2026-10-22 — Pinned Semgrep tooling candidate

On isolated branch `work` at baseline `99f2d472dd4511b446e1198ae80201e7207d089d` (clean before
edits), the gate and float-contract checker now share `scripts/semgrep_runner.py`. It requests exact
Semgrep 1.181.0 through isolated `uvx --from semgrep==1.181.0`, verifies `--version` before each
scan, and returns a failure on a missing tool, failed invocation, or mismatch. The existing rule
file and both callers' scan arguments are retained; application and worker lockfiles are unchanged.
Offline Semgrep-focused tests passed 12/12, including both callers, exact argv, version mismatch,
scanner failure and no stamp after a failed gate step on the initial implementation candidate. The
implementation remains local and uncommitted; subsequent candidate-specific checks are recorded in
the task handoff. This entry does not claim repository acceptance, publication or merge.

Cold-cache requalification later exposed that the gate adapter combined `uvx` stdout and stderr,
so first-install diagnostics polluted the exact version comparison and stopped before any scan. The
shared runner now checks only the probe's exact stdout, keeps bootstrap diagnostics separate,
propagates probe failures, and preserves both streams in failure logs. Both callers also emit stderr
from successful invocations so cold-cache bootstrap diagnostics remain visible. Added offline
regressions cover bootstrap stderr with the exact pin, wrong/empty/extra stdout, misleading version
text in diagnostics, failed bootstrap, both callers, scan arguments and full scan failures. The
failed cold-cache full-gate attempt is preserved in durable task evidence; it exposed the adapter
issue before any scan began. This entry makes no private-suite or release-qualification claim.

## 2026-10-24 — Local PR81–88 UI integration derivative

Disposable local derivative of the independently reviewed eight-PR candidate at
`76f85e673fe7e6d08a488a9da3dc6a85d0a7ddf6` (tree
`07d6416459764fd64f75e49cfba5cfea47ac346b`). It combines the separately reviewed investigation
selection-epoch, RunDetail trade-loading, Saved Workspaces load-ownership and ML Diagnostics
canonical-replay navigation fixes, their public browser regressions, the RunDetail manual note and
the ML navigation guide. The generated SPA was rebuilt once using Node.js 22.23.4 and the existing
locked frontend dependencies. Focused oxlint, TypeScript/Vite production build and all 17 real-panel
browser cases passed (11 on `chromium-minimum`; 6 selector cases on `chromium-reference-only` with
project dependencies disabled). The build reports the existing Bokeh direct-`eval` and large-chunk
warnings. No dependency or lockfile changed. Exact test output and source-candidate identities are
preserved in `/tmp/alpha-pr81-88-ui-integration-20261024.md` and its adjacent logs.

PR85 adds `membership_status` fields to ML response projections; compatibility with external strict
clients consuming those response schemas remains unverified and is not covered by this UI-focused
qualification.

This is local focused qualification only: the canonical full gate and private coverage are
outstanding. It does not authorize upstream integration, merge, publication or release acceptance.

## 2026-10-24 — RunDetail summary/catalogue request ownership correction

Separate local derivative of the PR81–88 UI integration tree
`3c3fcd4485e0a9c26cf471bd50caf8e0124c1d9a`. RunDetail now tags summary detail, request error and
figure catalogue values with their selected run ID and request epoch, and derives renderable values
only when both match the current route. The `RunDetail hides A summary and figures while B detail
and catalogue are pending` real-panel regression failed on the preserved pre-fix tree after
observing both A's summary and catalogue under B; it passes after the owner guard. Additional tests
cover a stale B detail error after A→B→A and delayed detail/catalogue completion after report
unmount. All 7 RunDetail tests pass; the combined 20-case focus passes (14 `chromium-minimum`, 6
`chromium-reference-only --no-deps`). Node.js 22.23.4 TypeScript/Vite build and targeted lint pass;
the existing Bokeh direct-`eval` and large-chunk warnings remain. No lockfile or dependency changed.

This remains focused local evidence, not canonical full-gate or private-coverage acceptance. The
external strict-client caveat for PR85 and the earlier unresolved process-reaping diagnosis remain.

**Bounded literature page reads (2026-10-24)** — `get_research_source` now optionally reads one
project-bound page and character slice from an already acquired extraction. The CLI reuses the
existing immutable extraction hash reader, verifies source/extraction binding and the selected
page hash, caps each result at 8,000 characters, enforces the extractor's 200-page ceiling, and
labels text `UNTRUSTED_SOURCE`. An over-limit extraction is marked truncated without retaining
partial text by the current worker, and page reads refuse any `truncated` artifact before returning
text. The legacy source preview also returns extraction status/warnings and can include bounded
page previews if present; it is not a full-paper review signal. The original source preview call
and all 62 MCP tool names remain compatible. The literature-review
protocol now requires metric/estimand definitions, units, sample and horizon, estimator and
uncertainty, assumptions, evidence/inference separation, reproducibility limits, and a falsifiable
extension linked to a registered analysis family; undefined metrics stay unknown. The change adds no
provider, full-text acquisition route, analysis family, model, or authority. Selected store,
protocol, CLI, and MCP regression checks passed; provider health was not tested. Neither source
preview nor page read screens claims or advances research status. Opening `ControlStore` retains
its existing schema/migration work and missing development-stage-row repair, which can write local
control data when needed; that lifecycle behavior was not changed by this reader. The scoped test
set passed 202 tests before the patch, 207 on its initial version, 6 targeted checks after the
page-type correction, and 209 on the qualified final patch. Ruff lint/format and mypy also passed
on the eight changed Python paths.

**Deferred SSRN scope** — no SSRN adapter or access route is configured by the page-reader change.
Keep any follow-up metadata-first: use Crossref/OpenAlex SSRN identifiers only where their actual
coverage and linkage are verified; preserve the exact SSRN id, DOI, working-paper status, known
version and retrieval provenance, and a content hash for any lawfully acquired text. A permanent
DOI is not proof that historical full text is immutable or retained. Default to explicit
metadata-only/access-unavailable states. Full-text intake requires a verified permitted route or
an owner-provided PDF, with source attribution and rights handled under SSRN's [preprint FAQ](https://www.elsevier.support/ssrn/news/welcome-to-ssrn-elseviers-preprint-server),
[DOI/version guidance](https://www.elsevier.support/ssrn/answer/doi), and [reuse guidance](https://www.elsevier.support/ssrn/answer/can-i-repurpose-content-available-on-ssrn).
Dataset/code relationship retrieval is a separate follow-up; linked code remains inert and must
never be executed as part of paper review. No SSRN API, host allowlist, automatic full-text fetch,
or corpus reuse permission is assumed here.

**Offline literature worker cache (2026-10-24)** — `_run_literature_worker` now passes only the
existing credential-free, offline child environment plus `UV_CACHE_DIR`. A valid configured cache
is preserved; otherwise the launch gets a temporary cache removed after the subprocess exits.
Invalid explicit cache paths fail before worker startup rather than silently switching caches.
Focused tests cover the configured and temporary paths, cleanup on success/failure, read-only home,
and environment isolation. A real synthetic owner-PDF CLI import and page read passed with no
inherited cache setting and a read-only home; no provider request or owner paper was used.

**Read-only qualification preflight (2026-10-25)** — Added `python3 scripts/gate.py preflight
[--json]` to identify known blockers before the full gate. It checks only allowlisted public
tracked prerequisites and Git alternates; reports branch, commit, Python/uv and CPU/memory/disk;
shares the existing manual-size predicate; reuses `gate.lint_harness` and the canonical Atlas
`--check`; and checks that the full-gate mypy command includes `tests` (`scope_only`) without
executing mypy (`not_run`). It does not install or repair anything, run test suites, or rewrite Atlas
outputs. The initial synthetic `unittest` module passed 8/8 and
`git diff --check` passed; the dated `FeaturePlan` validates. On branch
`codex/alpha-preflight-20261025` at baseline
`e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc`, initial preflight found all 173 required public paths
present, no Git alternates, the manual-size result at 5,965/6,000 bytes, Python 3.12 and uv
available, canonical harness lint passing, and full-gate mypy scope covering tests. It returned 1 because the local
`.venv` is missing and generated Atlas outputs are stale. The report showed 5 logical CPUs, about
17.0 GiB available RAM and 29.8 GiB free disk. Independent review found no remaining code findings.
At that point pytest was unavailable without creating an environment; the authorized follow-up
verification is recorded below.

**Qualification preflight follow-up (2026-10-25)** — On the same branch and baseline, the owner
authorized the repository's root-only `uv sync --locked`, canonical Atlas generation, focused tests,
canonical typing and cheap checks. Sync succeeded; `pyproject.toml` and `uv.lock` remained clean.
The canonical Atlas generator was run with the root candidate `.venv`; its `--check` confirmed all
8 generated outputs fresh. Final preflight JSON reports no blockers, all 173 allowlisted public
paths present, no alternates, manual size 5,965/6,000 bytes, local `.venv` and mypy present, and
Node/npm available. The mypy rows remain `scope_only` and `not_run`, respectively; separate executed
commands passed `uv run mypy packages apps tests` (857 source files) and the canonical harness mypy
command (18 files). Focused repository pytest passed 15 tests, including the synthetic preflight
suite and shared manual-size test. Changed-file Ruff check/format, import contracts (13 kept, 0
broken), harness lint, plan validation, Semgrep's pinned contract probe, and `git diff --check`
passed. Semgrep verified the existing 1.181.0 pin and detected all four synthetic leaky comparisons.
Independent review found no remaining findings. The initial blocked JSON and exit status remain preserved outside the worktree
at `/workspace/alpha-preflight-initial-blocked.json` and
`/workspace/alpha-preflight-initial-blocked.exit` (SHA-256: `465e75c44a0840bf8716a27dab640aae12d104d5db2a0f52fe3b46aab2d59b0d` and
`4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`). The first Semgrep probe
attempt was interrupted with exit 130; after the owner confirmed the existing pinned `uvx` package
workflow was authorized, it passed on retry. The first exit is preserved at
`/workspace/alpha-preflight-semgrep-exit-130.json`; the successful result is at
`/workspace/alpha-preflight-semgrep-contract-result.json`. No project dependency or lockfile
changed. At completion of that follow-up, no full gate or publication had been performed.

**Qualification preflight canonical gate attempt (2026-10-25)** — The owner subsequently authorized
one canonical full gate on the reviewed candidate. Its backend component completed 11 of 12 steps
successfully; the full public-test run reported 5,987 passed, 10 skipped, and one failure, with
93.12% coverage against the unchanged 93.0% floor. The failure was
`tests/unit/test_claude_harness_gate.py::TestDoctor::test_doctor_passes_on_wired_repo`: the
synthetic wired-repository fixture kept a hardcoded harness script list and omitted newly registered
`scripts/gate_preflight.py`. This exposed fixture drift without changing gate scope, thresholds, or
production behavior. The backend receipt records `stable_tree: true`, failed step `pytest +
coverage`, and original candidate fingerprint
`73c350a90902b139fba989885208dc53012e51ab6d7dccf8dd47ab5a302c138d`. The preserved run log is
`/workspace/alpha-preflight-full-gate.log` (SHA-256
`092086bfdb5f1d9f1afdfed40ae3ef89123212e9a83c7bc2fe3fcc1e6d001770`); the backend receipt is
`/workspace/alpha-preflight-backend-failed-receipt.json` (SHA-256
`d7e668811d88330c9a6696a3eb8af02494d23ecab1ec0e7b1296ecc87e1344f5`). No full-gate stamp was
written. The minimal correction updates the synthetic fixture to iterate canonical
`gate.HARNESS_SCRIPTS`; independent read-only review found it keeps the fixture aligned with
`gate.doctor()`. The corrected candidate's outcome is determined by its exact-tree checks and
canonical gate receipt; this first attempt does not claim aggregate acceptance or publication.

**Mutation-selection and freshness preflight follow-up (2026-10-26)** — Implemented in a separate
worktree on branch `codex/alpha-preflight-selection-20261026`, based on the preserved qualified
candidate tree `70e478836058e8da0f9b10e153e576029ce038f4`. The preflight now reports the canonical
effective mutation base and resolution, exact-diff versus conservative-fallback selection and
target count. Exact selection of every quant module is distinguished from fallback. Frontend API
and SPA index alignment is checked only for the canonical freshness pathspecs; an actionable
`index_setup` warning is explicitly separate from actual Atlas `generated_drift`. Synthetic tests
cover explicit/default valid refs, missing/invalid/empty refs, exact and fallback target parity,
unknown resolution, staged/unstaged outputs, sparse skip-worktree omissions, a missing canonical
freshness step, and actual Atlas drift. Independent review found those two frontend-scope gaps; the
diagnostic now requires both canonical freshness steps and verifies their tracked targets are
present. Canonical backend selection logic remains authoritative through a shared target helper.

The focused repository test run passed 25 tests with two sparse-target subtests; canonical
`uv run --locked mypy packages apps
tests` passed for 857 source files. Changed-file Ruff check/format, import contracts (13 kept, 0
broken), harness lint, plan validation, canonical Atlas generation and `--check`, and
`git diff --check` passed. The new worktree's existing locked root environment was created using
`uv sync --locked`; the dependency and lock files did not change. Final read-only preflight JSON
returned exit 0 with 173 required public paths present, no Git alternates, manual-size 5,965/6,000,
candidate-local `.venv` and mypy present, and Atlas outputs fresh. It reported the available default
`origin/main` ref, merge base `bf5baa75c8db0de8e85623c218fd89b1d4f5f668`, and an exact selection of
zero quant targets. Frontend freshness paths matched the index. The preflight's own mypy entries
remain correctly labeled `scope_only` and `not_run`; the passing mypy result above came from a
separate command. No full gate, publication, merge, or deployment was performed for this follow-up.
## 2026-10-26 — Synthetic native lifecycle candidate (local, inactive)

Adds protected typed native lifecycle events and atomic failure/cancellation closure using existing
ControlStore records. A detached trusted owner runs fixed synthetic payloads in a disposable fixture
workspace on the explicit linux-posix-v1 profile. Reconnect never dispatches or signals saved PIDs.
Unknown owner/cleanup remains nonterminal with capacity occupied and the reservation fully charged.
Clean return code zero records process completion pending scientific admission, not a completed D1
attempt. Ordinary D0 and deterministic deep execution remain on their existing paths.

No new schema/table, migration, dependencies, production dispatcher or native/provider/LLM calls.
Local public-only focused qualification is separate from full-gate and real-native acceptance.
Activation still requires executable qualification, physical worker isolation, stronger containment
where claimed, external effect limits, scientific output admission and compatible-writer cutover.
See `docs/superpowers/plans/2026-10-26-synthetic-native-lifecycle.md` for the bounded implementation.

### 2026-10-26 — Adversarial synthetic lifecycle continuation (local)

The isolated continuation freezes completion observations and shares a single retained-child cleanup
result between the lease and owner. No-spawn completion prevents later dispatch; launch preparation
rechecks expiry before Popen. Known synthetic escapes remain quarantined with capacity and the full
reservation held, even after their original process group has exited. No schema or admission changes.

Public fault cases cover both cancellation/completion transaction orders and duplicate calls, owner
SIGKILL after closure writes before commit, stopped-owner expiry, interrupted/provenance-lost cleanup,
and blocked journal publication. Journal stalls can delay process termination: this slice supplies no
hard wall-time bound or security sandbox. Native activation and aggregate qualification remain separate.
Running lease failures deterministically record `owner_error`; owner return never means scientific
success. Startup and outcome-publication errors still propagate.

### 2026-10-26 — Journal-independent synthetic cleanup candidate

The fixture owner arms its existing lease thread at retained Popen before post-spawn verification
or journal publication. Safety callbacks use only local monotonic time, a bounded nonblocking
cancel-only Unix datagram socket and shared one-attempt process-group cleanup. SQLite heartbeat
and outcome reporting stay on the owner thread. Native cancellation sends the live stop request
before database access; the owner atomically records received intent with its observation using
existing job events. Socket delivery never proves cleanup or releases capacity/budget.

Delayed immutable start observations can be retried after physical cleanup, never by re-dispatching.
A reaped leader cannot authorize signalling a surviving numeric group; uncertainty remains charged.
Blocked or failed reporting retains the slot until verified cleanup is durably recorded. Journal
append times can lag execution. Ordinary OS scheduling, owner death, denied cleanup and escaped
processes still limit enforcement; no hard real-time or hostile-code containment claim is made.
No new dependency, schema, application dispatch route, security setting or native workflow is added.

The first comprehensive independent audit blocked a passing candidate on concurrent leader reaping
before group signalling. Native-only observation now uses Linux waitid(WNOWAIT) under the shared
cleanup lock, retaining the child identity until after the final possible signal. Loss of wait
ownership or a group still visible after reap stays uncertain with no further destructive signal.
Default durable-lease callers preserve their previous polling/cleanup path. Red race receipts and
the blocked candidate remain preserved alongside the corrected public regression evidence.

Follow-up red cases showed that retaining an exited leader through blocked start/heartbeat reporting
could mislabel successful execution as timeout. The safety loop now cleans observed normal exits
without reporting work. The dedicated entry establishes default SIGCHLD before claims/spawn;
the host profile rejects other dispositions. Trusted in-process tests require no auto-reaping flags,
outside reaper or concurrent signal-disposition mutation. These are explicit process ownership
assumptions, not a hostile same-UID sandbox guarantee.

### 2026-10-26 — Pinned native loop conformance development candidate

Added an isolated `workers/rdagent` dependency lock and a fixed synthetic extension of the real
upstream LoopBase/LoopMeta at `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`. The complete supplied
source tree is verified before importing. The extension inherits native scheduling and signed
checkpoint serialization, uses actual Scenario/Experiment/Hypothesis/Trace types and preserves
explicit synthetic feedback labels and metric units/values. Stock RDLoop and provider backends
are excluded. Root dependencies and locks are unchanged.

Explicit public tests cover native stages, roundtrip/resume, concurrent and stale continuation
rejection, cancellation/quiescence, tampered source/checkpoints, and fixture pre-effect allowance.
Native step_n is post-effect and is explicitly not admission authority. Cancellation demonstrates
the upstream in-memory cursor advance without a successful checkpoint. The live fixture owner
drains native tasks before allowing another continuation; cancelled owners cannot resume.

These are development conformance results, not ALPHA ControlStore accounting integration,
scientific evidence or production release qualification. The previous process lifecycle candidate
is unchanged. No public dispatch route, cross-owner recovery, native activation or full-gate claim
is added. Fresh independent review of the exact final candidate is required before acceptance.

Independent review blocked the first native-loop candidate on an import-provenance gap: placing
the external source root first on sys.path could shadow the reviewed probe or dependency modules,
and the bootstrap verifier could use an existing worker bytecode cache. Eight fixed sentinel
regressions reproduced these failures. The correction removes general source-root import access,
binds upstream and worker imports to their intended directories/files, rejects source-root shadows,
and establishes a fresh fixture cache before local imports. All successful continuation probes now
require real upstream and worker source hashes. The blocked candidate and red receipts are retained;
the corrected descendant requires a fresh review against its own exact tree.

**2026-10-26 bounded W04 native admission candidate:** Connected one fixed pinned native
LoopBase/LoopMeta synthetic child to the existing approved D1 ControlStore reservation and
trusted process owner. The claim checks actual approved worker/code/lock/environment/evaluator
fingerprints, one reserved variant and positive CPU allocation; the existing ephemeral stage
guard consumes the reserved loop allowance before each operator. Signed checkpoints bind the
job, reservation, invocation and same live owner. The existing lease supervises the actual child;
exact labels and metric names/values/units are checked only after actual process-group cleanup.
All successful labels remain pending scientific admission / not_admitted. Failure/cancellation
reconciles through the existing records, and cleanup/result/journal uncertainty retains capacity
and the full charge. No lifecycle event fields or schemas changed. Study mandates and the closed
scientific operator registry remain unchanged; generic study/trial admission, complete CPU/token
metering, scientific artifact admission, cross-owner recovery and production activation remain
unqualified. Four guard mutants and separate launch-object/zero-CPU red-green checks discriminate
missing enforcement. The explicit public regression selection passed 400 tests; scoped Ruff/mypy,
FeaturePlan validation and all 13 import contracts passed. A controller-death fixture teardown
race was fixed by awaiting owner lock release before deleting its scratch directory. Earlier
failure receipts are preserved. This is an uncommitted local candidate, with fresh independent
review pending and no full gate or scientific run. See the bounded W04 admission plan and the
local `/workspace/alpha-native-w04-admission-receipts` evidence directory.

## 2026-10-26 — Frozen-rule native study prerequisite, integration blocked

Added an internal immutable request for a fixed daily synthetic `close>10` RuleSpec and a new
always-flat `close<0` position control. Canonical rules, actual five-bar bytes, dataset/artifact
identity, UTC cutoff, horizon and units are frozen. Public engineering tests call the existing
rule_signal and compare with independent hand-specified positions; no statistical estimator or
market evidence is added. NativeLaunch refuses study-bearing requests before source measurement,
claim or child effects, including with an existing approved synthetic double-bottom reservation.
D0/D1 authority still admits the double-bottom protocol; no rules/control registration is
invented. The isolated worker lacks the qualified ALPHA rule dependency closure. Consequently
scientific native execution, study/trial outcome accounting, metrics/provenance admission and
W08 completion remain blocked/incomplete. See
`docs/superpowers/plans/2026-10-26-native-rule-study-boundary.md` for the acceptance map.

## 2026-10-26 — Closed synthetic native rule workflow candidate

The earlier rule prerequisite refusal is superseded only for two exact synthetic engineering
protocol versions with persisted real local owner confirmation and immutable approved contracts.
The actual pinned LoopBase/LoopMeta child now executes real rule_signal and, for the separate
costed dataset, the canonical Nautilus engine before Feedback. Same-live checkpoint continuation,
one-family trial limits, existing full reservation accounting and protected immutable completion
are exercised. Independent cash/fill arithmetic matches12558.21 baseline versus12000 flat control;
scientific_acceptance remains not_admitted. Two canonical result projections reuse existing
snapshot/sidecar/chart/comparison APIs and share one trial. Self-rehashed altered equity is rejected.
Fresh worker profiles bind complete local source, preserved metadata and installed dependency bytes;
only the declared import subset is qualified. Root/old worker locks and environments are unchanged.

The broad explicit public selection passed 612 tests with no skips; the subsequently strengthened
projection/authority suite passed 27. Application/test typing passed 15 files plus the strengthened
test, worker typing passed 6 files against actual upstream annotations, and all 13 import contracts
passed. Scoped Ruff/format and canonical Atlas freshness are recorded in the executor receipts.
Existing context maps now link a lean validation dependency backlog while retaining full Qlib,
native RD-Agent and wider W01–W19 scope. Final candidate review remains pending. This is an uncommitted candidate,
not full-gate/release approval. Four other-owner transfers failed to materialize; their patches and
compatibility remain blocked. Real discovery, empirical W08 and full report/UI acceptance remain
unqualified. See [current plan](superpowers/plans/2026-10-26-native-rule-authority.md) for exact
authority, source paths, receipt map, blockers, rollback and resume.


## 2026-10-26 — Native workflow assembly onto current integration (pending qualification)

Preserved original tree d67a13e88ced67e234dd0183ad7fd01ed8c53e74 and its receipts. Applied its full
e635 delta once in an isolated bc5b58351cc334d36112167c9463a80184411cc6 checkout. Source merged
without conflicts; retained both build histories and regenerated Atlas. Moved detailed native
invariants from the operating manual to the existing current plan to preserve the canonical
manual-size guard. Fresh scoped verification and independent review are pending. No handoff,
private-suite, rendered UI, scientific or production acceptance is inherited. No commits/publication.


### Native assembly independent review corrections (2026-10-26)

The fresh comprehensive source review reproduced two high defects: self-rehashed projection
semantic fields were accepted, and a raw-result/artifact rewrite passed completed-case reads
without changing the database. Preserved failed probes and initial BLOCK report live in the
assembly executor packet. The correction derives exact projection identities/semantic fields,
binds the supervisor's same bounded-read receipt bytes in the existing trusted outcome, publishes
those captured bytes, and pins their full reference in immutable attempt details. No SQL schema,
ledger, _run_deep or production recovery change. Original process-only payloads retain V1 shape;
new closed rule outcomes have an additive versioned rule_result binding. Historical unbound rule
completion fails closed; mixed-reader/writer activation remains blocked.

Focused corrected authority/artifact/public-read checks passed27; final lifecycle/adversarial/journal
checks passed81. Test portability now requires explicit source/profile opt-in, configured broken
runtimes fail, and receipt copies are opt-in. Harness cleanup no longer signals saved/reaped groups;
intentional orphans use retained verified Linux pidfds, ordinary teardown requests live-owner stop.
The initial broad assembly run612passed and47preflight tests predate these corrections. Fresh final
broad regression and exact-tree independent re-review remain pending in the acceptance packet.
The root runtime was recreated offline from unchanged locks; canonical preflight then passed.
No full gate/private-suite/scientific/UI-release qualification, publication or activation is claimed.

Clarification from final independent probes: the general research_case_summary reader returns
metadata and revalidates D0 only; its unchanged response after a D1 artifact rewrite was not proof
of accepting numerical D1 evidence. Verified completion and verified_research_attempt are the new
full receipt-binding boundary. Standalone artifact consistency checks and generic UI/report readers
confer no ControlStore authority. Both repaired v1/v2 baseline/restore reads and semantic/raw tamper
rejections were independently observed at the intended verified boundary.

Final assembly review also demonstrated a mutable nested observation alias despite a read-only
outer mapping. The closed rule-result binding is now detached and frozen at issuance, and journal
serialization owns a separate plain copy. Both alias-mutation red cases and the real rule workflow
passed focused correction tests. Final public regression, independent review and the actual
canonical working-tree fingerprint are recorded in the existing assembly acceptance packet;
earlier SHA256-of-index-tree calculations are not substitutes for gate.compute_tree_hash.
The preserved original candidates, source-transfer holds and missing-private-suite obligation remain.

### Native assembly: recovered terminal public receipts

The interrupted session's saved commands completed on source tree
`d9fc9658686eb3247f284d7a0a65943dc88e6c11`:616 public tests passed with no skips,47
integration-preflight tests plus two subtests passed, strict typing passed for27 root/test and9
worker files, lint/format passed for36 changed Python files,13 import contracts held, and canonical
cheap preflight/plan/profile checks passed. Receipts54–63 are preserved in the existing assembly
packet. The final source-review verdict had not completed at interruption and is being completed
independently; consult that packet rather than infer acceptance from these checks. The ensuing
status-only documentation refresh receives fresh Atlas/preflight checks and an explicitly distinct
final identity. No full gate/private-suite/UI/empirical acceptance or publication is claimed.

Final review AR-006 reproduced synthetic snapshot source/date relabeling through consistent
artifact rehashing. The closed native projection now compares against a fresh canonical expected
snapshot from the fixed synthetic study, including full provenance and declared symbol/action
identity. Existing altered evidence is rejected without repair. Fourteen public lineage cases
failed before correction; focused and final exact-tree results are retained in the assembly packet.
This is an additional repair after d9fc/ef811; their earlier passes do not qualify the new code.

### Native full-gate followthrough candidate

The reviewed46e4f02 synthetic checkpoint remains physically preserved. A separate bc5-based
qualification worktree starts from that exact tree. The first complete backend pytest/coverage
step passed6210 tests but failed one monitor-fault test and produced22 archive teardown errors;
coverage93.04% exceeded the93% floor. The archive failures used an opt-in receipt directory before
its parent existed; the next invocation explicitly prepares that output path. The monitor test
injected its safety-loop fault before payload readiness, allowing cleanup to win that race. Its
repair arms the injected fault only after observed readiness, retaining the existing cleanup
deadline and assertions. No production behavior, admission/accounting or migration code changes.

The owner clarified that ordinary unchanged-lock project dependency setup is authorized; earlier
no-full-gate/runtime restrictions are historical to their recorded scope. The existing canonical
full gate is now the requested qualification action. Its actual terminal outcome and any remaining
source/runtime failures are preserved in the executor's engineering-gate-followthrough packet.
No private-suite, real-data/scientific, rendered native-UI or deployment acceptance follows from
engineering checks. No Library-transfer workaround or Qlib adapter change is included.



## 2026-10-26 Qlib tabular first-wave local candidate

Implemented in isolated `Project-ALPHA-handover/qlib-tabular-wave1-20261026`, branch
`codex/qlib-tabular-wave1-20261026`, from delivery baseline
`bc5b58351cc334d36112167c9463a80184411cc6`. The dirty primary checkout was not edited.
[Plan, recipe ledger and evidence route](superpowers/plans/2026-10-26-qlib-tabular-wave1.md)
are linked from the existing context index and Quant Platform model row; Atlas is regenerated.
The initially missing expanded scope authority was subsequently supplied as parent-verified
Library v1 section9/page9 planning text; the complete document was not materialized locally.
The upstream inventory denominator54355232463878d2eebb91fe0ee5fa7fa1f5976c remains distinct
from the unchanged Qlib0.9.7 worker pin and da920b7 runtime reference.

Additive schema3 selects LightGBM, Linear OLS/ridge/lasso/NNLS, CatBoost, XGBoost and upstream
DoubleEnsemble. Legacy1/2 remain covered. Available backends really fit synthetic folds;
CatBoost/XGBoost execution remains blocked by missing/unapproved optional dependencies.
The existing CLI and ML UI carry selection, dependency status, fold-local lineage and explicit
degenerate-score diagnostics. Comparisons bind identical frozen inputs, source/version lineage
and stable artifact bytes. Economics remain canonical-engine-only for new schema3 diagnostics.
There is no new control-store schema, RD-Agent protocol, admission authority or alternate backtester.

Focused evidence:269 root ML regression tests;48 isolated worker tests;420 frontend unit tests;
24 focused canonical ML browser cases. Six real worker processes each emitted2420 finite aligned
synthetic predictions with native reload parity and measured peak RSS609402880–655228928bytes.
One synthetic ridge exchange replayed through the existing canonical engine for121periods with
explicit1bps fee/2bps slippage and promotion_eligible=false. Independent Astra review reproduced
and verified fixes for comparison source replacement, hidden Lasso nonconvergence and misleading
degenerate-score quantiles; source-drift and native thread bounds were also addressed.

These results are bounded implementation evidence. See the plan and local `.alpha/state/qlib-tabular-wave1/`
receipts for the final candidate tree, complete changed paths, gate attempts and exact failures.
Full aggregate acceptance, Linux screenshot qualification, optional backend runtime qualification,
authentic private-suite coverage, real-data/discovery approval, empirical economics and promotion
remain separate. No commit, push, PR, merge, deployment or owner-data acquisition is claimed.


**Same-task qualification follow-up:** The exact73daaeae local candidate passed all six canonical
components and Astra's scoped review; receipts/source are preserved in its checkpoint directory.
Read-only current-package inspection identified bounded compatible CatBoost1.2.10 and
XGBoost3.4.1 CPU routes. The existing tabular plan now records all eight ADR-0011 proposal items
before additive isolated-worker adoption. No existing Qlib/NumPy/root pin may change. Optional
execution remains unverified until actual lifecycle tests; further edits invalidate the first
stamp for the new tree and require fresh independent review/full verification.


**Bounded optional runtime implementation completed locally:** CatBoost1.2.10 and XGBoost3.4.1
now execute on macOS ARM in the isolated worker. The217-package lock preserves all212 prior
versions and every211 non-project package record, adds no GPU runtime dependencies and persists
wheel-only guards. Final corrected source2070a9e4a11fc627b793456774e73b768c6240ec3a2ac220438abf7983492c64
passes68 worker tests; root ML269, frontend431 and focused browsers27 pass. Eight actual recipes
each publish2420 finite aligned predictions, validate through existing web contracts and compare
with immutable retry. New canonical Cat/XGB synthetic replays use explicit costs and remain
non-promotable. Astra verified selected-tree early-stop state and original/reloaded inference
thread bounds after reproduced failures; all prior trials/checkpoints remain preserved. ML list
labels now state prepared/prediction-pending/recorded evidence without inferring validation.
The plan's final-verification-summary link records exact final tree/review/aggregate outcome;
pending or absent receipts confer no pass. Linux/Windows transport, authentic private coverage,
empirical/data approval and promotion remain separate; no new local dependency authorization
is needed for these verified pins. No GitHub publication or accepted-stack upgrade occurred.


## 2026-10-26 — Qlib W11 successor engineering packet (in progress)

The five-backend/eight-recipe wave remains sealed at tree
`8df4b89561feee778cbf13909d28ca019b40bf20`, with its49-step/six-component full gate and
Astra review preserved in its original worktree. The isolated successor
`Project-ALPHA-handover/qlib-w11-refit-20261026` materializes that exact tree before edits;
its baseline commit remains `bc5b58351cc334d36112167c9463a80184411cc6`. Predecessor acceptance
is not inherited. See the [W11 packet plan](superpowers/plans/2026-10-26-qlib-w11-refit.md)
for supplied planning authority, scope, frozen engineering controls and next action.

Read-only inspection confirms real train-only normalization and fresh model fits already exist.
The genuine delta is observed component input/state provenance and a private fixture-only
single-world refit route, initially for ridge and DoubleEnsemble. Application planning/audit/status
must remain read-only. The integrated native registry has no W11 executor or W06 generic fit
reservation/ancestry contract; the reviewed six-module statistical source is unavailable. Neither
is reconstructed or replaced. Governed execution, statistical qualification and promotion remain
blocked. A transient Mac disconnect occurred before new fits; actual successor state was checked
after reconnection, with no uncertain source mutation found. New implementation/tests/review and
a fresh full gate are pending; this is an implementation checkpoint, not a passing receipt.

Subsequent source recovery: the approved native/W06 Library archive was materialized and verified
at516,864bytes/SHA256 `dd4d1c35e703bb9cc22bd2e76a79260b911a83e457f4d7901417d35ac7eb8525`.
Its actual patch reproduced producer tree `f15c906378fec2d4581564ecdf6cc610005c1ac8` on the common
base. W11 partial tree `b93f4d091fefa3a86aa580849ac4458360970a46` was frozen before reconciliation
in isolated `Project-ALPHA-handover/qlib-w11-native-20261026`. Both originals remain read-only.
This closes source availability only: Qlib protocol registration, fit-unit charging, world/reuse
ancestry and runtime/exposure qualification remain blocked. No real ControlStore was opened.
Pure call-graph and fixture eligibility tests have executed; actual W11 model fits, final review
and the assembled-tree canonical gate are still pending at this checkpoint.

The qualified predecessor was separately saved as Library `libfile_9c1b50c894dc819198579d0db90b503e`
v0,1,579,619bytes/SHA256 `6bb178052083a489564670042de412bdb8408c7cac75c23e4de0b654bf80b7c8`.
Its exact patch reproduces tree `8df4b89561feee778cbf13909d28ca019b40bf20`; its sanitized handoff
omits the panel and contains no W11 changes. Linux execution and authentic private coverage remain
unqualified. Packaging, source application and upload receipts are under the active successor's
`.alpha/state/qlib-w11-refit/`; no checkpoint acceptance transfers to this assembly.

Bounded W11 engineering execution subsequently completed:67 pure worker and62 CLI checks;
14 actual ridge/DoubleEnsemble worlds,2 expected cancellations,45 native fits and30 normalizer
fits;12 non-common mechanical oracles and both canonical economic controls passed. Source-bound
programme receipts and explicit remaining authority/statistical limits are linked from the dated
plan. Peak RSS was838,926,336bytes. The assembled-tree full gate and final independent review
remain separate required receipts; this entry does not grant scientific acceptance or promotion.


## 2026-10-26 W05 integration successor (local; qualification pending)

Preserved W11/native/tabular tree `a284def9502c20884ecf9740867db0810dc9ec83` remains unchanged.
This successor reconciles actual PR92 source (`fc6da893` → reviewed `f0ba4c34` → merge `98190e3b`
with `e635e6cb`) and the single reviewed W05 combined patch (`220b9b02`). PR92 production/test
bytes match the reviewed transport source; its generated maps are regenerated for the successor.
The W05 timezone fix is included once. See the [integration plan](superpowers/plans/2026-10-26-w05-research-integration.md)
for code, current checks, source identities, recovery and deferred final gate.

Imported producer behavior notes below describe the reviewed source; their historical tests do not
constitute verification of this successor.


**Tiingo transport-error redaction (2026-10-24)** — `TiingoAdapter.fetch` converts URL, timeout,
incomplete-read, and OS transport failures into type-only `DataError` messages and suppresses their
exception context for both bounded and unbounded reads. HTTP status errors, response-size limits,
parsing, and adapter result contracts are unchanged. Synthetic offline tests cover both read paths,
oversized responses, normal responses, and response cleanup.


**W05 bounded daily reference qualification (2026-10-26)** — A synthetic receipt-backed
Tiingo-format path exercises normalization, immutable snapshots, reopened typed queries,
partial-response quarantine, revisions, future-append invariance, raw/split-adjusted values,
and integrity rejection. Named IANA-zone cutoffs exposed a Polars timezone mismatch; PIT
comparison now normalizes the same instant to UTC, with spring/fall DST boundary regressions.
This is engineering reference evidence only. No suitable existing provider snapshot was
identified in the inspected public tracked paths. Historical source availability and revision
vintages remain unverified: daily session labels and retrieval times do not prove publication
times. A frozen rule/instrument/window and admissible raw receipt/snapshot remain W05 prerequisites.

**W05 opt-in acquisition budgets (2026-10-26)** — The existing Binance spot daily REST acquisition
accepts paired request/body-byte caps. One invocation shares its budget across pages and transport
attempts, including failed attempts and enabled 429 retries. Strict mode refuses redirects before
following them and aborts after interrupted reads. Defaults for other callers remain unchanged.
Synthetic transport tests exercise the real urllib handler chain; no market capture occurred.
Budgets constrain application HTTP attempts and body reads, not socket/TLS traffic, hidden buffering,
or separate invocations. A short terminal page is not proof of complete requested-window coverage.

Current integration status: local source and test review found no blocking defects; consolidated
public regression passed 358 tests. Final exact-tree check/review receipts are linked from the plan.
No full-gate stamp transfers. Native portability and full combined-tree gate remain blocked;
query/report/navigation source handoffs remain unavailable. Existing `data candles --manifest-id`
and member-level snapshot contracts are the current query seams, not the unpublished query/restore
work. No real acquisition, accepted discovery interval, scientific qualification or publication.


## 2026-10-26 combined Mac portability qualification

Preserved W05 successor `b0b9c8ea` and earlier W11/tabular checkpoints remain unchanged.
Verified native incremental archive `libfile_229009c0e56481918322aacbfcc0881b` reproduces
`f15c9063` → `35e762d5` exactly; actual consumer native production/test base hashes match.
The following producer notes describe imported source, not a Mac aggregate result.


**Native source portability follow-through (2026-10-26; qualification pending).** Explicit Linux
guards type the retained-child observer and Linux-only fixture probes for Darwin development.
Native modules avoid unconditional Windows `fcntl` imports; unsupported hosts and unavailable
observation capabilities reject before startup effects. Synthetic regression tests cover import
and no-effect rejection. Retained PID ownership, cancellation, uncertainty and charged-capacity
semantics are preserved. Windows-wide typing/runtime and non-Linux native execution remain
unsupported. Focused receipts, independent review and the final exact-tree gate determine
qualification; the previous candidate's receipts remain historical evidence.

**Native platform test requirements (2026-10-26; aggregate qualification pending).** Real Linux
owner fixtures now declare their platform before setup. Portable rejection/accounting tests retain
generic synthetic stores and verify job existence, no native events and no payload. A discriminating
failed-start test preserves an injected startup exception and verifies retained-process reaping
when the escape barrier directory is absent. POSIX lease coverage, LoopBase conformance and the
coverage policy are unchanged; actual macOS aggregate coverage remains unqualified.

Actual Mac qualification is in progress in the isolated successor. The [combined plan](superpowers/plans/2026-10-26-mac-portability-qualification.md)
links source reconciliation, preserved original failures, actual checks and final review.
Linux producer 49-stage/93.05% evidence and Darwin-target typing are not a Mac gate stamp.
Existing schema-v7 writable-open migration remains; synthetic stores only. Source reversal is
not database rollback. No scientific/private-suite acceptance or native Mac activation follows.


### Combined Mac portability follow-up (2026-10-26)

Verified native incremental f15c9063 → 35e762d5 was reconciled into an isolated
successor of b0b9c8ea. Actual Mac typing passed 883 files; the first aggregate attempt
failed with two missing-worker capability routes and 91.60% coverage against 93%.
A bounded readiness fix and portable approval-integrity verification follow; aggregate
acceptance is not granted by the producer Linux result or targeted checks. Exact final
receipts and next action are linked by the [Mac qualification plan](superpowers/plans/2026-10-26-mac-portability-qualification.md).


### Portable-evidence successor (2026-10-26, in progress)

The isolated 24f checkpoint completed 48/49 canonical commands; only 93% backend coverage failed
(6,298 tests passed, 149 skipped, 2 subtests; 91.6468%). Parent directed a meaningful portable-test
successor after a 363-module/210-function public coverage audit. It targets charged SQL readers,
closure atomicity, independent fixed costed-result validation and immutable artifacts/projections;
it does not emulate Linux or claim that the 761-statement gap is all kernel-dependent. See the
[existing qualification plan](superpowers/plans/2026-10-26-mac-portability-qualification.md) and
`.alpha/state/portable-evidence/`. No inherited aggregate acceptance.

Portable reader/accounting, D0 artifact and numerical/projection checks now include
nonzero-charge preservation, rollback, rehashed corruption and typed malformed-value
rejection. Narrow economics-validator repairs preserve canonical costs/returns and authority.
The exact successor identity, check receipts and residual statement inventory are recorded by
the qualification plan above; aggregate qualification depends on its actual final receipt.
No new platform skips or coverage-policy changes are part of this successor.

The first portable checkpoint passed 6,403 tests and failed the unchanged 93% coverage
floor at 92.0014%. A bounded reservation-admission follow-up addresses stale/malformed
bindings and charged replay identity. Final exact-tree evidence is linked by the same
qualification plan; intermediate coverage is not aggregate acceptance.

## 2026-10-27 Linux cloud qualification stabilization (not accepted)

Behavior changes on the integrated candidate: web ML experiment generation keeps the experiment's
frozen recipe unless a model is explicitly chosen (no silent schema-3 override); the synthetic native
owner child inherits its validated workspace `TMPDIR`; RD-Agent probe results report the source pin as
`expected`/`verified`/`not_verified` instead of constant commit and archive fields. Test-only repairs
establish the suspended-owner precondition and pin the lock-held fail-closed case.
Gate run 2 on the intermediate tree passed every backend step except coverage (6,563 passed, 0 failed,
55 skipped, 92.85% against 93%). Native suites passed 111/111 with a derived root of the pinned
`rdagent/` source; archive bytes were not verified. Five unchanged Linux visual baselines fail in the
cloud container; protected tests were absent and not executed. Details and open findings are in the
[native rule plan](superpowers/plans/2026-10-26-native-rule-authority.md#cloud-qualification-stabilization-2026-10-27)
and the [tabular plan](superpowers/plans/2026-10-26-qlib-tabular-wave1.md#cloud-qualification-stabilization-2026-10-27).

Review-scope alignment (same stabilization): review attestation now requires `files_reviewed` to
cover the Git guard's full review scope (risk-tier, protected control plane, hooks and guarded
config), and `/review-gate` uses that scope; see the
[gate preflight plan](superpowers/plans/2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27).
Gate run 4 passed every component on tree `844612d4`; this change creates a new candidate.

## 2026-10-27 Linux cloud qualification checkpoint published (not accepted)

Published checkpoint: branch `claude/cloud-qualification-c95f9d4d-20261027`, commit
`2e0832c735d97c7da93cb79c0cce23e533dd7f1a`, tree `c95f9d4d803bef4be552736a79a4855e5bea5bf9`
(parent `bc5b58351cc334d36112167c9463a80184411cc6`), unmerged; no pull request, merge or deployment.
On that exact tree the full gate passed all six components (49 steps) in the Linux cloud container,
superseding the visual-baseline and gate run 4 notes above for that tree only. A formal independent
review returned APPROVE with seven low findings under the one-time absent-private-suite exception
recorded in `.claude/agents/independent-reviewer.md` for that candidate only; private
`tests/holdout/` coverage is UNVERIFIED, never PASS. The two earlier formal BLOCKs of tree
`3c3b0d28` remain correct history. Hosted CI has not run: `ci.yml` triggers only on pushes to
`main` and on pull requests.

This entry and the routing lines added with it are a later, unpublished documentation successor;
the checkpoint's gate and review results do not qualify these or any other modified contents.

Current active work is that unpublished Linux cloud foundation successor: navigation/handoff
routing and gate/review freshness repair (see the
[gate preflight plan](superpowers/plans/2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27)).
The published commit above is the preserved qualification checkpoint, not the active stage. The Mac
portability successor stays open with its requirements intact but is deferred: not the current stage
or active owner, and not abandoned scope.

Canonical
[Packet 1](context/feature-readiness-checklist-2026-10-27.md#packet-1-close-the-successor-exact-tree-gate)
is unchanged. Its interrupted de074 successor and 48-of-49 result are preserved historical
prerequisite evidence, not the current c95 result and not a completed feature; no equivalence
between Packet 1 and the current successor is asserted. CHK27-PV01 resolves only through the
private map and is not independently repository-accessible evidence.

Evidence locations differ. In the repository: the published commit and the linked plan sections.
Container-local and git-ignored, so not durable repository evidence: the gate stamp and component
receipts under `.alpha/state/`. Session receipts, logs and review outputs live outside the
repository; delivery of the final evidence package to the owner is pending, not completed.

Open blockers: successor private-suite acceptance is unresolved and the exception covers no later
change; stale Darwin ML-lab baselines; unconfirmed root cause of the native lease/cleanup flake;
the about 21-byte `TMPDIR` limit from the AF_UNIX socket path; unverified RD-Agent archive SHA;
the gate stamp and review consumption gap (commit-time checks bound only the tree hash and the
risk-tier diff; a repair is implemented in the unpublished successor, see the
[gate preflight plan](superpowers/plans/2026-10-26-gate-preflight-selection.md#commit-time-gate-and-review-provenance-2026-10-27),
but not yet full-gated or independently reviewed); the
[gate preflight plan](superpowers/plans/2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27)
statements that no owner exception or reviewer policy changed are no longer current (an appended
note there corrects them; the original lines are kept); the missing `alpha ml refit-plan`/`refit-status` entries in `.claude/rules/alpha-cli.md`; the open but deferred
[Mac portability successor](superpowers/plans/2026-10-26-mac-portability-qualification.md#handoff-and-next-action).
Full scope stays with the
[canonical feature checklist](context/feature-readiness-checklist-2026-10-27.md).

## 2026-10-28 Native costed claim and lease fixture repairs (unpublished, not accepted)

The native fixture claim now admits the rule runtime `rule_profile` as the environment value it
has just verified against the approved implementation fingerprint, instead of hashing the
runtime a second time. This removes about 4s from the costed owner's in-deadline preparation
and closes an unapproved-profile binding gap; every other trust-boundary check is unchanged.

The durable-lease silent-child test holds its child until release instead of relying on a fixed
0.25s lifetime.

Gate run 7 on the preceding tree failed (2 tests) and remains the failed checkpoint. These
changes are not yet full-gated or formally reviewed; private coverage is UNVERIFIED. Details:
[native plan](superpowers/plans/2026-10-26-native-rule-authority.md#cloud-foundation-successor-native-and-lease-runtime-findings-2026-10-28).

## 2026-10-28 Foundation batch: pre-run evidence preservation and opt-in cloud bootstrap

Gate entry routes (`run_full`, `run_component`, `run_gate`) now copy existing stamp, receipt,
review/quant attestation and coverage files to a hash-named, verified, mode-read-only checkpoint
before replacing them, once per run, and stop before any overwrite if that copy cannot be verified.
`scripts/cloud_setup.sh` gains opt-in (`ALPHA_CLOUD_FOUNDATION=1`) guard, exclude, pinned RD-Agent,
qualified-venv validation, fontconfig and `origin/main` reporting steps. The native plan carries
the stage contract and ordered foundation backlog. The gate8 checkpoint (tree `fd960490`, public
full gate passed, review BLOCK) is separate; this batch is unqualified. Details:
[native plan](superpowers/plans/2026-10-26-native-rule-authority.md#foundation-stage-contract-and-handoff-icm-aligned-alpha-adaptation).

## 2026-10-28 Gate10/gate11 startup repairs (unpublished, not accepted)

Gate10 failed one lifecycle start test with its cause undetermined, because the owner log was not
retained. The gate11 retry failed three browser cases. The successor tree adds:
- a lazy CLI command-group dispatch: `data symbols` 4.19 s to 1.22 s;
- deferred native-loop imports on the synthetic start path:
  - supervisor import 2.39 s to 0.65 s;
  - the status/claim path's `CostedRuleStudy` edge (1.44 s), which the first fix missed;
- event-based lifecycle readiness in place of an incidental 6 s fixture bound. It has named prompt
  no-start failures and a hang guard only. The production owner deadline is unchanged.
- diagnostic-only failure retention.

Each change has a discriminating regression and independent review. A native compatibility
confirmation passed 254 with 0 skipped. Open findings:
- the TMPDIR-inheritance regression ran a 2 s `success` owner that timed out four times under
  `-n 4` (one before payload spawn, three after). No plan sets a start-up bound for it, so it now
  passes an explicit 5 s fixture budget. The default and every strict expiry test are unchanged.
  Why only this test timed out, while siblings with the same budget did not, was not established;
- cold-I/O margin after the fix not independently measured; readiness margins are recorded per run.

Gate12 on the approved candidate failed in backend pytest (4 failed, 1 error) and was not
published. The independent review found no evidence of a production regression:
- three sibling 2 s success-precondition owners ended in `timeout`, two of them by preparation
  expiry, so the asymmetry above did not hold;
- one test asserted on a conservative bound;
- a setup error is consistent with an unwaited owner `Popen` in cancel-pending (not proven).

Test-only repairs followed:
- explicit 5 s budgets for those three tests;
- `finally` cleanup with a red-to-green regression;
- a bounded wait on the owned owner `Popen` when a stop cannot be delivered. There is no signal,
  and a still-live owner fails loudly;
- a readiness-based delayed-start assertion. Defaults, strict expiry
controls and production are unchanged. Focused 25/25 and native compatibility 425/425 passed. No
full gate has run on the repaired tree. Review remains BLOCK on the absent private holdout suite.

Gate13 on the owner-approved `11b8540e` failed only in the atlas tests and was not published. The
startup-margin receipt was 3.770 s.
- Cause: the lazy CLI dispatch had silently removed all 24 CLI→module edges from the atlas map, and
  had made a CLI documentation drift test vacuous.
- Repair: the extractor reads the `GROUPS` registry and fails loudly on an unreadable shape; the
  drift test reads the registry.
- Disclosed as truthful: 26 `main → *_cmds` static `depends_on` edges are absent because those
  imports are runtime registry imports, and one edge is absent because the reviewed claim repair
  removed its import.
- Checks: atlas 104/104; drift and docs 54/54. No full gate on the repaired tree.

PR #95 follow-up:
- Hosted coverage: 92.91% was repaired with public synthetic contract tests, measured 93.01%;
  threshold unchanged.
- Gates 15 and 16 failed on owner no-starts; the causes of their uninstrumented stalls (10.2088 s
  and 5.9752 s) stay UNKNOWN.
- Phase capture localized a production defect: the owner's claim lazily imported heavy validators,
  about 1 s, under the store write lock and inside the deadline window.
- Fix: `_run_owner` now preloads them before the deadline starts.
  - The deadline start point, poll-point checks, budgets and assertions are unchanged.
  - About 0.8-0.9 s of claim-validator import work moved out of the deadline window and the store
    write lock. Total owner start-up latency is unchanged.
  - A regression test pins the no-import-under-lock invariant on the synthetic-fixture claim path;
    it was red, now green. Rule-native claims still hash the runtime under the write lock
    (pre-existing, disclosed).
- Focused native set: 453/453.
Details:
[native plan](superpowers/plans/2026-10-26-native-rule-authority.md#gate10gate11-repairs-and-retained-diagnostics-2026-10-28).


## 2026-10-29 — Isolated PR93 recovery reconciliation on PR95

The retained PR93 recovery and cancellation implementation is reconciled locally onto published
PR95 `cf9d53b2ea0fa2d2cff502e2aeeefd7572653839`. Stale reconciliation independently retains native
claims and ordinary D1/D2 research jobs: heartbeat age and a local PID miss cannot establish
remote owner termination. Failed-D1 journals match the exact project, contract, deep stage and
strict integer attempt in one SQLite snapshot; recovery reuses only immutable, verified D1
publication. Active cancellation keeps the durable owner bound until checkpoint handling, and
unbound cancellation uses an expected-state guard. PR92 redaction is already retained.

Two pre-implementation controls failed on the published baseline; the integrated focused research
suite passed 26 cases, generic job-store checks passed 6, and native/adjacent compatibility checks
passed 57. Changed Python lint/format, strict typing and all 13 import contracts passed. The
[reconciliation packet](superpowers/plans/2026-10-29-pr93-recovery-reconciliation.md) tracks the
remaining exact-tree producer, Atlas and review evidence. No historical gate or missing-suite
exception attests this candidate. Full qualification and reconciliation with Claude's final
published test corrections remain pending; no commit, push, PR mutation or merge is claimed.


### PR93 final-head qualification continuation

The isolated recovery/cancellation candidate now retains final PR95 commit
`2b967311be376cb1f96159d2137f964b05c03c77`, including native-supervisor validator preloading
outside the claim write lock, explicit elapsed/deadline disclosures, final regression coverage
and reviewer records. Atlas is regenerated from this combined tree. The owner approved an
absence-only private-suite exception for this bounded PR93 work through delivery; absent private
coverage remains UNVERIFIED. All other checks and independent review remain mandatory.
Final aggregate/review outcomes are recorded in the candidate evidence; historical receipts are
not reused. Publication waits for verified PR95 integration into main and parent coordination.

## 2026-10-30 Software Team workflow candidate

Based on merged main `f847581`, the existing development workflow now has the missing scoped
Linux orphan-test precondition. The test-process owner publishes PID/birth identity after enabling
subreaping; the two orphan-dependent durable-lease tests reject absent/stale/unrelated owners
before their bodies launch processes. Actual direct and pytest-worker launches through the owner
pass. This diagnostic precondition does not confer authority or independently prove another
process's subreaper flag. Existing descendant cleanup assertions and time budgets are unchanged.

The canonical feature/incremental skills and implement/plan commands now agree with the focused
development loop: carry authorized work through fixes, QA, independent review and context upkeep;
group related verified slices when coherent; require the unchanged exact-tree full gate and
independent approval before every actual commit. Existing roles are reused. No new team framework,
product research agent, statistical threshold, guard bypass or private-suite exception is added.

The failing-first setup probe observed the original missing precondition (expected nonzero,
observed exit 0). After implementation, 58 process-owner/lease tests passed, including real worker
inheritance and invalid identity cases. Existing harness/skills, Git guard, component receipts,
awareness and manual checks passed: 322 passed, 1 optional upstream-plugin check skipped.
Scoped Ruff, mypy and harness lint passed. These are focused results only. At writing, the final
six-component gate and independent review are pending; their exact-tree receipts belong in the
candidate evidence. Private coverage remains UNVERIFIED and requires a new scoped owner decision
before formal delivery; publication also awaits parent authorization. See the
[completion plan](superpowers/plans/2026-10-30-software-team-completion.md).

### Orphan-precondition scope completion, 2026-10-30

The narrow candidate subsequently passed the canonical six-component gate on unchanged Git tree
`6c14cc8c1fea8c4b693f9fda2a74053fd8667a1d`; its original patch and receipts remain preserved.
Independent review reported no source findings but remained BLOCK for the absent private suite.
That pass does not qualify this expanded tree.

A bounded public process-test inventory found five further tests requiring prompt external
orphan reaping: research interruption, suite leader-exit cancellation, suite nested-worker
cancellation, workstation nested-child cancellation and workstation startup-abort cleanup.
Each failed with its original assertions and budgets when a diagnostic supervisor retained
adopted zombies until pytest exited; the outer owner retained final cleanup responsibility.
This controlled missing-reaper premise does not measure PID 1 behavior. Five missing early
guards also failed the setup regression matrix (5 failed, 2 passed) before implementation.

All seven dependent tests now request the existing fixture, with direct and pytest-worker
acceptance coverage. The five covering modules passed 135 tests. Actual unsupported invocations
of all seven were then rejected before their bodies spawned descendants, with no adopted orphan
left by those refusals. Application code, cleanup assertions and budgets are unchanged.
Cooperative parent reaping, direct-child cleanup, pidfd exit-only checks, stopped-execution checks,
mocks and tests that launch the owner themselves retain their existing contracts. The test-layer
rule records how future externally reaped cases join the fixture and acceptance matrix.

At writing, expanded-tree aggregate verification and independent review remain pending. The
task-scoped absent-private-suite decision and publication authorization remain pending; private
coverage is UNVERIFIED. The filesystem owner's zero-byte manual discovery-link replacement is
reserved for combined integration; no duplicate link is added here.

### Configured UV cache portability correction, 2026-10-30

The expanded candidate's first aggregate stopped in backend coverage: 2 failed, 6,713 passed,
61 skipped, 2 subtests passed; coverage reached the unchanged 93.0% floor at 93.01%. Both failures
were parameter-free ML capability routes returning 422. The failed run and earlier narrow pass
remain preserved; neither qualifies this corrected tree.

Targeted diagnosis reproduced both failures alone and after a neighboring mock test in reversed
order. Clean pinned main `f847581` passed both before isolated worker installation and failed both
afterward. Its relevant production/test files were byte-identical to the expanded candidate.
The web-to-CLI allowlist discarded configured `UV_CACHE_DIR`, so installed-worker invocation
used an unwritable default cache. Direct CLI/worker output was valid schema version 1; forwarding
only the cache variable in a diagnostic process made both routes return valid 200 responses.
Thus worker availability exposed an existing environment-portability defect, rather than an
owner-guard regression or response-schema mismatch.

The correction adds only the non-secret `UV_CACHE_DIR` name to the existing process allowlist.
A portable configured/absent regression was red first (2 failed, 2 passed), then the focused
web/CLI/worker set passed 38 tests, including both original API cases. HOME, CODEX_HOME,
OPENAI_API_KEY, owner metadata and unrelated shell fields remain excluded in the tested ML and
generic command environments. Worker failure propagation, no-sync inspection and response
validation remain unchanged. Claude-owned response-schema and local-PDF files are untouched.

At writing, corrected-tree independent review and final aggregate verification remain pending.
Private coverage remains UNVERIFIED; the task-scoped absence-only decision cannot waive public
failures. Publication authorization remains pending. The manual's cache pointer brings it to
5,998 bytes; the filesystem owner's zero-byte discovery-link substitution remains compatible.

### Through-delivery absence decision and recorded-tree qualification, 2026-10-30

The corrected implementation passed all six canonical gate components on unchanged Git tree
`cf154fec628d71dd92122aa0df1cca40b4d8989c`. The gate started at 05:15:41 UTC; its stamp and six
component receipts remain preserved. This pass validates the cache correction with the installed
worker present and retains the earlier failure and clean-main diagnostic history.

At 05:41 UTC the owner approved the bounded absence-only private-suite exception through delivery
for cleanup/refactor, file-system, Software Team and two-bug follow-up work, including necessary
integration fixes. The reviewer policy now records that task scope, rather than requiring another
owner decision for each changed tree. Private coverage remains UNVERIFIED; no private source was
read or edited and no actual failure is waived. Private authorization provenance stays outside
publication payloads. Normal public checks, exact-tree verification, independent review and Git
guards remain mandatory; no GitHub APPROVE review or protection bypass is authorized.

The approval record is itself a protected source change. At writing, its final tree still requires
fresh full verification and independent attestation. No earlier stamp is rebound or reused as that
tree's acceptance. Publication remains subject to coordination and its separate authorization.


## 2026-10-30 Delivery status and bounded cloud cleanup reconciliation

Direct GitHub and Git parentage checks confirm [PR95](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/95)
merged at `dabdb08fee9ee4637339d26016d85acf16937546` and
[PR96](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/96) at
`f847581f2703f6b5b36aeccdf877c4354a19e176`. Their head CI runs
[40962372679](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/40962372679) and
[40972171573](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/40972171573)
each completed with seven successful listed jobs. The plans now distinguish those delivered
engineering packages from their historical unpublished/BLOCK checkpoints; earlier failure and
UNKNOWN-cause records remain unchanged. Private coverage remains UNVERIFIED.

The [bounded cleanup/refactor successor](superpowers/plans/2026-10-30-project-lineage-projection-refactor.md)
consolidates project-history policy and removes the test-only `changed_paths` wrapper in favor of
`comparison_context`; existing selection and gate semantics are retained. ADR/governance routes
and local receipt references are cleaned up. The prior 12-path checkpoint passed all six public
components/49 steps on `01bf937e`; the expanded successor needs its own final gate and review.
No prior private-suite exception is inherited, and no publication or merge has occurred.

The [existing hygiene plan](superpowers/plans/2026-10-08-repository-hygiene.md#cloud-visible-ledger-reconciliation-2026-10-30)
records the observed cloud branch/path/operation ledger, retained refs and verified move of the
cancelled docs-only predecessor. The saved Mac ledger, physical storage and historical owner-side
counts remain unverified and separately blocked; no unique local data was deleted. This bounded
cloud reconciliation does not declare the broader cleanup/refactor programme complete.


### Cleanup aggregate re-entry findings (2026-10-30)

The expanded `f1550eca` gate stopped at backend pytest: three failures, 6,711 passes, 61 skips,
two passed subtests; coverage met the unchanged floor at 93.01%. Complete failed evidence is
preserved privately by the [cleanup plan](superpowers/plans/2026-10-30-project-lineage-projection-refactor.md#aggregate-re-entry-findings-and-bounded-repairs).
One synthetic cancellation test read an empty PID marker between creation and content write.
Its deterministic regression was red, then green after the test reader waited for contents
within the same five-second bound. Production supervisor, budgets and exact-once assertions stay.

Two automatic ML capability aliases exposed a separate installed-worker re-entry defect:
web-to-CLI filtering dropped configured `UV_CACHE_DIR`, already allowed by CLI-to-worker launch,
and uv failed cache initialization. ML subprocesses now retain that nonsecret runtime setting.
Credential/auth-home routing, isolation and locked/no-sync launches are preserved. Both actual
installed-worker routes return HTTP 200; no P2 router/API or generated client contract changed.

The properly owned focused selection passed 102 tests after these repairs; scoped typing,
lint and format passed. An earlier direct invocation lacked the required process owner and
failed two reaping checks; that attempt is retained, and the same assertions passed under the
existing ownership runner. Final assembled gate/review remain required; no actual failure is
waived by the pending task-scoped private-suite decision.

## 2026-10-30 — Queryable context filesystem candidate

On main `f847581f2703f6b5b36aeccdf877c4354a19e176` (including PR96), the isolated Atlas tool
now computes project-intent, feature, task, decision, history and reference queries directly
from existing tracked documents. It retains exact file hashes, heading ancestry, line ranges,
source status text and an explicit list of matching excerpts omitted by the selection budget.
JSON handoffs bind the whole allowlisted corpus, retrieval code, query policy and expiry;
validation replays them and rejects changed/added/missing sources, stale policy, expired clocks
and altered payloads. Markdown and plain-text views support direct inspection. No new knowledge
graph, database, folder hierarchy, scientific authority or autonomous execution is introduced.

The [delivery record](superpowers/plans/2026-10-30-queryable-context-filesystem.md) maps H26
from the sole canonical feature checklist to the implementation and the actual primary ICM
paper (arXiv2603.16021v2, 21 pages) plus pinned companion source. Mechanical invalidation and
expiry are ALPHA adaptations, not demonstrated performance gains from the paper. Existing
source ownership, decisions, provenance and dated plans remain authoritative in their own homes.

Focused current context regressions passed 16 cases and strict Atlas typing passed 25 source
files. An earlier Atlas-wide candidate passed 119 tests before the additional final regression;
final producer, aggregate and independent-review evidence remain separate exact-tree obligations.
Local Git guards were installed. Patch checkpoints are retained under ignored
`.alpha/state/context-delivery/`; this entry claims no commit, publication, merge or aggregate
acceptance. No private holdout files were found through tracked-path metadata; their content was
not read, coverage remains UNVERIFIED and prior scoped exceptions do not cover this delivery.
This context filesystem is separate from bulk-document storage and backups. Mac backup remains
owned elsewhere and unavailable; ignored query receipts are not durable backups.

### File-system delivery: owner absence-only decision, 2026-10-30

The owner approved the bounded missing-private-suite exception through delivery for the
cleanup/refactor, file-system, Software Team and two-bug follow-up workstreams at 05:41 UTC,
including necessary integration fixes. The exact request, response, scope and unchanged
requirements are recorded in the existing
[file-system plan](superpowers/plans/2026-10-30-queryable-context-filesystem.md#owner-absence-only-decision--2026-10-30).
Documented absence alone is now informational for this delivery; private coverage remains
UNVERIFIED. No actual failure or other required check is waived, and no GitHub APPROVE review
or protection bypass is authorized. Earlier absence-only BLOCKs remain correct history.

All six public components passed before this approval metadata on exact tree
`65bb2cd19462836e77c8619ea736399514d33f598fccfc91bc7fc2a73479f9ce`, with a valid full stamp,
120 passing Atlas tests, fresh six-route navigator evidence and source-bound handoff/reopen
evidence. That checkpoint is preserved separately. The approval record changes the candidate;
its final exact-tree qualification, independent review and normal attestation remain required.
Commit/publication/PR/merge preparation remains subject to parent coordination of the exact
payload and branch. No Mac backup, bulk storage or wider scientific completion is claimed.

### File-system qualification: configured ML cache transport repair

The real approval-record aggregate failed two public capability-route cases with HTTP 422;
6,695 cases passed, 61 skipped and coverage reached 93.01% against the unchanged 93% floor.
The private-suite exception does not waive those actual failures. After Qlib was installed,
the web-to-CLI environment dropped the configured `UV_CACHE_DIR` and the installed worker's
`uv` could not initialize its protected fallback cache. The direct CLI succeeded with the
configured cache inherited. Failure evidence remains preserved.

A two-line command-scoped transport repair now preserves the configured cache for ML commands
only. Its failing-first public regression and the existing credential/auth-home isolation and
two real capability-route checks passed (5 cases); changed lint/format passed. No ML response
schema or PDF source was changed. The
[existing delivery plan](superpowers/plans/2026-10-30-queryable-context-filesystem.md#required-integration-repair-configured-ml-worker-cache)
records this necessary integration fix. Final source/producer reconciliation, exact-tree full
qualification and independent review remain required; private coverage stays UNVERIFIED under
the approved absence-only scope. No failed check, threshold or authority boundary is waived.

### Combined foundation integration candidate, 2026-10-30

The Software Team batch passed all six public components and independent review on Git tree
`80dbba4d52d15cce1d66f7b233a7637f11cf3a56`; its installed guards accepted commit
`b49e187392f4eb1132df2db5536d70203e91747f`, normally pushed to its named branch. Cleanup
commit `8f3d8b4394c3eabb08dda2ce21a9b18eb363aac0` was fetched through configured origin and
matched the producer's tree. Its supplemental disposition patch matched the supplied 4,472-byte
SHA-256 before applying. The filesystem's eight source blocks matched every individual hash
and the full 49,497-byte payload (`500395592164e585c30087ba773924dd9ca40312dd74634e214d386caa301002`).
Library byte downloads failed; no further Library download was attempted after coordination.

Both append-only histories are retained, and the manual's context-map link uses the agreed
byte-neutral substitution. The combined implementation retains the canonical process allowlist
entry for configured non-secret UV_CACHE_DIR; cache configuration is not a provider credential
and is available to generic CLI commands. The duplicate ML-only clause is removed, while
capabilities/train provider/auth-home exclusions complement the configured/absent ML and generic
command regression. The historical producer ML-only repair above describes its earlier tree.
The empty PID-marker readiness correction, history projection refactor and scoped orphan-test
preconditions retain their original lifecycle assertions and budgets. Queryable context remains
engineering navigation, separate from product research agents and scientific admission.

The [single reviewer-policy record](../.claude/agents/independent-reviewer.md#four-workstream-through-delivery-absence-exception--2026-10-30)
records the approved through-delivery absence exception. Private coverage stays UNVERIFIED;
actual checks, exact-tree review and installed Git guards remain mandatory. The owner's repository
delivery instruction authorizes coordinated commits/pushes; this candidate has not merged to main.
Focused combined cleanup checks passed 139 tests and scoped Ruff passed. Atlas regeneration,
fresh context handoff demonstration and final combined-tree gate/review are separate remaining
obligations at this entry; no standalone receipt qualifies this assembled tree. Final receipts
and publication disposition are retained in the exact candidate's ignored evidence directory.
