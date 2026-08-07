# Research-First Workstation — Authoritative Design

**Date:** 2026-08-07
**State:** Design approved; no phase implemented. Extends the Research Scientist program
(`2026-08-06-research-scientist-program-design.md`), which remains authoritative for Gate 0–1
mechanics, the D0 fixture, and the schema-v2 research control plane.
**Authority:** `CLAUDE.md`, ADR-0011, ADR-0014, ADR-0015, ADR-0018, ADR-0019, ADR-0020, and the
proposed ADR-0021 through ADR-0026.
**Phase plans:** `docs/superpowers/plans/2026-08-07-research-first-R1-command-center.md` … `R6`.

## 0. Purpose and non-negotiable separation

The application's default lifecycle is research-first. It is never
`idea → trading rules → backtest → optimise`. It is:

```
IDEA → DEFINE THE QUESTION → UNDERSTAND THE PHENOMENON → FIND EXISTING EVIDENCE
     → FIND AND VALIDATE THE DATA → FORMALISE THE HYPOTHESIS → DEFINE FALSIFICATION
     → RUN NON-STRATEGY RESEARCH → TEST EXISTENCE → TEST MEANINGFULNESS → TEST STABILITY
     → EDGE-VALIDATION GATE → only then STRATEGY DEVELOPMENT → BACKTEST → VALIDATION
     → OPTIMISATION → ML WHERE JUSTIFIED
```

Two AI-boundary rules are permanent product properties:

1. **Claude Code builds the application. Claude is never the in-product research or
   strategy-development AI.** No surface may present Claude chat as the research collaborator.
2. **Codex (OpenAI) is the sole in-product research/strategy AI collaborator**, attached through
   the `alpha` MCP server (`.codex/config.toml`). There is no generic "choose your AI provider"
   abstraction, no OpenAI API key inside the application, and no in-app chat transport. The
   application's job is to give Codex governed tools, bounded context, and durable artifacts —
   not to host a chatbot.

This program builds no live-capital route, grants no new order authority, and changes no paper
boundary. All prior invariants (PIT firewall, two-clock corporate actions, determinism, typed
errors, the import DAG, owner-only decisions) continue to bind every phase.

## 1. Research-First Architecture

### 1.1 The two planes and the one join

The system separates eight concerns onto two existing planes plus one join:

| Concern | Object | Plane | Store |
|---|---|---|---|
| IDEA | Research Case `raw_idea` (exact owner wording) | Research | `control/workstation.sqlite3` schema v2 |
| RESEARCH | Research Case (9 phases × 6 execution states) | Research | same |
| HYPOTHESIS | Immutable exploration/confirmation contract (`rc_…`) | Research | same |
| EVIDENCE | Typed findings, attempts, source claims, gate packet | Research | same + immutable run artifacts |
| EXPERIMENT | Contract-declared D0/D1/D2 research runs | Research | `data_dir/research/…` + v3 run store |
| STRATEGY | Strategy project, immutable versions (14 dev stages) | Strategy | schema v1/v2 project tables |
| BACKTEST | Canonical engine runs | Strategy | v3 run store |
| VALIDATION | Gauntlet, holdout, decision packets | Strategy | v3 run store + control plane |

The **only** join is `research_contract_strategy_links` / `research_contract_experiment_links`,
written at promotion (`advance_to_strategy` after a `SUPPORTED` outcome through consumed D2). A
research case exists, progresses, and terminates without any strategy object; a strategy version
cannot be created for a research-required project without the approved confirmation contract and
the owner's promotion decision (already enforced in `ControlStore.create_strategy_version`).

### 1.2 Lifecycle mapping (normative)

The conceptual Stage 0–14 lifecycle maps onto existing machinery. It is a **mapping**, not a UI:

| Conceptual stage | Home |
|---|---|
| 0 Idea capture | `captured` phase (`alpha research capture`, NL only) |
| 1 Research definition | `triage` (Codex intake protocol; ≤3 material questions) |
| 2 Evidence & literature | `triage` + source plane (sources/claims; packs frozen pre-confirmation) |
| 3 Data discovery & validation | `triage` feasibility + dataset registration + `run data-audit` |
| 4 Hypothesis formalisation | `exploration_review` (immutable contract freeze) |
| 4b Detector/mechanics proof | `pilot` (D0, synthetic) |
| 5 Exploratory research | `deep_research` on D1 (contract `analysis_plan`) |
| 6 Phenomenon testing | `deep_research` on D1 (same contract, registered families) |
| 7 Falsification & robustness | required falsifiers + registered sensitivity families on D1 |
| 8 Evidence synthesis | `confirmation_review` (family freeze) + gate-packet layers |
| 8b Confirmation | `sealed_confirmation` on D2 (one-shot) |
| 9 Research gate | `research_decision` (outcome × disposition) |
| 10–13 Strategy dev / backtest / validation / optimisation+ML | existing 14 dev stages, entered only via promotion |
| 14 Candidate | existing `candidate`/`decision` stages |

Decision-vocabulary mapping: PROMOTE = `advance_to_strategy` (requires `SUPPORTED`);
CONTINUE RESEARCH = remain in phase / next contract-scoped work; REFORMULATE = `revise`
(new contract lineage, audited D2 reuse rules); INSUFFICIENT EVIDENCE = `INCONCLUSIVE` outcome;
REJECT = `reject`; ARCHIVE = `park`. Negative and terminal results are permanent records
(attempt ledger, decision events, terminal packets); nothing is deleted.

### 1.3 The anti-wizard principle (normative)

The lifecycle is represented by **phases, evidence zones, and Evidence Hub sections — never by a
fourteen-screen wizard**. No phase may be reduced to a form-completion checkbox. A screen may show
where a case is and what the single `next_action` is; it may not present methodology as a survey to
click through. Any future UI change that adds a per-stage wizard step sequence violates this spec.

### 1.4 Exploration vs confirmation (existing, restated as product law)

Contract `scope ∈ {exploration, confirmation}` is the preregistration boundary. Exploratory
artifacts carry the `EXPLORATORY` watermark; sealed confirmatory artifacts carry
`REGISTERED CONFIRMATORY`. D2 is one-shot under an immutable, content-hashed boundary; D3 is
prohibited to research. Success criteria are frozen in the contract before the evidence is seen;
a changed hypothesis is a **new contract lineage** (`parent_contract_id`), never an edit.

## 2. Research Command Center Design

### 2.1 The desk

A seventh Workstation desk, preset id `research`, display name **Research Command Center**,
short name `RESEARCH`, added to `WorkspacePresetId` and `WORKSPACE_PRESETS` in
`apps/alpha-web/frontend/src/layouts/presets.ts`. Layout (Dockview anchors):

