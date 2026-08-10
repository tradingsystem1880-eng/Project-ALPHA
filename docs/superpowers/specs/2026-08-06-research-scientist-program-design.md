# Research Scientist Program — Authoritative Design

**Date:** 2026-08-06
**State:** Gate 0 and the bounded Gate 1/D0 CLI/MCP/REST/Cockpit walking skeleton implemented;
source-network worker, qualified real data, production empirical D1/D2 runners, verified
owner-presence authentication, research ML, and autonomous analytical runtime not implemented
**Authority:** `CLAUDE.md`, ADR-0011, ADR-0014, ADR-0015, ADR-0018, ADR-0019, and ADR-0020

## 1. Outcome and present boundary

Project ALPHA will turn a raw trading observation into a finite, cited, reproducible research case
before it becomes a strategy implementation. The program adds disciplined discovery and research
upstream of the existing 14-stage development lifecycle; it does not replace ALPHA's canonical
engine, validation gauntlet, evidence ledger, final holdout, paper controls, or owner decisions.

The owner-facing promise is:

1. Preserve the owner's original observation.
2. Translate it into a falsifiable thesis and competing explanations.
3. Review credible sources and data feasibility.
4. Freeze a bounded protocol before hypothesis-specific computation.
5. Run causal event studies, controls, registered sensitivities, transportability checks, and
   genuine replications where the setting is defensibly independent.
6. Explain what the evidence means, what it does not establish, and why it may be wrong.
7. Stop at a finite research decision with a scientific outcome and a separate owner disposition.

This document specifies the full target. The initial slice contains the additive control-plane
schema and state machines, deterministic intake preview/dossier projection, pure synthetic research
primitives, fail-closed acquisition validation primitives, a bounded local CLI walking skeleton,
six bounded MCP tools, six bounded REST routes, a registered Research Cockpit, and a deterministic
terminal ResearchGatePacket projection. The REST/Cockpit
slice can capture, read, propose, launch an already approved D0 pilot, read status, and read a
progress report; it cannot list all cases, create source packs, approve, decide, consume D2, or run
deep research. The program does not yet contain a source network/download worker, qualified
real-market dataset, MCP/REST approval/decision/D2 authority, autonomous analytical runner,
generalized intraday adapter, or new strategy authority. No document, skill, synthetic fixture, or
cockpit mockup may be cited as real-market empirical evidence.

### 1.1 The three plan hardening changes

The implementation order is deliberately rebuilt around three failure modes that a feature list
would not solve:

1. **Ideas lacked an enforceable epistemic contract.** Natural-language intake now becomes one
   durable Research Case with exact owner wording, mechanism, prediction, alternatives, falsifiers,
   material definitions, source pack, finite budget, stop rules, and one explicit owner/Codex next
   action. Exit evidence is a state-machine/authority test, not a polished prompt.
2. **Exploration could contaminate confirmation and manufacture significance.** D0/D1/D2/D3 are
   disjoint evidence zones; every event is point-in-time, every adaptive view is ledgered, D2 is
   prospective and one-shot under an immutable boundary/child contract, and D3 is prohibited to
   research. Exit evidence includes future-poison, planted-confounder, overlap, power, multiplicity,
   revision-lineage, and contamination tests.
3. **“Autonomy” lacked a finite operating and teaching model.** Codex may act only inside an
   approved contract and budget, pauses at material owner boundaries, preserves negative attempts,
   resumes from a deterministic delta brief, and explains estimates, uncertainty, caveats, and
   competing explanations through decision-selected charts. Exit evidence is restart/tamper/
   budget/stop-rule/UI acceptance; activity volume and chart count are never success metrics.

These changes make rigor, anti-overfitting, and owner collaboration architectural properties. They
do not make the system profitable, and no later feature may bypass them.

## 2. Non-goals and invariants

- No promise of profit, edge, or loss avoidance.
- No live-capital route and no research-agent paper/order authority.
- No automated final-holdout reveal, paper entry, candidate promotion, or owner impersonation.
- No Google Scholar scraping, paywall bypass, unauthorized document retention, or redistribution.
- No unrestricted AutoML, generated-code execution, dynamic Python over untrusted source material,
  agent-created thresholds after results are visible, or self-approved skill changes.
- No second engine, agent framework, vector truth database, graph database, or embedded LLM provider
  loop. Codex remains the conversational runtime and ALPHA remains analytical authority.
- No relabeling research scratch data as a canonical snapshot, validation run, or paper evidence.
- No change to the daily decision-at-close, next-open-fill convention.

All existing point-in-time, two-clock, deterministic identity, immutable artifact, negative-attempt,
holdout, dependency, license, and thin-surface rules continue to apply.

## 3. The Research Case operating model

`StrategyProject` remains the aggregate. A research case is the upstream owner-facing projection of
that project and its research records, not a second project database.

### 3.1 Phase and execution state

Research phase and process execution are separate fields:

```text
ResearchPhase =
  captured | triage | exploration_review | pilot | deep_research |
  confirmation_review | sealed_confirmation | research_decision | closed

ResearchExecutionState = idle | queued | running | paused | blocked | failed

ResearchOutcome = SUPPORTED | CONTRADICTED | INCONCLUSIVE | INVALID

ResearchDisposition =
  advance_to_strategy | revise | park | reject
```

At the shipped Gate 1 boundary, evidence-free and D0-only closures may be only `INCONCLUSIVE` or
`INVALID`. `CONTRADICTED` requires a lineage-bound typed non-synthetic falsifier or result;
`SUPPORTED` remains a mechanical D2 classification only.

Legal phase flow is:

```text
captured -> triage -> exploration_review -> pilot
pilot -> deep_research | research_decision
deep_research -> confirmation_review | research_decision
confirmation_review -> sealed_confirmation | research_decision
sealed_confirmation -> research_decision
research_decision -> closed
```

`ResearchOutcome` answers what the frozen statistical test found. `ResearchDisposition` records what
the owner chooses to do next. For example, `INCONCLUSIVE` is an outcome, not a fifth disposition; it
usually leads to `revise`, `park`, or `reject`. `revise` returns to `exploration_review` only through
a new immutable exploration-contract lineage. A never-authorized, never-viewed sealed boundary may
be reused by that child; if D2 was already opened, its prior state remains
`consumed` or `contaminated`; revision cannot reseal or reuse those observations. Only
`advance_to_strategy` may make the existing strategy/version/experiment lifecycle ready. It does
not mean validated or paper-ready. A paused or blocked case retains its research phase and exact
resumable checkpoint.

Every active case exposes exactly one `next_action` and one `responsibility` (`codex` or `owner`).
The projection also includes `execution_state`, latest decision-relevant finding, blocker and
recovery action, completed/total milestones, active durable job, last checkpoint, approved and
consumed budgets, and the current contract/source-pack/run hashes.

### 3.2 Capture and triage

Natural-language input is the normal entry point. The original text is immutable. Codex drafts a
name, mechanism, testable claim, competing explanations, tentative event/outcome, falsifier, and
data/source feasibility; the owner is not required to write JSON or pre-formulate a statistical
test.

During triage Codex may, within the active request and available tools:

- check compatible prior evidence, rejected attempts, and duplicate research cases;
- search source metadata and inspect lawfully accessible documents;
- inspect provider coverage and small data previews under existing provider rules;
- estimate whether the requested horizon can produce a meaningful effective sample; and
- record explicit recommended defaults for non-material choices.

Triage performs no parameter sweep, candidate ranking, full backtest, holdout access, paper action,
or strategy implementation.

### 3.3 Evidence topology is not the phase machine

The research phase names above are owner-workflow states. D0–D3 are disjoint evidence zones and are
never phase aliases:

| Zone | Canonical role | Access rule |
|---|---|---|
| D0 | Deterministic synthetic fixtures | Proves detector, timestamp, null, confounder, power, and artifact behavior; makes no real-market claim |
| D1 | Earliest 60% of chronologically ordered eligible date/session/dependency groups by default | Adaptive exploration only; every viewed or attempted family member enters the ledger and every artifact is watermarked `EXPLORATORY` |
| D2 | Next chronological 20% of eligible groups by default | Sealed one-shot research confirmation under an immutable boundary hash; one exact child confirmation contract and explicit owner authorization are required before consumption |
| D3 | Newest chronological 20% of eligible groups by default | Final strategy holdout; research access is prohibited and remains under the existing lifecycle |

The default split is applied to indivisible, chronologically ordered eligible groups, not to
post-event rows, event counts, or already-observed outcomes. A date, session, or registered
dependency group never straddles two zones; integer remainders stay in the newest, most protected
D3 zone. A different allocation is admissible only when it is event-blind, frozen in the
owner-approved exploration contract before any D1 view, and leaves D3 at 20% or more. The shipped
Gate 1 draft path materializes the default 60/20/20 commitment; no empirical runner consumes either
the default or an alternative allocation yet.

The `ResearchD2BoundaryV1` hash binds the chronological group-allocation rule, group memberships,
D2/D3 shares, chart fingerprint, data hash, and event definition. Authorization, consumption, and
contamination events must retain that exact boundary hash; a changed boundary is a new lineage,
never a reseal.

`pilot` first proves the proposed detector and evaluator on D0. Any bounded real-market pilot and
all `deep_research` adaptation use D1 only. At `confirmation_review`, the D1-selected family is
frozen into a child confirmation contract. `sealed_confirmation` may consume D2 exactly once after
owner approval. A supported claim can reach `research_decision` only after D2. A contradiction,
invalidity, insufficient power, stop rule, or rejected confirmation contract may terminate early
with D2 still sealed and an outcome other than `SUPPORTED`. Research never reads D3, including after
a null, failure, revision, or apparently attractive D1 result.

### 3.4 Ask-versus-act contract

Codex asks at most three blocking questions in one batch. Each question includes a recommended
answer and the consequence of that answer. A question is blocking only when it changes one of:

- the primary instrument or economic exposure;
- event confirmation/availability time;
- primary outcome or executable horizon;
- session/timeframe/data authority;
- a legal, paid, credentialed, or retention boundary; or
- the intended meaning of the owner's claim.

Codex does not ask the owner to choose libraries, plot styles, retry ordering, document filenames,
source-search ordering, or other implementation details. Non-material assumptions are visible and
revisable, not hidden.

The ordinary owner checkpoints are:

1. resolve material ambiguity, if any;
2. approve or reject the exploration contract;
3. approve or reject the exact child confirmation contract before D2; and
4. choose the research disposition.

An extra owner checkpoint is required for restricted/paid data, protocol amendment, budget or
search-space expansion, final-holdout access, paper entry, or any execution-related action. Safe
technical failures may retry at most twice inside the frozen protocol and budget.