```
┌────────────────────────────────────────────────────────────────────────────┐
│ topbar: DESK | LINK GROUP | SYM | ASOF | RESEARCH CONTEXT | STATUS         │
├───────────────┬──────────────────────────────────────┬────────────────────┤
│ ResearchBacklog│ ResearchCockpit (active case)        │ CodexBench         │
│ (left, 300)    │  · sticky case header + scorecard    │ (right, 420)       │
│  buckets:      │  · thesis / HypothesisCard           │  · packet composer │
│  needs_owner   │  · budgets, lineage, next action     │  · protocol picker │
│  running       │  · approval boundary (CLI line)      │  · packet history  │
│  ready         ├──────────────────────────────────────┤  · notes stream    │
│  blocked       │ EvidenceHub (below, 320)             │                    │
│  closed        │  tabs: overview·data·literature·     │                    │
│                │  mechanism·exploration·experiments·  │                    │
│ inactive tabs: │  for·against·falsification·          │ inactive tabs:     │
│ PriceChart     │  robustness·decision                 │ ResearchDataExplorer│
│ RunBrowser     │                                      │ JobMonitor         │
└───────────────┴──────────────────────────────────────┴────────────────────┘
```

Panel inventory: `ResearchBacklog` (new), `ResearchCockpit` (existing, promoted from
palette-only), `EvidenceHub` (new), `CodexBench` (new, Phase R2), `ResearchDataExplorer`
(new, Phase R3), plus `PriceChart`/`RunBrowser`/`JobMonitor` reuse through link groups. All panels
follow the registry contract (`guarded()` dormancy + error boundary, `PANEL_MENU` entries,
e2e desk registration, axe zero serious/critical).

### 2.2 ResearchBacklog

Serves the **already-tested, currently unserved** model in
`apps/alpha-web/frontend/src/panels/researchCockpitModel.ts`: `researchCaseBucket()`
(`needs_owner | running | ready | blocked | closed`), `sortResearchCases()`
(bucket → owner-pinned → priority → updated_at → case_id), `researchCaseProgress()`
(milestone and budget fractions, native units, never summed across resources). The priority rubric
is the spec-§10 advisory rubric — falsifiability, data readiness, novelty, information gain per
unit cost. **Expected profit is never a priority input.** Selecting a case sets the linked-context
`projectId` and drives the Cockpit + EvidenceHub. Requires the new read-only
`GET /api/research/cases` route (ADR-0021).

### 2.3 Case header and scorecard strip

The Cockpit gains a sticky header: case name · phase · execution state · responsibility
(`owner`/`codex`) · exact `next_action` · a compact Readiness Scorecard strip (§10) · elapsed and
remaining budget in native units. One glance answers "where is this case, who acts next, on what."

### 2.4 New Idea entry

A top-level **New Idea** action (topbar button on the research desk + command-palette entry
"New Idea / New Research"). It opens the capture form: one natural-language textarea (≤8192 chars)
and an optional name. **It contains no entry-rule, stop, target, indicator, parameter, or
optimisation input of any kind**, and the e2e suite asserts that absence. Capture calls the
existing `POST /api/research/cases`; the reply's ≤3 material questions (closed choices with
consequences) are the only structured follow-up.

### 2.5 What the Command Center cannot do

Unchanged Gate-1 authority: no approve/reject/decide, no D2 consumption, no D3 reveal, no paper,
no orders, no arbitrary Python, no source-network fetch from the browser. Owner mutations remain
trusted-local CLI; the Cockpit's `ApprovalBoundary` keeps printing the exact CLI command. The
backlog and Evidence Hub add **read-only projections only** (ADR-0021 supersedes the Gate-1
"cannot list all cases" scope statement for reads, and only for reads).

## 3. Codex Integration Design

### 3.1 Where Codex appears

- **CodexBench** panel (research desk): context-packet composer, protocol picker, packet history,
  notes stream. This is a workbench, not a chat: the conversation itself happens in the owner's
  Codex CLI/IDE session attached to `alpha` MCP; the bench prepares, records, and displays what
  Codex is given and what it produced.
- **DevelopmentCenter**: the existing "Prepare Codex task" (AgentBrief) plus, after R6, the
  carried-forward research block.
- Everywhere agents act, the surface shows the responsibility field (`owner`/`codex`) and the
  authority boundary text.

### 3.2 What Codex receives — context packets

A **context packet** is a bounded, content-addressed, recorded unit of context:

- Table `research_context_packets`: `packet_id` (`cp_<sha256>` of canonical payload JSON),
  `project_id`, `packet_kind ∈ {asset, research_case, experiment, chart, validation,
  strategy_promotion}`, `protocol_id` (nullable), `protocol_content_hash` (nullable),
  `payload_json`, `created_by`, `created_at`. Append-only.
- Packet contents are assembled server-side from authoritative records only (case summary,
  contract, dataset refs, quality reports, claims, findings, attempt ledger, charts metadata +
  bounded series) inside one read snapshot, following the `get_agent_brief` pattern (bounded
  limits, point-in-time, fail-closed warnings, truncation flags).
- **Recording is visibility.** The CodexBench shows the exact JSON of every packet ever built;
  MCP returns the identical bytes. There are no invisible context dumps: if Codex saw it through a
  packet, the owner can open it.
- Delta brief: `get_research_brief(project_id)` returns the spec-§10 "Resume with Codex" packet —
  what finished since the last owner visit, what changed, what remains, the exact next action.

Packet kinds map to research tasks: `asset` (shared asset knowledge + evidence search),
`research_case` (hypothesis, data, results, papers, open questions), `experiment` (exact
spec + result), `chart` (chart metadata + underlying bounded series), `validation` (claims and
evidence under challenge), `strategy_promotion` (the complete promotion dossier, §11).

### 3.3 MCP tools (the Codex seam)

Added across phases, each addition consciously updating the pinned tool-set test:

| Phase | Tool | Class |
|---|---|---|
| R2 | `get_research_brief` | read (delta brief) |
| R2 | `build_research_context_packet` | draft-write (records packet, returns bytes) |
| R2 | `get_research_context_packet` | read |
| R2 | `list_research_protocols` / `get_research_protocol` | read |
| R2 | `add_research_note` | draft-write (commentary, never evidence) |
| R3 | `get_data_inventory` / `get_data_quality` / `get_data_candles` / `list_snapshots` / `get_provider_registry` | read |
| R4 | `search_research_sources` / `get_research_source` / `draft_source_claim` | read / draft-write |

Forever absent: approve, reject, decide, D2 transition, D3 reveal, paper, orders,
`corroborated`-status writes, arbitrary code execution.

### 3.4 How Codex output becomes persistent artifacts

Three channels, strictly separated by epistemic status:

1. **Commentary** (critiques, confounder reviews, test designs, completeness reviews, syntheses)
   → `research_case_notes` (append-only: `note_id`, `project_id`, `note_kind ∈ {critique,
   confounder_review, test_design, completeness_review, synthesis}`, `body`, `author`,
   `author_kind ∈ {owner, agent}`, `context_packet_id`, `created_at`). Notes are **structurally
   outside** the evidence model: the gate packet's evidence-basis ladder reads typed run
   artifacts and cited evidence only, never notes.
2. **Claims about external literature** → `research_source_claims` drafts (§7), elevated only by
   owner screening.
3. **Empirical results** → contract-governed research runs (D0/D1/D2) producing immutable
   artifacts; admission mechanically re-verified. Codex cannot author a result; it can only
   propose work that the governed runners execute.

### 3.5 Distinguishing unverified Codex claims from verified evidence

Already-existing mechanisms are the answer; this spec adds no new trust machinery:

- Evidence records: agents write `draft` only; `corroborated` requires the owner path.
- Gate packet: the evidence-basis ladder (`SEALED_D2 > EXPLORATORY_D1 >
  NO_TYPED_NON_SYNTHETIC_EVIDENCE`) and the `NOT_TESTED` findings vocabulary make unsupported
  claims visually impossible to dress up.