At Gate 1, **owner-only CLI** means the mutation is deliberately absent from MCP, REST, and the
Cockpit and must be invoked through the trusted local operator boundary with an explicit recorded
actor. The actor string and `human` record are audit semantics, not cryptographic proof of identity
or physical owner presence. Verified owner-presence authentication for unattended or multi-user
operation remains a hard gate; agents must not represent the current local CLI field as that proof.
The generic REST job launcher rejects all governed `research` commands except the separate legacy
`research compare` operation, so it cannot bypass this boundary.

### 3.5 Bounded funnel and stopping

Default ceilings are protocol fields, not targets:

| Pass | Default ceiling | Permitted work |
|---|---|---|
| Triage | 20 minutes; 20 source candidates; five accessible full texts | thesis, competing explanations, source/data feasibility; no sweeps |
| Pilot | one primary specification; eight preregistered sensitivity contrasts | event validity, primary estimate, matched/negative control, initial confounder check |
| Deep research | 40 screened sources; 12 full texts; 64 declared parameter-grid cells; two heavyweight hours; at most two analytical rounds | registered surfaces, regimes, cross-assets, robustness, bounded ML after interpretable baselines |

A second analytical round runs only when the first activates a preregistered continuation trigger:
an unresolved material confounder, unstable parameter neighborhood, contradictory transportability
or genuine-replication evidence, or insufficient precision that the already available data can
realistically resolve.

Research stops with a packet when any of these is true:

- data authority or effective sample cannot meet the frozen minimum;
- required falsification tests reject the thesis;
- no continuation trigger fires;
- the approved budget is exhausted;
- the next test changes the protocol or search family;
- two safe retries fail; or
- remaining uncertainty cannot be reduced with approved data and methods.

An agent may propose an extension but cannot grant one. A null, rejected, blocked, or inconclusive
case remains useful negative knowledge.

## 4. Records and storage

Gate 1 extends the CLI-owned SQLite control plane additively. Mutable state changes are append-only;
immutable content is content-addressed. Existing v1 projections remain readable.

The initial control-plane records are:

- `ResearchSource` (`rs_<sha256>`): canonical locator, metadata, access mode, optional content hash,
  and project lineage.
- `ResearchSourcePack` (`sp_<sha256>`): frozen search plan, queries, candidates, inclusion/exclusion,
  screened evidence map, and source membership.
- `ResearchContractV1` (`rc_<sha256>`): immutable `exploration` or `confirmation` payload containing
  the raw idea, thesis, protocol, source-pack identity, budgets, evaluator/data/code/environment
  hashes, evidence topology, and confirmation family where applicable. Owner review is a separate
  append-only event and agents cannot approve their own contract.
- `ResearchPhaseEvent`, `ResearchExecutionEvent`, `ResearchD2Event`, and `ResearchDecisionEvent`:
  independent append-only state histories for phase, process health, sealed-data state, scientific
  outcome, and owner disposition. Every D2 state event retains the same immutable
  `ResearchD2BoundaryV1` hash.
- `ResearchAttempt` (`ra_<sha256>`): every completed, failed, pruned, rejected, or interrupted
  source/analysis attempt with configuration fingerprint, budget use, run link, details, and error.
- `ResearchLaunchReservation` (`rl_<sha256>`): an append-only pre-compute D0 slot and fixed-budget
  debit committed atomically with `running`; a separate one-to-one link terminalizes it with a
  completed or failed `ResearchAttempt`. An unlinked crash reservation is never refunded or reused.
- Exact strategy-version and experiment links to the approved confirmation contract. These links do
  not promote or validate the strategy.

Typed empirical chart bundles and the D1/D2 evidence sections of a `ResearchGatePacket` remain work
for later gates. Gate 1 does implement a content-addressed terminal `ResearchGatePacketV1` for D0 or
other early-terminal cases; absent typed D1/D2 evidence, it reports empirical fields as
`NOT_TESTED` and cannot promote a synthetic result. Every packet carries exact contract/run
selectors and remains distinct from the existing post-holdout/paper `DecisionPacket`.

A later source plane will keep permitted full documents and extracted text outside Git in a content-addressed
`data_dir/research/objects/` store. Only open-access, owner-provided, or otherwise explicitly
permitted full text may be stored. Paywalled or uncertain material retains identifiers, allowed
metadata, anchored notes, and links only.

The canonical generated dossier directory is
`data_dir/research/projects/<project_id>/`. A deterministic Research Dossier may be exported for
human review. Generated Markdown is a read-only, tamper-checked projection; immutable control
records and verified run artifacts remain authority and edited dossier text is never accepted as
input.

Schema v2 also records project research governance. Every newly created project requires governed
research, and the public `alpha project create` command automatically captures its research case
and enters triage. A strategy version for such a project cannot omit the approved confirmation
contract and owner `advance_to_strategy` decision. Existing projects created before the 2026-08-06
program launch and discovered during a v1-to-v2 migration are explicitly grandfathered as
`legacy_import`; existing post-launch records become research-required. No normal API can emit
`legacy_import`, even with a backdated timestamp. A pre-existing v1 backup must have the same
logical schema-and-row fingerprint as the live migration source or migration fails closed. The
migrator holds one SQLite writer lock before taking that snapshot and retains it through all
additive DDL and the v2 version commit; a waiting migrator re-reads the version under the lock.

`alpha research capture` preserves the owner text and persists the deterministic intake preview in
one restart-idempotent transaction with the project, governance marker, contract, phase, execution,
and D2 seal; it
is intentionally not approval-ready. After the bounded questions are answered and a source pack is
frozen, `alpha research draft` materializes the complete thesis/protocol, budget, `source_pack_id`,
code-tree/dependency-lock/environment/evaluator/data hashes, and D2 boundary hash into an immutable
approval-ready contract. Owner approval and `alpha research run pilot` complete the local D0 walking
skeleton only for the exact registered `double_bottom` + `second_trough_confirmable` operator.
Its approval fingerprint is the executable `alpha_synthetic_fixture`/`SYNTHETIC_SPY`/UTC equal
60-minute fixture with a 240-minute pattern window and the registered 25 bp outcome. Arbitrary ideas,
literal SPY/ES charts, alternate outcomes, and neckline variants remain explicit unavailable drafts
and cannot borrow that fixture. One artifact-complete v3 run with an ID derived from the frozen
contract, fixture, and execution fingerprint plus a canonical hashed `ResearchD0AcceptanceV1`
artifact is required to leave `pilot`. The artifact contains raw measurements only; admission
mechanically reruns the frozen detector, null, four-observation D1/D2 and D2/D3 boundary-embargo,
and prospective-power criteria instead of trusting producer pass flags. Completed-D0 recovery,
status/dossier, phase, and packet reads repeat that computation and bind the SQLite-stored
acceptance selector to the current manifest. A fresh launch also
recomputes the approved code, dependency-lock, evaluator, and environment fingerprints before
compute. The passing run then moves directly
to owner-owned `research_decision` because D1 is unavailable. D0 cannot carry typed D1/D2 evidence,
enter the generic corroborated-evidence ledger, or substantiate `CONTRADICTED`. Real D1/deep and
D2/confirm runs fail closed as unavailable.

Negative knowledge is a projection across excluded sources, rejected/pruned/failed variants,
contradictory evidence, and closed research packets. It is not a parallel memory store.

## 5. Thesis and protocol contract

Every protocol fixes these fields before pilot computation:

- Original observation and owner goal.
- Primary falsifiable claim and economic/market mechanism.
- Explicit competing explanations and a causal diagram or equivalent dependency map.
- Instrument, venue/exposure, session, timezone, timeframe, and unit of analysis.
- Event definition, confirmation rule, and `available_at` timestamp.
- Primary estimand, outcome, executable entry/measurement time, and horizon.
- Primary sample/universe, same-underlying equivalence checks, correlated-market transportability
  set, and any genuine-replication setting.
- Data provider/schema/version, adjustment policy, knowledge time, and quality limitations.
- Matched control, negative controls, placebo dates/events, and overlapping-event policy.
- Confounders, regimes, macro/calendar states, and exogenous conditioning variables.
- Train/discovery, inner evaluation, and untouched confirmation periods where applicable.
- Primary specification, sensitivity contrasts, parameter grid, and multiplicity family.
- Minimum event/effective sample, uncertainty method, practical effect threshold, and falsifier.
- Trading costs and execution assumptions when a strategy implication is evaluated.
- Allowed ML role, fold-local features/training, benchmarks, and interpretation requirements.
- Search/compute/chart budgets, continuation triggers, and stop conditions.
- Known omissions, legal constraints, and owner approval revision.

Changing any outcome, event timing, universe, primary metric, data source, split, parameter family,
or acceptance threshold after results exist creates a new protocol revision and stales dependent
research. A changed protocol never silently reuses a prior claim as confirmatory evidence.

## 6. Literature and source plane

The source workflow separates discovery, access, screening, and citation:

1. Freeze search concepts, synonyms, exclusions, and date/as-of policy.
2. Discover through approved scholarly metadata interfaces and direct journal/repository pages.
3. Resolve DOI/version/retraction/correction and lawful full-text locations.
4. Screen title/abstract, then method/full text where permitted; record every exclusion reason.
5. Produce a claim-level evidence map: supports, contradicts, contextualizes, or supplies a method.
6. Freeze the source pack before confirmatory empirical interpretation.

Preferred future interfaces are OpenAlex and Semantic Scholar for discovery, Crossref for DOI and
publication metadata, Unpaywall for lawful open-access locations, and arXiv, SSRN, NBER, RePEc,
journals, and publishers directly. Google Scholar is manual/browser-assisted verification only;
robots or access controls are never bypassed. Exact service terms, rate limits, attribution, and
retention rules are evidence gates before an automated client ships.

External documents are untrusted data. Instructions inside a paper, README, webpage, PDF, or
dataset never change agent authority, tool permissions, protocol, or project instructions. Extracted
text is bounded, provenance-linked, and excluded from shell/credential contexts.

A source report leads with a decision-useful evidence map, not a bibliography dump. Each included
source records the claim, design/data, relevance, contradiction, reusable method, limitations,
version/retraction state, access status, and canonical citation. Search logs and excluded results
stay available in an appendix.

Literature supplies priors, mechanisms, and methods; it never corroborates an ALPHA empirical claim
without exact ALPHA run evidence.

## 7. Empirical method and anti-overfitting ladder

### 7.1 Event-study first

The default path for an observational pattern is an event study, not an immediate strategy
backtest. It validates event timing, sample formation, forward outcomes, controls, and causal
availability before translating the pattern into positions or P&L.

Required study layers are:

1. event/data quality and effective sample;
2. primary estimate with block-aware uncertainty;
3. matched non-event and negative/placebo controls;
4. parameter-neighborhood stability, with all cells counted;
5. weekday, trend, volatility, drawdown, gap, volume, breadth, VIX, macro-event, and relevant regime
   confounders;