- Notes render under an explicit "Codex commentary — not evidence" badge in every surface.

### 3.6 Conversation ↔ project association

Codex sessions are external; the durable association is the packet + note + attempt trail: every
packet, note, contract draft, and launch records `project_id` and actor. The bench's packet
history is the per-project "what has Codex been given"; the notes stream is "what Codex said";
the attempt/decision ledgers are "what was actually done."

## 4. New-Idea Workflow

The complete path from "I have an idea" to "enough evidence to consider strategy development":

1. **Capture (Stage 0).** Owner clicks New Idea, types the observation verbatim. System creates
   the Research Case (restart-idempotent), preserving exact wording forever. No rules asked.
2. **Triage (Stage 1–3).** Responsibility usually `codex`. Codex, via the intake protocol +
   `research_case` packet: states the tentative falsifiable claim, mechanism, expected
   direction/horizon, ≥2 competing explanations; searches prior internal evidence
   (`search_asset_evidence`) and the data inventory (R3 tools) for feasibility; drafts literature
   leads (R4). At most one batch of ≤3 material questions comes back to the owner — only
   instrument/event-availability/outcome ambiguity, never plotting or retry choices.
3. **Contract freeze (Stage 4).** `alpha research draft` materialises the approval-ready
   exploration contract (thesis, alternatives, falsifiers, confounders, topology, statistical
   policy, budgets, stop rules, report plan, `analysis_plan` after R5). Owner reviews the
   HypothesisCard rendering and approves/rejects **on the CLI**.
4. **D0 pilot.** Detector/mechanics proof on the registered fixture; three lifetime launch slots;
   acceptance mechanically recomputed.
5. **D1 deep research (Stages 5–7).** Durable `research:event-study` jobs execute only the
   registered analysis plan on registered datasets: exploration, phenomenon tests, falsification
   and robustness families. Budgets debit; stop rules and continuation triggers bind; every
   attempt (including failures) is ledgered. Evidence Hub fills.
6. **Synthesis (Stage 8).** Codex runs the evidence-synthesis and research-critic protocols;
   confirmation family frozen in the child contract; owner approves confirmation on the CLI.
7. **D2 confirmation.** One-shot sealed run under the immutable boundary; mechanical
   classification (`SUPPORTED/CONTRADICTED/INCONCLUSIVE/INVALID`).
8. **Research gate (Stage 9).** Owner reads the gate packet + scorecard + edge-validation
   checklist and records outcome × disposition on the CLI. `advance_to_strategy` triggers
   promotion (§11); `park`/`reject`/`revise` are first-class permanent outcomes.

At every step the case can pause, block, fail, resume, or terminate early
(`INCONCLUSIVE`/`INVALID`) with an honest terminal packet. Insufficient evidence is a valid,
stored result — never a dead end that vanishes.

## 5. Hypothesis Standard

### 5.1 The standard is the contract; the card is its rendering

The formal hypothesis object **is** the immutable research contract. `HypothesisCardV1` is a pure
projection (Python: CLI/REST; TS: panel model) that renders contract fields in the standard
vocabulary:

| Card field | Contract source |
|---|---|
| Research question | `thesis.prediction` restated interrogatively at draft time |
| Phenomenon | `raw_idea` + `thesis.mechanism` |
| Population / universe | `chart_fingerprint` (instrument, venue, session, bar construction) |
| Condition / event | `event_definition` (name, availability, confirmability rules) |
| Dependent variable | `primary_claim.primary_endpoint` |
| Horizon | `primary_claim.primary_horizon` |
| Expected direction | `primary_claim.direction` |
| Economic mechanism | `thesis.mechanism` + `thesis.interpretation` |
| Null hypothesis | derived: no association at `familywise_alpha` after registered controls |
| Alternative hypothesis | `thesis.prediction` |
| Baseline | registered controls (matched/pseudo-pattern/shuffled/randomised-price) |
| Confounders | `confounders` (≥6 at draft) |
| Falsification criteria | `required_falsifiers` (≥5) + stop rules |
| Success criteria | `statistical_policy` (alpha, power, minimum effect) frozen pre-evidence |

### 5.2 Completeness and versioning rules

- A draft with any unresolved/placeholder material field is not approvable (existing
  `_require_resolved_material`); the card shows Complete/Partial/Missing per field and the
  scorecard's "hypothesis definition" dimension derives from it.
- Contracts are immutable rows; a change is a child contract (`parent_contract_id`) with audited
  D2-reuse relation (`unopened_sealed_reuse` today; `non_overlapping_future` /
  `external_replication` reserved). **Success criteria cannot be invented after seeing favourable
  results**: the confirmation family, alpha, power, and minimum effect are frozen in the approved
  contract before D2 exists, and the gate packet recomputes the classification from the frozen
  numbers — producer attestations that disagree fail loud.

## 6. Research Evidence Model

### 6.1 Evidence objects (all existing, newly surfaced)

- **Typed findings** — every gate-packet finding is `{status, summary}` with status ∈
  `{PASSED, FAILED, STABLE, UNSTABLE, SUPPORTED, CONTRADICTED, INCONCLUSIVE, NOT_TESTED}`.
  Missing evidence renders `NOT_TESTED`, never disappears.
- **Attempt ledger** — `research_attempt_records` keeps every attempted, failed, pruned, and
  completed unit of work with config fingerprints and budget debits: the negative-knowledge store.
- **Evidence ledger** — the existing append-only cited `evidence_revisions` (two clocks:
  `market_data_cutoff` vs `knowledge_at`; exact `run_id`/artifact/field citations; contradiction
  links; `draft → corroborated/rejected → superseded`). Research runs are structurally excluded
  from the generic ledger (research markers reject them); research evidence lives in research
  artifacts and the gate packet.
- **Source claims** (new, §7) — literature evidence for/against, claim-level.
- **Terminal packet** — `ResearchGatePacketV1`, the case's permanent synthesis.

### 6.2 Evidence Hub

One aggregating read-only projection (`GET /api/research/cases/{id}/evidence-hub`) + one panel
with eleven sections. Not eleven dashboards: one workflow surface whose sections fill as phases
progress, each rendering honest empty/`NOT_TESTED` states before then.

| Section | Contents (source) |
|---|---|
| Overview | original idea, HypothesisCard summary, phase/state, current conclusion, scorecard, outstanding questions (`next_action`, unresolved confounders, open notes) |
| Data | registered dataset refs, coverage/quality summaries, data-audit findings, known limitations |
| Literature | claims map: supporting / contradicting / contextualising / method, with strength and screening status; bibliography second |
| Mechanism | `thesis.mechanism`, alternatives, confounders resolved/unresolved, persistence reasoning notes |
| Exploration | D1 descriptive/exploratory artifacts (EXPLORATORY watermark), headline charts board |
| Experiments | attempt ledger view: every registered analysis, config fingerprint, status, run link |
| Evidence for | findings with status `SUPPORTED`/`PASSED`/`STABLE` + supporting claims |
| Evidence against | findings with `CONTRADICTED`/`FAILED`/`UNSTABLE` + contradicting claims — **rendered with identical prominence to Evidence for** |
| Falsification | the required falsifiers and their results (placebo, shuffled, randomised-price, planted-confounder, negative controls) |
| Robustness | parameter-neighborhood, temporal, regime, transportability stability findings |
| Decision | edge-validation checklist, full scorecard, gate packet, decision history |