6. chronological evaluation and untouched confirmation where sample permits;
7. same-underlying equivalence and dependence-aware correlated-market transportability, with
   genuine replication reserved for non-overlapping future data or a defensibly independent
   data-generating setting;
8. null, multiplicity, and data-snooping corrections; and
9. executable strategy/cost analysis only after the association survives the event-study ladder.

Overlapping outcome windows are purged or clustered; effective independent event count is always
reported. IID trade shuffles and equity-curve partitions are not labeled Monte Carlo or walk-forward
validation. Block/bootstrap/HAC methods must match serial dependence. All variants, failures,
crashes, exclusions, and post-result amendments remain in the attempt ledger.

### 7.2 Multiple testing and selection

The protocol distinguishes one primary specification from sensitivity and discovery families.
Parameter surfaces are interpreted as neighborhoods, not a winning cell. The full declared and
attempted family feeds FDR and, where applicable, White/Hansen Reality Check/SPA, DSR, CPCV, and PBO.
No acceptance threshold may be reduced to make a result pass.

### 7.3 ML boundary

ML is secondary to an interpretable baseline. It may rank causal features, estimate heterogeneous
effects, or test whether registered contextual variables add stable OOS information. Every transform,
feature selection, neutralization, training, and calibration step is fold-local. Models refit inside
each training fold and compare against simple linear/tree/rule benchmarks. Feature importance alone
is not a mechanism, and an ML improvement cannot rescue a failed primary thesis without a new
protocol.

Agent-generated feature or code proposals remain reviewable inputs. No agent executes unrestricted
generated code or imports a new model/runtime dependency without the ADR-0011 gate.

## 8. SPY four-hour acceptance case

The first empirical vertical slice is the observation: "the S&P 500 bounces after a double bottom
on the four-hour chart." It is an acceptance case, not a privileged framework rule.

### 8.1 Instrument and bar construction

"S&P 500 on a four-hour chart" is materially ambiguous. There is no silent default. Intake blocks
until the owner chooses exactly one of these contract identifiers:

- `spy_extended_fixed_4h`: SPY extended-hours observations with equal 240-minute duration and an
  explicit session anchor;
- `es_fixed_4h`: separately governed equal 240-minute ES observations with a dated-contract, roll,
  and futures-session policy; or
- `spy_rth_60m_four_hour_window`: equal 60-minute SPY regular-hours bars with a 240-trading-minute
  pattern window, always labeled an RTH proxy rather than a literal four-hour chart.

The unequal open-anchored XNYS construction of a 240-minute bar followed by a 150-minute remainder
is rejected as a sequence of "four-hour" observations. It changes observation duration within the
sample and cannot enter the equal-duration detector. Gate 1 acceptance uses only deterministic
synthetic 60-minute proxy bars, so it proves code behavior and makes no SPY market claim. Real data
for any choice remains Gate 4.

`ResearchBar` records timezone-aware `start`, `end`, and `available_at` plus OHLCV and a
`ResearchDatasetRef` carrying provider, symbol, venue, timeframe, timezone, session, content hash,
and permanent `research_only` scope. A collection rejects mixed duration, overlap, and dataset-ID
mismatch.

### 8.2 Event and outcome

The primary double-bottom detector is causal. A symmetric pivot is not available until its required
right-hand confirmation window has elapsed, so the event timestamp is delayed accordingly. The
second trough's separation, price tolerance, prominence, intervening rebound, confirmation, and
overlap rules are protocol fields. A neckline breakout is a separate variant, not a retrospective
reinterpretation.

Event availability is also owner-frozen as either `second_trough_confirmable` or the distinct later
`neckline_breakout_confirmed` event. The primary endpoint is one owner choice:
`four_trading_hour_return_25bp`, `next_regular_session_return_50bp`, or one exact
`owner_specified_economic_hurdle`. The outcome is measured at a point-in-time executable boundary
relative to matched non-event controls. Other horizons, MFE/MAE, and hit rate are descriptive unless
registered in a multiplicity family. The pilot explicitly tests whether weekday—especially
Tuesday—trend, volatility, VIX, breadth, or prior drawdown accounts for the observed relationship.

SPY and SPX are same-underlying equivalence checks, not independent replications. QQQ, IWM, and DIA
are dependence-aware correlated-market transportability checks when compatible qualified data
exists. Genuine replication is reserved for the unchanged contract on non-overlapping future data
or a defensibly independent data-generating setting. ES is separate because dated contracts, rolls,
overnight sessions, and futures licensing require a different protocol.

### 8.3 Authority ceiling

This case produces research association evidence only. It cannot emit canonical strategy Sharpe,
promotion evidence, a holdout verdict, paper eligibility, or an order. Intraday strategy execution
requires a later ADR and implementation proving receipt-backed provider authority, timestamp/session
correctness, point-in-time snapshots, generalized interval feed semantics, intraday validation
geometry, costs, and paper parity.

QuantPad remains scratch research input under ADR-0018 until its adapter, qualification, and written
retention evidence exist. If no authorized persistent provider is available, the case stops at
source/data feasibility rather than silently substituting data.

## 9. Codex skills and agent-improvement boundary

Codex remains the runtime. Repository skills live below `.agents/skills/` and must read this spec and
`CLAUDE.md` before research work.

The initial skills are:

- `alpha-research-scientist`: intake, triage, protocol drafting, bounded research, explanation, and
  research-decision synthesis.
- `alpha-adversarial-reviewer`: independent attack on mechanism, availability, data, confounding,
  multiplicity, validation, source quality, execution assumptions, and conclusion strength.

Internal work is expressed as three passes—construct, attack, synthesize—not nine user-visible
agents or votes. Specialist methods may be added only when a frozen evaluation demonstrates a
specific gap. Disagreement is recorded as evidence and unresolved findings block the relevant gate.

The strategy-research loop and agent-improvement loop are separate:

- A strategy loop freezes the protocol/evaluator, changes one registered research variant at a time,
  and records keep/reject/fail outcomes.
- An agent-improvement loop freezes a benchmark corpus and scorer, changes one skill/prompt at a
  time, and measures citation accuracy, protocol completeness, leakage/confounder detection, schema
  validity, explanation quality, runtime, and cost.

An agent cannot modify an active skill, approve its own candidate skill, change an evaluation after
seeing candidate scores, or merge a proposed improvement. Candidate skills remain staged until
owner review. Hermes and external agent runtimes are not adopted; a later sandboxed proposal-only
trial requires a measured Codex-skill gap and a separate ADR.

## 10. Research Cockpit and teaching contract

The primary owner view is one Research Cockpit, not seven competing top-level workbenches.

The implemented Gate 1 panel is the deliberately narrow first vertical slice. It is registered in
the Workstation palette and uses generated OpenAPI types for capture, explicit-case read, proposal,
approved synthetic-pilot launch, status, and progress-report calls. It shows the exact thesis,
competing explanations, owner responsibility, native-unit budget rows, D2/D3 firewall, and the
owner-only approval boundary. Global list/backlog orchestration, evidence charts, pause/cancel/
resume controls, sources, and deep/confirmation work remain target behavior, not shipped behavior.

It contains:

- a sticky case header with phase, execution state, health, next action/owner, budget, blocker, and
  pause/cancel/resume actions;
- a conversation/protocol card with the current interpretation, material questions, assumptions,
  and owner checkpoint;
- a bounded evidence board with the findings that determine the disposition; and
- expandable source, lab, chart, attempt, contradiction, and immutable-history details.

The global backlog groups cases as `needs_owner`, `running`, `ready`, `blocked`, and `closed`.
Owner-pinned cases rank first. Remaining ready cases expose a transparent advisory rubric for
falsifiability, data readiness, novelty against prior evidence, and expected information gain per
compute cost. Expected profit never determines priority. One heavyweight case runs at a time.

`Resume with Codex` returns a delta brief: what finished since the last owner visit, what changed,
what remains, and the exact next action. It never asks the owner to restate the thesis.

### 10.1 Chart contract

All preregistered artifacts remain available, but the headline board displays at most six charts:

1. data/event-sample validity;
2. primary effect, uncertainty, and matched control;
3. parameter-neighborhood stability;
4. confounder/regime decomposition;
5. OOS, correlated-market transportability, or genuine replication; and
6. null/multiplicity result.

An inapplicable category is omitted, not filled. Every chart records its protocol question, answer,
sample and uncertainty, caveat, source selectors, hashes, alt text, and why it affects the decision.
Appendix charts are grouped by question. Chart quantity is not a success metric.

### 10.2 Research Gate Packet

The final packet has three layers: a 90-second summary, guided evidence explanation, and technical
appendix. It contains:

- the thesis answer and recommended disposition;
- primary estimate, uncertainty, effective sample, and practical magnitude;
- mechanism status and strongest support/counterevidence;
- resolved and unresolved confounders;
- parameter, chronological, transportability, and genuine-replication stability;
- null, negative-control, and multiplicity results;
- data/source/legal limitations and work not performed;
- what evidence would change the conclusion;
- complete source/variant/attempt/budget lineage; and
- exact links to the headline charts and appendices.

Explanation is layered. The main text teaches the owner what the evidence means without hiding
caveats; selected evidence offers deeper statistical detail. Generated prose never replaces typed
tables or citations, and private chain-of-thought is not exposed.

The Gate 1 CLI now emits `ResearchGatePacketV1` only for a closed case with a human owner decision.
It deterministically selects typed D2 evidence before D1; when neither exists it says
`NO_TYPED_NON_SYNTHETIC_EVIDENCE`, reports empirical fields as `NOT_TESTED`, and preserves the D0-is-
synthetic caveat. It content-addresses the packet and includes bounded source, contract, variant,
attempt, launch-reservation/terminal-link, budget, phase/review/execution/D2/decision, and
immutable-artifact ledgers. This projection
summarizes recorded evidence; it does not create D1/D2 evidence or independently validate a strategy.

## 11. Implementation ownership and surfaces

The initial `alpha_research` package is a pure, deterministic research-only boundary. Its ALPHA
package dependency is `alpha_core`; declared numerical libraries remain subject to ADR-0011 and the
dependency matrix. It currently owns fixed-duration data identity/bars, group-atomic chronological
D1/D2/D3 topology, a causal double-bottom detector, prospective power, confirmation classification, and
immutable chart/artifact payloads. It also owns point-in-time event observations, deterministic
overlap purging and exact pre-event matching, cluster-bootstrap predictive-association estimates,
one frozen Holm secondary family, and byte-stable Matplotlib line-chart rendering with embedded
teaching/lineage metadata. Broader matching, dependence estimators, multiplicity families, and run
orchestration remain later work. The package does not import or compose data, strategy, backtest,
validation, forecast, options, screener, CLI, MCP, or web packages and cannot create strategy,
validation, paper, or execution evidence.