### 6.3 Chart evidence board

Headline board uses the existing `headlineResearchCharts()` — at most six charts, at most one per
registered category (`event_validity`, `primary_effect`, `parameter_stability`, `confounders`,
`transportability`, `null_multiplicity`; `appendix` never headlines). Every chart is
`ResearchChartData`: question, plain-language answer, uncertainty, caveat, sample sizes, lineage
hashes, watermark. Charts without those fields cannot be rendered — a chart that answers no
registered question does not exist.

## 7. Literature System

### 7.1 Structured source objects (extend, don't replace)

`research_source_records` gains typed columns by additive migration: `doi`, `year`,
`authors_json`; publication, methodology, markets, sample period, and other descriptors remain in
`metadata_json` (typed on read). Sources keep `access_mode ∈ {metadata_only, open_access,
owner_provided}`, `content_hash`, and provenance. Source packs remain content-addressed frozen
sets.

### 7.2 Claim-level evidence (new)

Table `research_source_claims`: `claim_id`, `source_id`, `project_id`, `contract_id` (the
hypothesis version the claim bears on), `claim_text`, `direction ∈ {supports, contradicts,
contextualizes, method}`, `strength ∈ {weak, moderate, strong}`, `method_summary`,
`sample_summary`, `markets_json`, `limitations`, `status ∈ {draft, screened}`, `author`,
`author_kind`, `created_at`. Codex drafts claims (via `draft_source_claim`); **only owner
screening (`alpha research sources screen`) elevates `draft → screened`**. A paper is never
treated as true because it is published: the claim record forces methodology, sample,
limitations, and strength to be stated, and the Literature section renders screened and draft
claims distinctly.

### 7.3 Acquisition worker (Gate 2 made real)

An isolated worker (ADR-0016 isolation pattern; own lockfile; not a root workspace member) that
finally gives the fail-closed primitives in `alpha_cli/research_acquisition.py` a transport:

- Metadata clients: OpenAlex, Crossref, Unpaywall, arXiv (the contract-listed candidate
  services); Google Scholar remains manual-browser-only.
- Document fetch: open-access or owner-provided only; every URL/redirect re-validated through
  `AcquisitionPolicy` (HTTPS, allowlisted IDNA hosts, global addresses only, MIME/size/magic
  checks); every stored object content-addressed under `data_dir/research/objects/` with a
  `SourceReceipt` (`trust_label="UNTRUSTED_SOURCE"` — document text never carries instruction
  authority).
- Retraction/version resolution recorded on the source record.
- Hostile-document suite (malformed PDFs, archive bombs, prompt-injection bodies) is the phase
  gate, per the 2026-08-06 spec §12 Gate 2 row.

## 8. Research Data Hub

### 8.1 Inventory and quality projections (read plane)

The store already computes everything a data explorer needs; this program surfaces it:

- New CLI projection `alpha data snapshots --json` (snapshot id, created_at, source, symbols,
  manifest hash) — the one missing seam.
- Five read-only MCP tools (R3, §3.3) wrapping existing `--json` projections: inventory
  (symbols × range × row counts), per-receipt quality reports (`quality.json` vocabulary:
  `calendar_gap`, `missing_existing_session`, `price_difference`, `invalid_ohlcv`, corrections),
  bounded PIT candle previews, snapshot list, provider registry (capabilities, coverage,
  credential presence — never values).
- `ResearchDataExplorer` panel: coverage matrix (symbol × source × range × quality status), gap
  timeline, quarantine/candidate status, provenance chain (receipt → candidate → quality →
  canonical → snapshot), descriptive statistics, seasonality/regime views, sample-size readouts.
  This panel answers "what do we actually have, and can it answer the question" **before** any
  hypothesis-specific computation.

### 8.2 Research dataset registration

Table `research_dataset_refs` binds the pure `ResearchDatasetRef` (provider, symbol, venue,
timeframe, timezone, session, `content_sha256`, permanent `research_only` scope) to its physical
origin: canonical store slice, immutable snapshot, or QuantPad `FetchReceipt`. CLI
`alpha research data register|audit`. **Fail-closed: no receipt/provenance → no registration; no
registration → a contract cannot reference the data.** Registered refs feed the scorecard's data
dimension and the contract's dataset fingerprint.

### 8.3 Descriptive analytics (pre-hypothesis)

New pure module `alpha_research/descriptives.py` (core-only imports, deterministic): coverage and
calendar-gap summaries, return/volume distributions (moments, quantiles, tails), autocorrelation
where appropriate, seasonality tables (time-of-day/day-of-week where the timeframe supports it),
regime tagging (volatility buckets), effective-sample and event-frequency estimates (reusing
`power.py`). Executed by `alpha research run data-audit` — a bounded synchronous run class whose
artifacts are **descriptive only**: admissible to the Evidence Hub data section, never to the
effect/falsification dimensions. Understanding the data is not evidence about the hypothesis.

### 8.4 QuantPad lane

Per ADR-0018 + ADR-0023: discovery through the registered QuantPad MCP stays bounded; bulk
research data arrives through the official SDK/REST behind a receipt-backed adapter that
preserves symbol/schema identity, UTC event + knowledge time, request/response hashes, coverage
and corrections, then passes the candidate/quality/quarantine path. Qualified data lands as
registered `research_dataset_refs` — still `research_only`, still barred from canonical store,
validation snapshots, strategy evidence, holdout, and paper.

## 9. Pre-Strategy Experiment System

### 9.1 What a research run is not

A research run is **not a backtest**. It has no orders, fills, portfolio, position sizing, or
cost model (costs enter only as the last "economic magnitude" rung). It estimates whether a
phenomenon carries information: conditional association, not trading performance. Research runs
carry `research_only` markers, `evidence_zone`, watermark, `real_market_evidence`, and
`eligible_for_holdout_or_execution: false`; the generic evidence ledger and all strategy surfaces
structurally reject them.

### 9.2 The analysis plan (preregistered per hypothesis)

The exploration contract gains `analysis_plan`: the registered selection of test families for
**this** hypothesis — chosen because the hypothesis and data-generating process demand them,
never as a blanket battery:

- Event study (mean/median forward paths, purged overlap, matched controls)
- Conditional forward-return analysis (by signal quantile / feature bucket / regime)
- Difference-in-means/medians with cluster bootstrap CIs
- Distribution comparison and quantile analysis
- Information coefficient / rank correlation (where a graded signal exists)
- Temporal / regime / subsample stability
- Cross-market or cross-asset transportability (dependence-aware)
- Sensitivity to event definition, thresholds, horizon (the registered neighborhood)
- Placebo tests, negative controls, shuffled/randomised nulls, lead/lag checks
- Leakage diagnostics (future-poison assertions on the exact pipeline)

Each family declares its grid and joins a multiplicity family (Holm today; families frozen at
approval). Anything outside the plan is exploratory-by-declaration: it lands in the attempt
ledger and the multiplicity accounting, and can never headline.

### 9.3 The D1 runner