`alpha_cli` remains the sole orchestrator and owns SQLite migrations, source metadata/workspace
storage, D0 research runs, durable jobs, and composition with existing data/backtest/validation packages.
`alpha_web` and `alpha_mcp` receive versioned bounded projections and subprocess CLI actions. They
never query SQLite directly, execute generated Python, expose raw full-text or Parquet payloads, or
gain holdout/paper/order authority.

Owner commands are grouped behind five ordinary actions—capture, approve or reject a contract,
pause/resume, review, and decide—while lower-level source/attempt/run/export commands remain for
audit and recovery. The initial CLI slice provides `capture`, `sources add|screen|freeze`, `draft`,
`approve`, `reject`, `run pilot`, `status`, `report`, `export`, `verify`, `pause`, `resume`, `cancel`,
`decide`, and `revise`; an owner may close an evidence-free or D0-only case only as
`INCONCLUSIVE` or `INVALID` with a non-advance disposition. A pre-D2 `CONTRADICTED` outcome requires
lineage-bound typed non-synthetic evidence.
`run deep` and `run confirm` fail closed because production empirical D1/D2 is hard-disabled. Six
thin MCP tools provide `research_capture`, `research_get`, `research_propose`, `research_launch`,
`research_status`, and `research_report` by subprocess CLI. The same six operations have strict
REST/OpenAPI projections for the registered Cockpit. MCP and REST cannot approve, reject, decide,
consume D2, reveal D3, run deep research, start paper, or construct an order.

## 12. Delivery gates

| Gate | Deliverable and exit condition | Current state |
|---|---|---|
| 0 — Authority | Authoritative spec, ADR-0019/0020, risk/dependency updates, `CLAUDE.md`, repository skills; no unresolved critical contradiction | **Complete in initial slice** |
| 1 — Synthetic case foundation | Additive schema-v2 migration; immutable source packs and exploration/confirmation contracts; independent phase/execution/D2/decision histories; deterministic capture-to-draft/dossier/terminal packet; bounded local CLI D0 pilot; six non-owner MCP tools and matching bounded REST/Cockpit operations; topology, detector, prospective-power, confirmation, and chart primitives | **Implemented CLI/MCP/REST/Cockpit walking skeleton and honest terminal packet; there is no case-list/source-pack UI, deep runner, or real-market run** |
| 2 — Source plane | Approved metadata clients, lawful document resolution/storage, screening, retraction/version checks, immutable source packs, hostile-document tests | **Literature plane shipped (R4, ADR-0024):** the isolated stdlib-only acquisition worker (own lockfile; vendored primitives byte-pinned to `research_acquisition.py`) fetches with manual-redirect re-validation into content-addressed UNTRUSTED_SOURCE objects with tamper-detecting verification and the phase-gating hostile-document suite (incl. verbatim-stored prompt-injection text); typed DOI/year/authors columns, owner-invoked `sources fetch`, and claim-level draft→owner-screened revisions are live |
| 3 — Scientific engine | Broader matched controls, multiplicity and dependence-aware event-study runner, research run family, planted/null/confounder fixtures, and typed empirical Gate Packet sections | **D1 shipped (R5, ADR-0025):** the preregistered analysis-plan runner (`alpha research run deep`) executes event-study/conditional-return/stability/falsification families on the discovery share as governed `research:event-study` jobs, with planted/null/confounder acceptance fixtures and mechanical `ResearchGateEvidenceV1` re-verification. **One-shot D2 shipped (R6d, ADR-0026):** owner `approve confirmation` authorizes the sealed share, the deterministic executor reads it exactly once (protocol-frozen seed-7 weekday-matched cluster bootstrap) under a REGISTERED CONFIRMATORY watermark, one mechanical classifier serves write and every admission/read, INVALID is reachable only through contamination, and the owner decision is bound to the mechanical classification |
| 4 — SPY intraday lane | Receipt-backed qualified research data for one owner-selected chart contract, causal aggregation and double-bottom case, session/DST/equal-duration acceptance | **Tiingo-daily fallback lane shipped (R5):** registered `rd_` datasets load into research bars behind fail-closed origin re-verification and session/equal-duration acceptance, and the D1 executor runs the frozen plan on them end to end; the QuantPad intraday lane stays gated on retention/licensing evidence, and no chart contract has navigated the empirical lifecycle |
| 5 — Bounded autonomy and ML | Durable funnel, continuation/stop enforcement, fold-local bounded ML, skill-evaluation harness, teaching/decision views | Not started |
| 6 — Connected workflow and hardening | Complete versioned REST/Cockpit workflow including backlog, sources, durable D1/D2 work, evidence charts and owner checkpoints; any later owner-gated MCP additions; full offline gates, future-poison suite, restore/tamper/security/license review, end-to-end owner pilot and dual review | **Connected workflow shipped (R1-R6, ADR-0021..0026):** the research desk (backlog · cockpit · hub · data explorer · CodexBench), decision view with the fourteen-question checklist, promotion dossier into the strategy AgentBrief, research-gate state/override with permanent run watermarks, Develop-desk UI gating, and the program acceptance suite (spec-§13/§17 composites in `tests/integration/test_research_program_acceptance.py`) are live behind green full offline Python + frontend gates; the end-to-end owner pilot on a real case, dual security review, and the distribution-blocking license review (R-22) remain open |

No later gate is complete because a document, prompt, UI scaffold, or happy-path demo exists. Each
Gate risk closes only with the specified machine evidence.