`alpha research run deep` (Phase R5, ADR-0025) executes the registered plan as durable
`research:event-study` jobs (the reserved heavyweight kind): durable lease + heartbeat +
cancellation, restart-resume from checkpoints, budget debits in native units, stop-rule and
continuation-trigger enforcement. Output per analysis: immutable v3 run artifacts + registered
`ResearchChartData` renderings (EXPLORATORY watermark) + the typed
**`ResearchGateEvidenceV1`** artifact — the already-fully-specified evidence contract
(primary result, mechanism, confounders, stability, multiplicity, power, negative controls,
artifact links, confirmation claim/checks). Admission into the case follows the D0 pattern:
the store re-verifies run identity, zone, markers, and recomputes the acceptance-relevant
numbers; producer pass-flags are never authority.

New pure modules backing the families: `alpha_research/conditional_returns.py`,
`stability.py`, `ic.py`, `leadlag.py` (all core-only, deterministic, fail-loud), joining the
existing event-study/matching/bootstrap/power/multiple-testing primitives.

### 9.4 D2 confirmation

`alpha research run confirm` (Phase R6, ADR-0026): the one-shot sealed confirmation under the
immutable `ResearchD2BoundaryV1` — approved child confirmation contract, frozen family, frozen
alpha/power/minimum-effect, `REGISTERED CONFIRMATORY` watermark, D2 `authorized → consumed`
(or `contaminated`) events, mechanical classification recomputed by every reader.

## 10. Research Readiness Gate

### 10.1 Edge-validation checklist

Rendered in the decision view and embedded in the gate packet's guided-evidence layer — each
question answered by a typed finding or explicitly `NOT_TESTED`:

1. Does the effect exist? (primary result)
2. Is it large enough to matter? (practical magnitude vs registered minimum effect)
3. Is it stable through time? (temporal stability)
4. Does it exist beyond one small sample? (effective N, subsamples)
5. Does it exist across relevant assets, or only one? (transportability)
6. Is it regime-dependent? (regime decomposition)
7. Does it survive alternative definitions? (parameter neighborhood)
8. Does it survive falsification tests? (placebo/negative controls/nulls)
9. Is it likely a data artifact? (data-quality findings)
10. Is it likely look-ahead or leakage? (future-poison diagnostics)
11. Is there a plausible mechanism? (mechanism finding + claims)
12. Could the magnitude survive realistic costs? (economic-hurdle check, last rung)
13. Do we have enough observations? (power, low_cluster_count)
14. How much uncertainty remains? (intervals, untested work)

### 10.2 Readiness Scorecard

A pure projection over the findings vocabulary — **enumerated states only, no numeric aggregate,
no single "AI confidence score" anywhere**:

| Dimension | States | Derived from |
|---|---|---|
| Hypothesis definition | Complete / Partial / Missing | contract material-field completeness |
| Data quality | Strong / Adequate / Weak / Blocked | dataset refs + quality reports + audit findings |
| Sample adequacy | Strong / Adequate / Weak | power report, effective N, low_cluster_count |
| Effect existence | Supported / Mixed / Unsupported / Not tested | primary-result findings |
| Effect size | Meaningful / Marginal / Negligible / Not tested | practical magnitude vs minimum effect |
| Temporal stability | Strong / Mixed / Weak / Not tested | stability findings |
| Cross-asset stability | Strong / Mixed / Not tested | transportability findings |
| Regime robustness | Strong / Conditional / Weak / Not tested | regime findings |
| Falsification | Passed / Mixed / Failed / Not tested | falsifier findings |
| Mechanism | Plausible / Unclear / Unsupported | mechanism finding + screened claims |
| Literature | Supporting / Mixed / Contradictory / Insufficient | screened claim aggregate |
| Data-mining risk | Low / Medium / High | attempted-vs-registered family ratio + multiplicity results |
| Unresolved questions | count + list | unresolved confounders, untested work, open notes |

Recommendation line (transparent, rule-derived, shown with its reasons):
`READY FOR STRATEGY RESEARCH` / `MORE RESEARCH REQUIRED` / `REFORMULATE HYPOTHESIS` /
`EVIDENCE DOES NOT SUPPORT CONTINUATION`. Dual implementation — Python (packet/REST) and
`researchScorecardModel.ts` (panel) — pinned to each other by drift-guard fixtures exactly as
`bands.ts` is pinned to `verdict.py`.

## 11. Research-to-Strategy Promotion

- Authority unchanged: promotion is the owner's CLI `alpha research decide … --outcome SUPPORTED
  --disposition advance_to_strategy`, legal only through consumed D2, and
  `create_strategy_version` keeps enforcing the link.
- New at promotion: the store records a `strategy_promotion` context packet containing the
  HypothesisCard, gate-packet reference (id + hash), registered dataset refs, screened literature
  claims, confounder ledger (resolved/unresolved), falsification results, stability findings,
  known failure conditions, assumptions/limitations, headline chart references, negative-attempt
  summary, and open questions.
- `get_agent_brief` (strategy plane) gains a research block: when
  `research_contract_strategy_links` resolves, the brief embeds the promotion packet reference so
  Codex starts strategy work with the complete research inheritance — "given an independently
  researched phenomenon, how can it be converted into a robust executable strategy?"
- DevelopmentCenter renders the carried-forward research artifacts on the promoted project; the
  hypothesis stage of the 14-stage lifecycle links back to the research case.

Strategy development then follows the existing engine path (implementable signal → causal timing
→ entry/exit → risk/sizing → execution assumptions → baseline strategy → backtest → integrity →
robustness → walk-forward/OOS → costs → parameter stability → cross-market/regime → optimisation
→ ML only where incremental), all under the existing gauntlet, holdout, and decision-packet
machinery. ML remains behind the existing isolated-worker boundary and enters only after
baselines and leakage controls exist (existing `ml` stage discipline; the phenomenon-discovery /
feature-research / model-development / strategy-construction / model-validation /
strategy-validation distinctions map to research phases vs the `ml` and validation stages —
there is no "AI Strategy Builder" button anywhere).

## 12. Research Visualisation Matrix

Every visualisation answers a registered question and ships with its numerical table. Charts are
`ResearchChartData` (deterministic Matplotlib, watermark, lineage hashes); tables are typed
projections. Stage column = lifecycle mapping (§1.2).

| Stage | Question | Visualisation | Table | Required data | Result stored | Decision enabled |
|---|---|---|---|---|---|---|
| Data validation | What does the store actually contain, and is it trustworthy? | coverage matrix, gap timeline, quality-flag chart | per-symbol coverage/quality rows | store + receipts + quality.json | data-audit run artifacts | proceed to contract draft / acquire data / block |
| Data validation | What are the raw distributions and regimes? | distribution panels, rolling vol/regime chart, seasonality grid | descriptive-stats table | registered dataset | data-audit artifacts | feasibility of the question |
| Hypothesis | Are events detectable and causally confirmable? | `event_validity` chart (planted + real detections, confirmation timing) | event count/frequency table | dataset + detector spec | D0/D1 run artifacts | approve exploration contract |
| Phenomenon testing | Is there an effect after the event? | `primary_effect`: mean/median forward path + CI bands + matched control | association estimate table (estimate, SE, CI, p, N, effective N) | registered events + outcomes | ResearchGateEvidenceV1 + charts | continue / stop rules |
| Phenomenon testing | Is the effect conditional? | conditional-return charts by quantile/regime/bucket | conditional outcome table | registered features/regimes | D1 artifacts | family results |
| Falsification | Does the effect survive designed refutation? | placebo/negative-control/null distribution charts | falsifier outcome table | registered controls + null draws | D1 artifacts (falsifier findings) | falsification dimension |
| Robustness | Is it stable across time/parameters/assets? | `parameter_stability` surface (phenomenon parameters only), rolling effect size, subperiod comparison, `transportability` panel | stability tables | registered neighborhoods/subsamples | D1 artifacts | robustness dimensions |
| Robustness | Which alternative explanations survive? | `confounders` decomposition chart | confounder resolution table | registered confounder controls | D1 artifacts | mechanism dimension |
| Synthesis | How much selection happened? | `null_multiplicity` chart (family-adjusted results) | Holm-adjusted table | attempt ledger + families | packet multiplicity finding | data-mining-risk dimension |
| Confirmation | Does the frozen claim hold out-of-exploration? | REGISTERED-CONFIRMATORY primary chart | frozen confirmation-check table | sealed D2 | D2 artifacts + classification | research decision |
| Gate | What is the totality of evidence? | headline board (≤6, one per category) | scorecard + checklist | all of the above | ResearchGatePacketV1 | outcome × disposition |
| Literature | What does published evidence say? | evidence-map matrix (supports/contradicts × strength) | claims table | screened claims | claim records | literature dimension |

Inapplicable categories are omitted, never padded. Every chart's underlying series is available
as a table/CSV (the `ChartDataAlternative` pattern) for accessibility and for `chart` context
packets.

## 13. Research Artifact Lineage

Every conclusion is traceable end-to-end through content-addressed identifiers:

```
IDEA          raw_idea, preserved verbatim on the case (uuid5 idempotent capture)
  ↓
HYPOTHESIS    rc_<sha256> contract (parent_contract_id lineage; nothing overwritten)
  ↓
DATA          research_dataset_refs → provenance/receipts/snapshot manifests (sha256 chain)
  ↓
EXPERIMENT    reservation rl_… → attempt ra_… → run_id (v3: config+snapshot+seed+code hash)
  ↓
RESULT        immutable run artifacts + ResearchGateEvidenceV1 (content-hashed selectors)
  ↓
EVIDENCE      typed findings + source claims + attempt ledger (append-only)
  ↓
CONCLUSION    ResearchGatePacketV1 (packet_hash; recomputing readers)
  ↓
STRATEGY      research_contract_strategy_links + strategy_promotion packet (cp_<sha256>)
```

Additional recorded lineage: protocol usage hashes on packets; seeds (semantic derivation;
protocol-frozen where verification requires it); code/dependency/evaluator/environment
fingerprints on contracts (drift blocks launches); Codex packet/note trail per project. The
lineage view in the Evidence Hub decision tab renders this chain for the active case.

## 14. Codex Research Protocol Library

Thirteen reusable protocols, stored in Git at `.agents/skills/alpha-research-protocols/` (one
file per protocol + `protocols.json` index: id, title, purpose, required packet kind, output
contract). Git storage keeps protocol content owner-reviewed and prevents agent self-modification;
the control store records only usage (`protocol_id` + `protocol_content_hash` on each packet).

| Protocol | Purpose | Packet kind | Output contract |
|---|---|---|---|
| `new-idea-intake` | idea → research questions, no trading rules | research_case | tentative claim, mechanism, alternatives, material questions |
| `hypothesis-formalisation` | idea → falsifiable quantitative hypothesis | research_case | draft-ready material answers + card fields |
| `data-discovery` | which existing data answers the question; real gaps | research_case + inventory tools | dataset candidates + gaps |
| `data-audit` | validate required datasets before research | asset/experiment | audit plan → `run data-audit` proposal |
| `literature-review` | find and organise published evidence | research_case | source records + draft claims |
| `mechanism-analysis` | mechanisms, persistence, confounders | research_case | mechanism note + confounder additions |
| `exploratory-analysis` | descriptive design without strategy fitting | research_case | analysis-plan candidates (descriptive) |
| `falsification-design` | tests designed to disprove | research_case | falsifier/negative-control proposals |
| `event-study-design` | causal, time-correct event analysis | experiment | registered event-study spec |
| `robustness-review` | sample/market/regime/definition survival | research_case | sensitivity family proposals |
| `research-critic` | independently attack current evidence | validation | critique note (adversarial-reviewer format) |
| `evidence-synthesis` | established vs speculative | research_case | synthesis note + packet-input review |
| `strategy-promotion-review` | is evidence strong enough to begin strategy work | strategy_promotion | promotion-readiness note vs checklist |

The two existing skills remain: `alpha-research-scientist` (the operating method) and
`alpha-adversarial-reviewer` (the critic's format); protocols are task-shaped entry points into
that method, not replacements. A new idea therefore never starts at an empty prompt: the bench
pairs the case's packet with `new-idea-intake` by default.

## 15. Anti-Premature-Backtesting Controls

1. **Data-model gate (exists).** Research-required projects cannot mint a strategy version
   without the approved confirmation contract + owner promotion decision.
2. **Projection field (new).** Project projections gain `research_gate_state ∈
   {not_required (grandfathered), open, passed, overridden}` derived from governance +
   decision records.
3. **UI gating (new).** StrategyLab, DevelopmentCenter, and the Pipeline panel disable
   strategy-creation/optimisation affordances for `open` projects, showing the reason and the
   research case link instead. Backtest/optim remain available for non-research contexts
   (legacy projects, engine maintenance) — they are staged later, not deleted.
4. **Explicit override (new).** `alpha project override-research-gate PROJECT_ID --actor …
   --reason …` — owner-only CLI, recorded as an append-only project scope event (never a mutable
   boolean). Overridden projects carry `research_gate_state = "overridden"`.
5. **Watermark propagation (new).** Runs launched under an overridden gate carry
   `EXPLORATORY / RESEARCH GATE NOT COMPLETED` in the manifest; RunBrowser rows, run detail,
   and tear sheets render the marker; the Operations desk lists active overrides. Such a run can
   never present itself as validated research.
6. **Default-workflow inversion (new).** The Research Command Center desk plus the New Idea
   action make research capture the primary entry point; strategy construction is reached
   through promotion, not through the front door.

## 16. Phased delivery

Authoritative plans live in `docs/superpowers/plans/2026-08-07-research-first-R{1..6}-*.md`;
ADR-0021…0026 record the decisions. Summary:

| Phase | Name | Scope | Depends on | ADR |
|---|---|---|---|---|
| R1 | Research Command Center desk | read-only case list/evidence-hub/scorecard routes; `alpha research list --json`; desk + ResearchBacklog + EvidenceHub + HypothesisCard; New Idea action | — | 0021 |
| R2 | Codex research desk | context packets + notes tables; protocol library; CLI context/protocol/note commands; +6 MCP tools; CodexBench | R1 | 0022 |
| R3 | Research Data Hub | +5 MCP inventory tools; `data snapshots --json`; dataset registration; `descriptives.py`; `run data-audit`; ResearchDataExplorer; QuantPad adapter sub-slice | R1 (∥ R2/R4) | 0023 |
| R4 | Source plane | claims table + typed columns; isolated acquisition worker; +3 MCP tools; Literature section live | R2 (∥ R3) | 0024 |
| R5 | Pre-strategy experiment engine | analysis-plan contract extension; family modules; durable D1 runner emitting ResearchGateEvidenceV1; Gate-4 real-data lane (QuantPad-qualified; Tiingo-daily fallback) | R2+R3 | 0025 |
| R6 | Confirmation, gate, promotion | D2 runner; checklist + full scorecard; promotion packet + AgentBrief research block; `research_gate_state` gating + override + watermark | R5 | 0026 |

Bounded research ML (`research:ml`, existing Gate 5) is deliberately outside this program's
critical path (optional R7). Each phase lands the full offline Python and frontend gates, updates
the MCP pin and `CLAUDE.md` in the same change, and is independently shippable.

### 16.1 Risks

1. The case-list route reverses a documented Gate-1 absence — read-only, ADR-0021, negative
   tests asserting no mutation verbs.
2. MCP surface grows 48 → ~62 across R2–R4: one conscious pin update per phase, same commit,
   budget table in ADR-0022; approval/decision/D2 tools stay absent forever.
3. The acquisition worker is the only new network surface: isolated, allowlisted, hostile-suite
   gated; R4 never blocks R5.
4. QuantPad retention/licensing may stall the Gate-4 real-data lane: R5 accepts on synthetic +
   planted fixtures first; the qualified-data lane is a separable sub-gate with a
   Tiingo-daily-derived fallback contract.
5. UI scope vs the e2e gate: ≤2 new panels per phase; dormancy and screenshot budgets explicit.
6. R5 concentrates scientific risk: the D1 hard-disable flip is the final commit, after the §17
   acceptance scenarios pass.
7. Scorecard dual implementation can drift: TS↔Python parity fixtures are mandatory.
8. Wizard creep: §1.3 is normative.

## 17. Acceptance scenarios (program level)

Inherited from the 2026-08-06 spec §13 and extended; each phase plan carries its slice:

- A raw sentence becomes a case with wording preserved, no rules asked, ≤1 three-question batch.
- A fresh case renders an all-`NOT_TESTED` scorecard and an honest empty Evidence Hub.
- A planted synthetic pattern is recovered; a planted confounder is rejected; a pure-null family
  stays null after selection accounting; future-poison tests fail any leaking pipeline.
- Kill-and-resume at every phase reproduces identical hashes, budgets, and next actions.
- Budget exhaustion, failed falsifiers, insufficient sample, and no continuation trigger all
  terminate with honest packets rather than more work.
- An agent (MCP or REST) can never approve, decide, consume D2, write `corroborated`, or reach
  paper/orders — negative tests at both surfaces.
- `SUPPORTED` requires consumed D2; promotion requires `SUPPORTED` + owner disposition; the
  promotion packet reaches the strategy AgentBrief byte-identically.
- An overridden gate is visible on the run manifest, RunBrowser, tear sheet, and Operations desk.
- Every context packet ever provided to Codex is retrievable byte-identically in the CodexBench.

## Appendix A — 17-workflow audit

Format per workflow: **Current** state → **Friction** → **Target** → **UI** / **Data** /
**Backend** / **Codex** → **Why better**. Phase tags (R1…R6) mark where the target lands.

**W1 — I have a vague new trading idea. What do I do?**
Current: `alpha research capture` CLI or the palette-only Cockpit's capture box; nothing on any
desk. Friction: entry point invisible; after capture the owner sees one case at a time, no
backlog. Target: New Idea action on the Research Command Center desk; case lands in the backlog
`needs_owner`/`running` buckets with next action visible (R1). UI: New Idea + ResearchBacklog.
Data: existing case records. Backend: `GET /api/research/cases` + `alpha research list --json`.
Codex: intake protocol via `research_case` packet (R2). Why better: the front door is research,
not a strategy form, and no idea can silently vanish.

**W2 — I want Codex to help convert the idea into a research question.**
Current: owner manually pastes context into a Codex session; the six MCP research tools exist but
Codex must rediscover everything. Friction: unstructured context, no record of what Codex saw.
Target: CodexBench pairs the case packet with `new-idea-intake`/`hypothesis-formalisation`;
material answers flow into `research_propose` (R2). UI: CodexBench composer. Data:
`research_context_packets`. Backend: packet build/read tools + `get_research_brief`. Codex:
protocol-guided intake. Why better: structured, recorded, resumable — no re-explaining, no
invisible dumps.

**W3 — Do we already possess the necessary data?**
Current: `alpha data symbols/source-status --json` exist on CLI/REST; MCP has none; the
DataExplorer panel lists symbols only. Friction: Codex literally cannot ask what data exists; the
owner greps. Target: inventory MCP tools + ResearchDataExplorer coverage matrix (R3). UI:
ResearchDataExplorer. Data: store/provenance/snapshots. Backend: 5 MCP tools + snapshots
projection. Codex: `data-discovery` protocol. Why better: data feasibility becomes a triage step
with evidence, not an assumption.

**W4 — Inspect the quality and characteristics of that data.**
Current: `alpha data audit` per receipt (CLI only); quality.json rich but unsurfaced; no
descriptive statistics anywhere. Friction: quality is invisible unless something quarantines.
Target: quality projections + `run data-audit` descriptive runs + explorer views (R3). UI:
explorer quality/gap/distribution views. Data: quality.json + `descriptives.py` artifacts.
Backend: `get_data_quality` + data-audit run class. Codex: `data-audit` protocol. Why better:
"understand the data before forcing it into a strategy" becomes a governed, stored step.

**W5 — Codex finds and organises papers and prior internal research.**
Current: source records/packs exist (CLI-only, metadata-only); no discovery clients; prior
internal evidence searchable via `search_asset_evidence`. Friction: literature is manual
paste-in; no claim structure. Target: acquisition worker + claims + literature MCP tools (R4).
UI: Literature section evidence map. Data: source records + claims + receipts. Backend: worker +
3 MCP tools. Codex: `literature-review` protocol; drafts claims, owner screens. Why better:
papers become structured evidence with method/limitations/strength, not links in notes.

**W6 — Formalise a falsifiable hypothesis.**
Current: `alpha research draft` builds the full contract (thesis, falsifiers, confounders,
budgets) — already strong. Friction: contract JSON is expert-facing; the standard vocabulary
(null, baseline, DV…) is implicit. Target: HypothesisCard rendering + completeness states (R1).
UI: card in Cockpit + Evidence Hub. Data: existing contract. Backend: card projection. Codex:
`hypothesis-formalisation`. Why better: one owner-readable artifact per hypothesis version;
completeness is visible before approval.

**W7 — Preregister the important tests.**
Current: exploration/confirmation scopes, frozen budgets/families exist; analysis selection is
implicit in the protocol. Friction: no per-hypothesis registered test plan. Target:
`analysis_plan` in the contract; plan visible on the card; off-plan work auto-ledgered as
exploratory (R5). UI: card + experiments tab. Data: contract extension. Backend: draft/validate
plan. Codex: `event-study-design`/`falsification-design`. Why better: exploration vs
confirmation is enforceable per test family, not just per contract scope.

**W8 — Run descriptive analysis WITHOUT creating a strategy.**
Current: impossible outside ad-hoc notebooks; nothing stores results. Friction: descriptive work
either doesn't happen or leaks into strategy code. Target: `run data-audit` (R3) + exploratory
D1 analyses (R5), stored as research artifacts. UI: data + exploration tabs. Data: run
artifacts. Backend: audit run class + D1 runner. Codex: `exploratory-analysis`. Why better:
description precedes hypothesis-specific computation and persists.

**W9 — Run an event study WITHOUT trading rules.**
Current: primitives complete (`event_study.py`) but only the synthetic D0 executes. Friction: no
runner, no real data. Target: registered event-study family through the D1 runner on registered
datasets (R5). UI: primary-effect chart + tables. Data: dataset refs + events. Backend:
`research:event-study` jobs → ResearchGateEvidenceV1. Codex: `event-study-design`. Why better:
the phenomenon is tested as association with purge/matching/clustered uncertainty — no
entries/exits anywhere.

**W10 — Test the hypothesis across regimes.**
Current: no regime machinery in research. Friction: regime claims are vibes. Target: regime
tagging in `descriptives.py` + regime-conditioned families in the plan (R3+R5). UI: robustness
tab + regime charts. Data: regime tags + conditional results. Backend: stability module. Codex:
`robustness-review`. Why better: regime dependence becomes a typed finding feeding the scorecard.

**W11 — Intentionally try to falsify the hypothesis.**
Current: five required falsifiers are declared in every contract — but nothing executes them.
Friction: falsification is a promise, not a result. Target: falsifier families execute in D1;
results land in the falsification tab and the packet's negative-controls finding (R5). UI:
falsification tab. Data: falsifier artifacts. Backend: D1 runner. Codex: `falsification-design`.
Why better: refutation is designed, executed, and stored with the same rigor as support.

**W12 — Codex independently critiques the current evidence.**
Current: the adversarial-reviewer skill exists; no packet, no record. Friction: critiques
evaporate. Target: `validation` packet + `research-critic` protocol + critique notes (R2). UI:
notes stream + mechanism tab. Data: notes. Backend: packet + note tools. Codex: adversarial
format (AR-### findings). Why better: attacks on the evidence are durable, badged commentary the
owner sees at decision time.

**W13 — See everything supporting and contradicting the hypothesis.**
Current: findings exist only inside the terminal packet; contradicting evidence has no dedicated
surface. Friction: synthesis requires reading JSON. Target: Evidence Hub for/against sections
with equal prominence + claims map (R1, filled by R4/R5). UI: Evidence Hub. Data: findings +
claims. Backend: evidence-hub projection. Codex: `evidence-synthesis`. Why better: the totality
of evidence — both signs — is one screen, before any decision.

**W14 — Understand whether the effect is economically meaningful.**
Current: practical-magnitude and economic-hurdle fields exist in the packet schema; nothing
computes them pre-strategy. Friction: significance conflated with meaningfulness. Target:
registered minimum effect + practical-magnitude finding + checklist question 12; cost realism
stays the last rung before promotion (R5/R6). UI: decision tab. Data: packet fields. Backend:
confirmation checks. Codex: `evidence-synthesis`. Why better: statistical significance can never
silently stand in for tradable edge.

**W15 — Decide whether to abandon the idea.**
Current: `alpha research decide` with park/reject exists and persists. Friction: the decision
context (scorecard, checklist, both-sides evidence) isn't assembled anywhere. Target: decision
tab = checklist + scorecard + packet + history; abandonment is a first-class stored outcome
(R1/R6). UI: decision tab. Data: existing decisions. Backend: scorecard projection. Codex:
`research-critic` before deciding. Why better: negative decisions are informed, recorded, and
recallable — rejected ideas teach.

**W16 — Promote successful research into strategy development.**
Current: the CLI gate chain exists (SUPPORTED → advance_to_strategy → create_strategy_version).
Friction: nothing carries the research over; the strategy project starts bare. Target: promotion
packet recorded at decision; DevelopmentCenter renders inheritance (R6). UI: DevelopmentCenter
research block. Data: `strategy_promotion` packet. Backend: packet build at decide. Codex:
`strategy-promotion-review`. Why better: strategy work begins from the evidence, not from
memory.

**W17 — Every important research artifact automatically inherited by the resulting strategy.**
Current: only the contract link row. Friction: manual re-assembly, lossy. Target: AgentBrief
research block resolves the promotion packet (hypothesis card, gate packet, datasets, claims,
falsification results, limitations, open questions) byte-identically (R6). UI: Prepare Codex
task includes it. Data: packet + links. Backend: brief extension. Codex: receives the full
inheritance in its first strategy packet. Why better: the research-to-strategy handoff is
automatic, bounded, and lossless.

## Appendix B — Quality-gate mapping

The redesign is unacceptable if any of the following holds; each row names the binding mechanism.

| Unacceptable if | Mechanism preventing it |
|---|---|
| Default workflow still encourages immediate strategy creation | §15.6 desk inversion; §15.3 UI gating; data-model gate |
| A research project cannot exist independently of a strategy | research cases are standalone; the only join is at promotion (§1.1) |
| Codex is a generic empty chat panel | CodexBench is a packet composer; no chat transport; §0 boundary |
| Codex cannot receive structured project context | context packets + brief/packet MCP tools (§3.2–3.3) |
| No research lineage | §13 content-addressed chain; append-only ledgers |
| Hypotheses silently changed after seeing results | immutable contracts; child-lineage revision; frozen criteria recomputed by readers (§5.2) |
| Supporting stored, contradicting ignored | for/against sections equal prominence; CONTRADICTED findings; contradiction links (§6.2) |
| Papers remain disconnected links | structured sources + claim-level records (§7) |
| Cannot investigate phenomenon without entry/exit rules | D1 research runs have no orders/fills (§9.1); New Idea has no rule inputs (§2.4) |
| Backtesting treated as the first serious test | pre-strategy D1 ladder precedes any strategy object (§9); gate before promotion (§10) |
| Research results not reusable on the same asset | asset evidence search; asset packets; dataset refs; permanent case records (§3.2, §8.2) |
| Cannot tell exploration from confirmation | contract scopes + watermarks + D2 one-shot (§1.4) |
| Cannot tell hypothesis evidence from strategy performance | separate planes, run classes, and markers; research runs barred from strategy surfaces (§1.1, §9.1) |
| Statistical significance auto-treated as tradable edge | checklist Q2/Q12; practical-magnitude + economic-hurdle checks; promotion needs owner disposition (§10–11) |
| ML before simpler evidence and baselines | ML outside program critical path; existing isolated-worker + stage discipline (§11, §16) |
| Negative research results disappear | attempt ledger; park/reject dispositions; terminal packets; W15 (§6.1) |
| A failed hypothesis cannot be archived as rejected | `reject`/`park` dispositions are permanent decision events (§1.2) |
| Strategy development begins without research evidence | promotion packet + AgentBrief research block (§11) |
| Claude designed in as the strategy-development AI | §0 rule 1; no Claude surface exists in the product |
| Codex not the intended AI research collaborator | §0 rule 2; `.codex/config.toml`; responsibility field; ADR-0022 |