> **Extended by** `2026-08-07-research-first-workstation-design.md` (proposed ADR-0021..0026),
> which phases the remaining gates: Gate 2 → phase R4; Gate 3 → phases R5/R6; Gate 4 → phase R5;
> Gate 5 → optional phase R7 (outside that program's critical path); Gate 6 → phases R1/R2/R3/R6.
> That spec also narrows, by ADR-0021 and for read-only projections only, this document's Gate-1
> statement that the REST/Cockpit slice "cannot list all cases." This document remains
> authoritative for Gate 0-1 mechanics, the D0 fixture, and the schema-v2 control plane.

## 13. Acceptance scenarios

The completed program must prove:

- A raw sentence reaches `exploration_review` with its original wording preserved, no manual JSON, and
  no more than one three-question clarification batch.
- Material instrument/outcome/session ambiguity asks; plotting, library, and retry choices do not.
- A process killed at every phase resumes the identical phase, hashes, budget, next action, and job
  lineage without duplicate sources, variants, or runs.
- Budget exhaustion, insufficient sample, pure null, failed falsifier, unavailable data, and no
  continuation trigger terminate with an honest packet rather than launching more work.
- An agent cannot expand scope/budget, approve a protocol, corroborate itself, modify an active
  skill, reveal a holdout, start paper, or construct an order.
- Source deduplication, DOI/version/retraction state, access policy, anchored citations, document
  tamper detection, and malicious document instructions fail safely.
- Future-poisoning later bars, revisions, regimes, features, controls, outcomes, or sources cannot
  alter an earlier as-of result.
- Synthetic data recovers a planted pattern and correctly rejects one explained by a planted
  weekday/regime confounder; pure-null families remain null after selection accounting.
- Event overlap, serial dependence, chronological splits, full family counting, FDR/Reality
  Check/SPA, deterministic seeds, and insufficient-power outcomes behave as declared.
- Intraday tests reject mixed 240/150-minute observations and cover timezone/DST, holiday/early
  close, missing bars, corrections, splits/dividends, halts, anchor choice, and pivot confirmation
  availability for the selected equal-duration contract.
- The headline board never exceeds six charts and every chart traces to a frozen question and exact
  data/run selectors.
- Every active case exposes one owner/Codex next action; every closed case has a ResearchGatePacket;
  no upstream packet is labeled validated strategy, paper, or execution evidence.

Product measures are time to protocol, time to research decision, owner interruption count, time
waiting on owner, budget expansion, restart recovery, terminal-case rate, repeated-question rate,
and source/chart/appendix opens. The pilot targets 100% next-action ownership, 100% terminal packets,
zero silent scope changes, and at most three routine owner interruptions per case. Profitability is
not an implementation acceptance measure.

## 14. External pattern disposition

The two owner-supplied local Beast-Mode reports were reviewed as design inputs:

- `/Users/hunternovotny/Desktop/Beast-Mode/docs/research/deep-research-report-1.md`
- `/Users/hunternovotny/Desktop/Beast-Mode/docs/research/deep-research-report-2.md`

They are not ALPHA evidence and their citations, market claims, thresholds, framework choices, and
performance claims are not inherited. Their pattern disposition is:

| Disposition | Pattern | ALPHA realization |
|---|---|---|
| Retain | Typed role handoffs | Repository skills plus typed Research Case contracts; construct, attack, and synthesize remain separable passes |
| Retain | Adversarial critique | Independent `alpha-adversarial-reviewer` attacks sources, causality, timing, confounding, power, multiplicity, stability, and authority before synthesis |
| Retain | Negative-knowledge ledger | Rejected sources, failed/pruned/interrupted attempts, contradictions, tested variants, and stop reasons remain first-class and appear in terminal lineage |
| Retain | Append-only/versioned conflict and recovery | Immutable contracts/source packs, append-only phase/execution/review/D2/attempt/decision events, explicit contaminated states, and new-lineage revision preserve history instead of rewriting it |
| Retain | Staged walking skeleton and human gates | Gate 1 proves one synthetic end-to-end slice first; human approval remains required for contracts, scope/budget expansion, D2, disposition, holdout, paper, and promotion |
| Reject | LangGraph, vector/graph store, or imported runtime authority | Codex remains the conversational runtime; SQLite control records and immutable ALPHA artifacts remain authority; another runtime/index needs a measured gap and separate ADR |
| Reject | Generated-code execution | Source text and model output are untrusted data; no arbitrary Python, dynamically generated strategy, or source-supplied instruction can execute through research surfaces |
| Reject | Arbitrary universal thresholds or profitability claims | Thresholds must be protocol-specific, prospective, practical, and independently justified; no cited rule or attractive chart proves edge, profit, validation, or paper readiness |
| Reject | Autonomous capital | Research cannot construct orders, reveal the strategy holdout, enter paper, promote a strategy, or route live capital; all remain separately governed human boundaries |

TradingAgents contributes adversarial role separation and typed handoffs; QuantDinger contributes
durable jobs, scoped capability concepts, and factor diagnostics; Vibe-Trading contributes
hypothesis/evidence workflow patterns; AI-Trader and atlas-gic supply cautionary examples around
signal challenges and adaptive keep/revert loops. Karpathy-style autoresearch contributes a frozen
harness, one mutable target, fixed budget, and keep/reject log.

These are architecture references only. No repository is vendored, no upstream backtest or claimed
result becomes ALPHA evidence, and no external execution, memory, or agent framework is adopted.
Any code reuse or runtime dependency requires an exact revision, license/notice review, capability
gap, threat model, deterministic acceptance test, and ADR-0011 approval.
