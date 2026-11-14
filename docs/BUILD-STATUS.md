# Project ALPHA — Build Status (delivery history)

Relocated from `CLAUDE.md` on 2026-08-18; CLAUDE.md keeps only the governing
current-status paragraph, which is maintained there and may be newer than the copy
below. With ADR-0027/0028, that paragraph takes precedence over the dated narratives
below wherever they conflict. Append new delivery records HERE.

## History

Entries dated before 2026-10-01 were rotated verbatim into quarterly archives on 2026-11-13:

- [2026 Q2 (April–June)](build-status/2026-Q2.md)
- [2026 Q3 (July–September)](build-status/2026-Q3.md)

Entries below run in date order, oldest first.

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

## 2026-10-01 — Immutable rule execution in the bounded research controller

The isolated research branch adds embedded canonical rule specifications to `BaselineExecutionPlan`.
Both baseline and validation consume one immutable rule file plus its exact byte hash, and the
collector verifies returned rule identity. Existing named-rule behavior, CASH/long-only policy,
validation defaults and two-operation budget remain unchanged. Invalid or altered inputs fail
before engine execution. Default launch forms omit the new local-file options; existing authorized
generic CLI transport can relay them. No new REST schema, MCP tool or approval authority.

This addresses fixed-rule operator coverage, not agent pressure-turn behavior or whole-agent
information isolation. Historical Claude evidence is unchanged; no new model trial is claimed.
See the [plan](work/archive/2026-10/2026-10-01-immutable-research-rules.md) and
[usage guide](operations/bounded-research-workflow.md). Acceptance is recorded separately in
exact-tree gate and independent-review receipts; combined main/UI integration remains pending.

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
The [proposed program](work/archive/2026-10/2026-10-02-agentic-research-capability-program/02-plan.md)
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
`output/data-hygiene/2026-10-02-retirement-applied-audit.json` (archived to
`docs/archive/data-hygiene-2026-10-02/`; sha256
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
exact-tree full-gate receipt. See the [delivery report](records/2026-10-03-reference-quant-workstation.md)
for architecture, review findings, checks and limitations.

**2026-10-03 scientific workstation correction:** Owner retained the classic top bar but corrected the renderer direction: Qbot's actual Bokeh report and Matplotlib integration are scientific references, beyond panel composition. BokehJS now defaults for market observations, recorded series, histograms and QQ plots; optional Lightweight preserves existing market features. The research report preset combines equity, drawdown, diagnostics and genuine backend figures. Visible project selection supports no-project browsing and clears dependent evidence identity while retaining market/archive views. Native-hourly discovery opens an exact venue/market chooser. No backend endpoint, statistical calculation, artifact or domain authority change. Verification is determined by the current exact-tree aggregate receipt; see the [correction report](records/2026-10-03-scientific-research-workstation.md).

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
[execution plan and remaining roadmap](work/archive/2026-10/2026-10-03-codex-research-runtime.md).
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

[Runbook](operations/codex-investigations.md), [scope and acceptance record](work/archive/2026-10/2026-10-03-codex-comparison-evidence.md). Final-tree full gate and independent review are required before commit. Snapshot provenance is not quality certification or historical-vintage proof; schedule completeness, causality and benchmark suitability remain unverified. Bounded acquisition and existing-contract data qualification remain next. Historical Claude results and concurrent primary UI work were untouched.

**2026-10-04 workstation performance continuation:** Scientific cursor overlays and a frame-budgeted resize queue preserve real series and chart lifetime; market resizing coalesces while retaining the latest logical range. Revised large-series checks require an actual changed-size settled redraw within the original timing limits. All frontend steps passed; a documentation edit invalidated that component receipt. Current aggregate acceptance still requires the exact-tree canonical full receipt. See the correction report for the methodology and evidence.

The following canonical run passed backend and 302 browser tests but failed the scientific p99 limit (35.6 > 34 ms). Two paint frames between relayouts and a correctly settled preflight baseline now pass focused timing checks and 21 viewport regressions; independent scoped review approves them. Current exact-tree full receipt remains mandatory.

### 2026-10-04 — Chart exploration and readability

Scientific charts now expose direct UTC windows, full-returned coverage/null/extrema summaries and expandable native OHLCV cursor data. Recorded tables have shared exact CSV/page counts; sampling is readable while raw provenance remains. Friendly panel/layout labels preserve enums and empty charts guide source selection without a project. No statistical/backend/data/authority changes. Review caught and tests reproduced zero-width date/singleton ranges; fixed with positive-span guards. Focused 359-unit coverage passed; browser/snapshot verification and exact-tree review are recorded in [delivery report](records/2026-10-04-chart-exploration-usability.md). Intermediate scientific/market performance failures remain explicit there. Current frozen-tree canonical full receipt governs aggregate acceptance; historical passes never authorize changed source.

The first chart-exploration canonical tree (`2be915e…`) passed backend and 311 browser tests but failed the scientific slow-frame allowance by one frame; no aggregate receipt. Cursor updates now reuse the existing text node and avoid redundant tooltip/closed-disclosure DOM work. Both unchanged focused performance tests pass, including actual resize settlement. Full acceptance still requires the subsequent frozen-tree canonical receipt; boundary timing headroom remains limited.

The second chart-exploration canonical run passed backend and 311 browser tests but missed optional market p99 (36.1 > 34 ms). Both renderers now share cancellable staggered resizing, and linked ranges deliver one latest-value peer per frame while cursors stay together. Unchanged focused performance passed both p99 at 26.3 ms with real changed/settled canvases; independent scoped review approves. Historical failures and range-convergence latency remain in the delivery report. Current exact-tree full receipt remains mandatory.

The third frozen chart-exploration full run passed backend and 311 browser tests but scientific p99 missed by 1 ms (35 > 34). Axis dispatch now coordinates resizing and linked ranges; cursor transforms avoid redundant geometry writes. Native painting may still overlap. Acceptance remains dependent on the current exact-tree full receipt; failures are retained in the delivery report.

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
[scope and acceptance plan](work/archive/2026-10/2026-10-04-bounded-comparison-acquisition.md).
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

[Plan and acceptance scope](work/archive/2026-10/2026-10-04-workstation-investigations.md),
[operator workflow](operations/codex-investigations.md). Primary checkout's concurrent UI is
untouched; this branch's acceptance does not certify a future combined tree. Codex stays the only
reasoning model; Claude artifacts, research admission and trading authority are unchanged.

**2026-10-05 — Aggregate acceptance recorded for the crypto terminal tree.**
The canonical `gate.py full` passed all six components on the frozen shared tree (stamp tree
`54b7f96e5837f47d…`, HEAD `e54aa7a`, 2026-10-04 13:46 UTC, 969 s). That pass supersedes the
"aggregate receipt pending" and "full gate blocked" statements in the 2026-09-30 through 2026-10-04
records above, which remain as history. The 198-error ruff blocker was the benchmark session's
scratch script; it and the benchmark PDFs are archived outside the repository and `tmp/` is now
ignored. The DefiLlama retirement-audit receipts under `output/data-hygiene/` (now `docs/archive/data-hygiene-2026-10-02/`) are committed so the
sha256 citation above resolves in the repository. Five July research files deleted without record
(`research/*mizerxbt_eth*`, now `docs/archive/research-one-offs/mizerxbt-eth/`) are restored. ADR numbering is corrected before integration: published
ADR-0036 belongs to the DefiLlama family on origin/main, agent-neutral engineering becomes ADR-0037
and local confirmation/terminal archive charts becomes ADR-0038; every reference and the Atlas
were regenerated. Re-verification on 2026-10-05: pytest 4,879 passed, vitest 361 passed, ruff,
format, 13/13 import contracts and semgrep clean. Full archive-wide byte integrity remains an
unclaimed separate inventory. Reconciliation with origin/main follows under
[the clean-and-reconcile plan](work/archive/2026-10/2026-10-05-clean-reconcile-main/02-plan.md).

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
27–35 ms, branch 28–47 ms; medians ~10 ms each). [Plan](work/archive/2026-10/2026-10-07-technical-chart-language.md).

**2026-10-08 — Technical-chart cleanup review correction (unmerged).** PNG exports now composite the DOM calendar, legends, tags and gaps plus the title/OHLC header over the native Bokeh canvases. Original downloads omitted these layers. Download regression and fresh full verification govern acceptance of this correction; the earlier full stamp is invalid after source edits. Opt-in performance limitations remain recorded in the chart plan.

**2026-10-08 — Repository cleanup checkpoint (in progress).** Outstanding chart and weekly-mutation changes are being completed in their existing worktrees. Initial main regular CI passed; nightly mutation cancelled after six hours while preceding checks passed. Independent review reproduced report-validation holes and a chart PNG export omitting DOM calendar/legend layers. The research import contract omitted the patterns prohibition; a failing regression reproduced it and the corrected boundary passes. Current README and architecture guidance is reconciled to source. No final combined gate, merge, hidden-suite acceptance or scheduled-workflow completion is claimed. [Cleanup plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).

**2026-10-08 — Expanded repository and GitHub cleanup (in progress).** Three merged clean worktrees, five merged local branches, three merged remote branches and two superseded stash entries were retired after preserving full history, working-tree patches and byte-verified local state. Six undelivered research checkpoints are consolidated under `backlog/research-runtime` with original tips archived. Obsolete draft PR #52 is closed and preserved under a GitHub archive tag. The missing CASH fee-affordability fix is being ported separately; no unfinished research features are promoted. The prior combined tree passed all six canonical components; the expanded tree requires fresh verification and hidden-suite acceptance remains blocked. [Cleanup plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).

**2026-10-08 — Primary checkout consolidated; final acceptance pending.** The primary integration checkout is the only remaining worktree. Original changed source/workflow paths and the transferred staged Git tree were verified exactly before removing duplicate checkouts. Eight redundant merged/preparation local branches, four obsolete/merged remote branches, six research checkpoint branch names and two superseded stash entries are retired with recovery refs/archives; the unique research lineage remains under `backlog/research-runtime`. GitHub has no open PRs. The recovered CASH affordability fix reproduced seven failures before the port and passes 41 focused tests plus one existing expected failure afterward, including a deliberately leaky bias control. A fresh primary aggregate gate and independent risk review remain required; absent hidden tests continue to block final acceptance, commit and merge. [Cleanup plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).

**2026-10-08 — Exact viewport volume mask and orphan recovery.** The volume renderer now restricts painting to every original bar rectangle intersecting the observation-index viewport, including partial edge bars, while preserving the full native source and colors. Four failing-first geometry tests are covered by 23 passing model tests; seven focused browser tests pass with unchanged screenshots and actual PNG export. An isolated timing run passed at 28.5 ms p99; repeats were 26.3/26.2/43.0 ms, so intermittent timing remains unresolved under unchanged limits. A discovered unregistered worktree folder was retired after byte-verifying an archive of all 181 noncache files; its partial source is preserved, not assumed delivered. Final aggregate and hidden-suite acceptance remain required. [Cleanup plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).

**2026-10-09 — Malformed PIT bar error boundary corrected (unmerged).** Visible malformed bars now raise chained `DataError` with symbol, timestamp and original validation reason instead of leaking Pydantic errors past CLI handlers. Point-in-time filtering remains first; invalid rows are neither dropped nor coerced. Twenty failures were reproduced before the source fix; all 27 focused source/bias/public-seed tests pass, including future exclusion, a deliberately leaky twin, and CLI exit 2 with no run publication. The previous primary tree passed all six canonical components; this changed tree requires fresh aggregate verification and independent review. Hidden-suite acceptance remains UNVERIFIED/BLOCK; no commit, merge or scheduled-workflow deployment is claimed. [Cleanup plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).

**2026-10-09 — Exact volume color views (unmerged).** Post-mask profiling exposed full-source CSS color materialization on every view update. Complementary up/down views now share the full native x/volume source with scalar style colors, retaining previous-close classification, equal-close bars, partial viewport intersections, width, scales, cursor and exports. Three failing-first partition tests are covered by 26 passing model tests; seven focused browser tests pass with unchanged screenshots and PNG export. The new profile recorded zero `_from_css_array` samples, versus about 165.5 ms directly before the change. Profiled/ordinary p99 passed at 27.2/27.3 ms; a fixed three-repeat run passed at 27.2/27.3/27.2 ms against the unchanged 34 ms limit. This evidence improves the previously intermittent timing lane without promising every future machine/run will pass. Fresh final aggregate and independent acceptance remain required; hidden-suite execution stays UNVERIFIED/BLOCK. [Cleanup plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).

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

**2026-10-10 — Preserved feature reconciliation (local, unaccepted).** Recovered intended technical charts, exact PNG layers and volume views, CASH fee-affordability rejection evidence, typed PIT errors and core-only research import hygiene into an isolated checkout. Standing engineering holdout policy and active mutation/maintainability work are excluded. Original index/source bytes remain preserved and unchanged. Focused verification and final aggregate acceptance are pending; no publication or integration is claimed.

**2026-10-10 — Preserved feature focused verification (local).** CASH/PIT/core/artifact/boundary regressions:69 passed. The chart PNG lost its visible outside-window annotation warning and gradient-based volume swatch; two failing browser regressions reproduced both omissions, then eight technical-chart tests passed after sharing the warning text and painting the same three swatch rectangles in DOM/export. Classic/Default screenshots are unchanged. Frontend lint/type/build/unit-coverage and Python import/lint/format checks pass. Packaged SPA rebuilt from this source. Fresh aggregate and independent release acceptance remain pending; no new private-suite exception or standing policy is adopted.

**2026-10-10 — Preserved feature integration corrections (local, unaccepted).** Independent review reproduced a strict chart API response failure for CASH pretrade `execution_rejection` events and a native recorded-series PNG export missing its visible value tag. Backend/OpenAPI/frontend event contracts now include rejection events; an artifact-bound response regression fails before and passes after correction, and all 42 chart API integration tests pass. The native Save export now composites the recorded tag while preserving Save/Copy/Open controls and prompt; its browser regression fails before and passes after repair. Empty export headers retain image dimensions. Independent source review found no remaining issue in those repairs; the pixel placement of the recorded tag is not separately asserted. Type/lint and both lifecycle unit tests pass. Packaged assets are rebuilt. A new exact-tree canonical full run follows these final sources; release acceptance remains blocked by the unchanged absent-private-suite rule. No scoped exception has been extended, no feature committed or published, and the original shared index/source remain byte-identical.

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

**2026-10-11 — Recovered-work scoped delivery authorized.** The owner approved separate
chart/CASH/PIT/hygiene and existing research-runtime PRs/merges after all available checks,
with the [one-time private-suite exception](records/2026-10-11-recovered-work-private-suite-exception.md).
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
under `docs/work/archive/2026-10/2026-10-10-mutation-checkpoints.md` only. Its absence remains
UNVERIFIED; the denied private execution will not be retried. No actual failure, public
check, independent review, hosted mutation completeness or Git protection is waived, and
no private-source access or future exception is granted. The isolated pre-exception tree
passed all six full-gate components; the updated tree requires fresh full verification
and independent review before guarded publication.

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
  [accepted pilot plan](work/archive/2026-10/2026-10-16-context-ownership-and-test-layout-pilot.md)
  retains historical collection parity for 135 module and 5,839 public cases,
  AST/fixture/lifecycle and outcome parity; these are retained receipts, not a new
  rerun here. [PR73](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/73)
  readiness and [PR74](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/74)
  evidence preservation are accepted, with all seven postmerge jobs passing in
  [39082708982](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39082708982)
  and [39088156452](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39088156452).
- **Pending cleanup:** reconcile the reported owner-side handover count of 144 paths
  against the [broader hygiene plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md).
  The item-level handover is unavailable to this inspection; this count is
  not a verified repository inventory. The
  [maintainability plan](work/archive/2026-10/2026-10-10-maintainability-cleanup.md)
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
  [setup plan](work/archive/2026-10/2026-10-15-cloud-setup.md) and
  [owned-process readiness plan](work/archive/2026-10/2026-10-15-cloud-readiness-owned-processes.md)
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
The [audit plan](work/archive/2026-10/2026-10-21-atomic-snapshot-retry.md) records scope and limits.
Final full-gate and exact-tree independent-review outcomes are recorded in separate task receipts;
this entry does not assert those outcomes, private-suite coverage, provider qualification or release
acceptance. No prior missing-suite exemption applies. No commit or publication is part of this work.


The first corrected-tree aggregate attempt passed backend, frontend/browser, literature and Qlib
and passed Atlas tests, then stopped on stale generated Atlas graph/input/unknowns outputs.
Their canonical regeneration is part of this change; the failed attempt remains preserved and is
not aggregate acceptance. Final regenerated-tree results remain in the separate task receipts.

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

**2026-10-23 local candidate — unscheduled ML membership guard:** On main `99f2d472dd4511b446e1198ae80201e7207d089d`, schema versions 1 and 2 could accept `point_in_time` without a membership schedule. This local protective slice rejects that declaration at new export/preparation, retains `current_membership` only with its visible warning, and leaves historical artifacts byte-identical and inspectable with a `declared_unverified` status carried through CLI and web result/evaluation/tear-sheet projections. Existing frozen unscheduled PIT inputs cannot be trained or replayed by ALPHA/Qlib. No promotion gate changed; no schedule-v2 or date-varying model support is claimed. Focused synthetic contract, exporter, CLI, worker and web response tests passed; independent review approved the guard and read-only web projection. The full gate was not run, and this patch is not committed or merged.

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

**Tiingo transport-error redaction (2026-10-24)** — `TiingoAdapter.fetch` converts URL, timeout,
incomplete-read, and OS transport failures into type-only `DataError` messages and suppresses their
exception context for both bounded and unbounded reads. HTTP status errors, response-size limits,
parsing, and adapter result contracts are unchanged. Synthetic offline tests cover both read paths,
oversized responses, normal responses, and response cleanup.

**2026-10-25 local candidate — bounded DefiLlama snapshot query:** On isolated branch
`codex/storage-snapshot-query-audit` from verified commit `e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc`,
added `alpha crypto-data snapshot-query SNAPSHOT_ID` for exactly one `defi_tvl` member. The reader
checks volume UUID, exact snapshot/member identity, manifest and raw lineage, artifact hash, quality,
and schema. It caps normalized Parquet at 32 MiB, the raw receipt at 8 MiB, accepted input at 50,000
rows, and each page at 1,000 rows; `has_more` and `next_offset` make continuation explicit. A
50,001st row is only a rejection sentinel. Fixed-width selected columns contribute about 1.2 MB /
1.15 MiB at the accepted row cap before Polars internal buffers; this is a logical materialization
bound, not an OS-enforced decompression or process-RSS ceiling. JSON retains observation and
availability clocks, USD units, artifact/dataset/raw-response hashes, provider schema/parser
versions, and receipt fetch time. `available_at` uses only the parser's next-UTC-day convention;
fetch time is retrieval evidence, every result sets `point_in_time_claim=false`, and no historical
publication time is inferred.

Synthetic focused storage/query/CLI tests passed (39); DefiLlama fixture/acquisition tests passed
(21); public fixture/harness checks passed (14); manual-size tests passed (23). Root Ruff check and
format passed (1,001 files); strict mypy passed across packages/apps/tests (859 files) and harness
scripts (17 files); import contracts kept all 13 rules. Atlas lock/sync, lint/format, package mypy
(23 files), full non-network tests (102 passed, one Starlette deprecation warning), and generated
freshness (8 outputs) passed. Root and Atlas lock/sync, harness lint, plan-check, and `git diff
--check` passed. Independent read-only review approved the byte/row/page bounds and confirmed no
silent truncation or historical point-in-time claim. Changed-files Semgrep passed (198.2 seconds),
and the Semgrep contract check passed. No full gate, DuckDB/dependency change, migration, provider
call, commit, merge, deployment, or publication was performed.

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
See `docs/work/archive/2026-10/2026-10-26-synthetic-native-lifecycle.md` for the bounded implementation.

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
`docs/work/2026-10-26-native-rule-study-boundary/02-plan.md` for the acceptance map.

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
unqualified. See [current plan](work/archive/2026-10/2026-10-26-native-rule-authority.md) for exact
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
[Plan, recipe ledger and evidence route](work/archive/2026-10/2026-10-26-qlib-tabular-wave1.md)
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
is not inherited. See the [W11 packet plan](work/2026-10-26-qlib-w11-refit/02-plan.md)
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
The W05 timezone fix is included once. See the [integration plan](work/archive/2026-10/2026-10-26-w05-research-integration.md)
for code, current checks, source identities, recovery and deferred final gate.

Imported producer behavior notes below describe the reviewed source; their historical tests do not
constitute verification of this successor.

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

Actual Mac qualification is in progress in the isolated successor. The [combined plan](work/2026-10-26-mac-portability-qualification/02-plan.md)
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
receipts and next action are linked by the [Mac qualification plan](work/2026-10-26-mac-portability-qualification/02-plan.md).

### Portable-evidence successor (2026-10-26, in progress)

The isolated 24f checkpoint completed 48/49 canonical commands; only 93% backend coverage failed
(6,298 tests passed, 149 skipped, 2 subtests; 91.6468%). Parent directed a meaningful portable-test
successor after a 363-module/210-function public coverage audit. It targets charged SQL readers,
closure atomicity, independent fixed costed-result validation and immutable artifacts/projections;
it does not emulate Linux or claim that the 761-statement gap is all kernel-dependent. See the
[existing qualification plan](work/2026-10-26-mac-portability-qualification/02-plan.md) and
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
[native rule plan](work/archive/2026-10/2026-10-26-native-rule-authority.md#cloud-qualification-stabilization-2026-10-27)
and the [tabular plan](work/archive/2026-10/2026-10-26-qlib-tabular-wave1.md#cloud-qualification-stabilization-2026-10-27).

Review-scope alignment (same stabilization): review attestation now requires `files_reviewed` to
cover the Git guard's full review scope (risk-tier, protected control plane, hooks and guarded
config), and `/review-gate` uses that scope; see the
[gate preflight plan](work/archive/2026-10/2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27).
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
[gate preflight plan](work/archive/2026-10/2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27)).
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
[gate preflight plan](work/archive/2026-10/2026-10-26-gate-preflight-selection.md#commit-time-gate-and-review-provenance-2026-10-27),
but not yet full-gated or independently reviewed); the
[gate preflight plan](work/archive/2026-10/2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27)
statements that no owner exception or reviewer policy changed are no longer current (an appended
note there corrects them; the original lines are kept); the missing `alpha ml refit-plan`/`refit-status` entries in `.claude/rules/alpha-cli.md`; the open but deferred
[Mac portability successor](work/2026-10-26-mac-portability-qualification/02-plan.md#handoff-and-next-action).
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
[native plan](work/archive/2026-10/2026-10-26-native-rule-authority.md#cloud-foundation-successor-native-and-lease-runtime-findings-2026-10-28).

## 2026-10-28 Foundation batch: pre-run evidence preservation and opt-in cloud bootstrap

Gate entry routes (`run_full`, `run_component`, `run_gate`) now copy existing stamp, receipt,
review/quant attestation and coverage files to a hash-named, verified, mode-read-only checkpoint
before replacing them, once per run, and stop before any overwrite if that copy cannot be verified.
`scripts/cloud_setup.sh` gains opt-in (`ALPHA_CLOUD_FOUNDATION=1`) guard, exclude, pinned RD-Agent,
qualified-venv validation, fontconfig and `origin/main` reporting steps. The native plan carries
the stage contract and ordered foundation backlog. The gate8 checkpoint (tree `fd960490`, public
full gate passed, review BLOCK) is separate; this batch is unqualified. Details:
[native plan](work/archive/2026-10/2026-10-26-native-rule-authority.md#foundation-stage-contract-and-handoff-icm-aligned-alpha-adaptation).

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
[native plan](work/archive/2026-10/2026-10-26-native-rule-authority.md#gate10gate11-repairs-and-retained-diagnostics-2026-10-28).

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
[reconciliation packet](work/archive/2026-10/2026-10-29-pr93-recovery-reconciliation.md) tracks the
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

## 2026-10-29 PR #95 post-merge advisory findings (follow-up)

After PR #95 merged, the advisory Codex review raised two P2 findings in code from the preserved
integration history; both were verified as real:
- `GET /api/ml/exchanges/{id}/evaluation` rejected schema 2 and 3 exchanges: `MlEvaluation`
  allowed only version 1, while `ml evaluate` keeps the request's contract version.
- The owner-selected local PDF import blocked indefinitely on a FIFO before its regular-file
  check could reject it.

Fixes:
- The response model accepts the CLI's supported versions; OpenAPI and the client were regenerated.
- The PDF open uses `O_NONBLOCK`; the regular-file, symlink, size and replacement checks are
  unchanged.

Regressions: every supported evaluation version (parametrized over the CLI's supported set, so a
new CLI version fails until the web contract follows), a bounded FIFO rejection, and a negative
control that an unsupported version is still rejected. Versions 2 and 3 and the FIFO case were red
before the fix; version 1 and the negative control passed before and after.

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
[completion plan](work/archive/2026-10/2026-10-30-software-team-completion.md).

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

The [bounded cleanup/refactor successor](work/archive/2026-10/2026-10-30-project-lineage-projection-refactor.md)
consolidates project-history policy and removes the test-only `changed_paths` wrapper in favor of
`comparison_context`; existing selection and gate semantics are retained. ADR/governance routes
and local receipt references are cleaned up. The prior 12-path checkpoint passed all six public
components/49 steps on `01bf937e`; the expanded successor needs its own final gate and review.
No prior private-suite exception is inherited, and no publication or merge has occurred.

The [existing hygiene plan](work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md#cloud-visible-ledger-reconciliation-2026-10-30)
records the observed cloud branch/path/operation ledger, retained refs and verified move of the
cancelled docs-only predecessor. The saved Mac ledger, physical storage and historical owner-side
counts remain unverified and separately blocked; no unique local data was deleted. This bounded
cloud reconciliation does not declare the broader cleanup/refactor programme complete.

### Cleanup aggregate re-entry findings (2026-10-30)

The expanded `f1550eca` gate stopped at backend pytest: three failures, 6,711 passes, 61 skips,
two passed subtests; coverage met the unchanged floor at 93.01%. Complete failed evidence is
preserved privately by the [cleanup plan](work/archive/2026-10/2026-10-30-project-lineage-projection-refactor.md#aggregate-re-entry-findings-and-bounded-repairs).
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

The [delivery record](work/archive/2026-10/2026-10-30-queryable-context-filesystem.md) maps H26
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
[file-system plan](work/archive/2026-10/2026-10-30-queryable-context-filesystem.md#owner-absence-only-decision--2026-10-30).
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
[existing delivery plan](work/archive/2026-10/2026-10-30-queryable-context-filesystem.md#required-integration-repair-configured-ml-worker-cache)
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

The [single reviewer-policy record](records/2026-11-hidden-suite-exceptions.md#four-workstream-through-delivery-absence-exception--2026-10-30)
records the approved through-delivery absence exception. Private coverage stays UNVERIFIED;
actual checks, exact-tree review and installed Git guards remain mandatory. The owner's repository
delivery instruction authorizes coordinated commits/pushes; this candidate has not merged to main.
Focused combined cleanup checks passed 139 tests and scoped Ruff passed. Atlas regeneration,
fresh context handoff demonstration and final combined-tree gate/review are separate remaining
obligations at this entry; no standalone receipt qualifies this assembled tree. Final receipts
and publication disposition are retained in the exact candidate's ignored evidence directory.

## 2026-10-30 — Recover stranded bounded snapshot query

The existing snapshot-query slice from `4710a00392cc40739f97ed49890a85ac911ec6e0` is
reconciled onto main `f847581f2703f6b5b36aeccdf877c4354a19e176` in an isolated successor.
Original history and main's PR95/96 protections remain intact. Selected member/raw-lineage
verification replaces whole-store payload scanning for this query. Byte ceilings precede payload
hashing; mixed families and unsafe metadata paths fail closed. Availability/fetch-time disclosures
and `point_in_time_claim=false` remain. Stored chain cells are not decoded; the chain label comes
from manifest identity. Generic snapshot verification and admission remain separate.

Inherited checks passed 39 cases; four discriminating regressions failed before correction.
Corrected focused checks passed 45 cases including the availability poison/control. Independent
early review identified repeated unchanged captures with distinct raw receipts; exact retained
`--manifest-id` reopening resolves ambiguity without rewriting the snapshot contract.
[Scope and owner decision](work/archive/2026-10/2026-10-25-crypto-snapshot-query.md#cleanup-recovery--2026-10-30).
Private coverage stays UNVERIFIED under the scoped absence-only exception. Final full/review/CI
acceptance belongs to external exact-tree evidence; no historical receipt is reused.

The first full attempt stopped at backend coverage: 6,716 cases passed, 61 skipped and two
subtests passed, but 92.98% missed the unchanged 93% floor. Added public malformed-input and
lineage regressions address new-reader error paths; no production code or threshold changes.
A fresh complete gate and final independent review are required for this corrected tree.

## 2026-10-30 — Coordinated P2 and snapshot follow-on assembly

A separate integration candidate retains foundation PR97 `d1aa8157`, P2 PR98 `daece223` and
qualified snapshot recovery `6eb4d5df`. The supported ML v1/v2/v3 response and nonblocking PDF
FIFO rejection coexist with foundation UV-cache/ownership/context controls and exact-manifest
snapshot reopening. Production/test bytes are verified against their source commits; shared
reviewer and delivery histories retain all scopes and failures. Derived Atlas output is regenerated
from the complete tree. The combined candidate requires its own exact-tree full gate and
independent review; no prior individual pass accepts this assembly. Private coverage stays
UNVERIFIED under the existing task-scoped absence-only decisions. Main and existing PRs are not
mutated during preparation. See the [follow-on execution record](work/archive/2026-10/2026-10-25-crypto-snapshot-query.md#coordinated-follow-on-assembly--2026-10-30).

## 2026-10-30 — Verified combined delivery on main

[PR99](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/99) normally merged as
`6e451274f57304eeb6f3d4febfacb7eab756974c`. Its main tree
`a37c03cc326ed7d257d25f927466b6fc2cb635bc` exactly matches the qualified combined candidate:
all 49 public gate steps passed, backend coverage was 93.02%, independent review approved,
and the exact-head Codex advisory review completed without findings.
[Post-merge CI](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/41043555388)
completed successfully at 11:10:01 UTC with all seven jobs passing.

This delivers the bounded cleanup/refactor, Software Team workflow, source-bound context
filesystem, retained snapshot query and P2 ML-schema/PDF repairs. PR97 and PR98 are merged
by ancestry. After verifying successor content on main, PR80, PR91, PR92 and PR93 were closed
as superseded; all branch heads and histories remain preserved. Earlier candidate and failure
entries remain historical evidence. Private coverage stays UNVERIFIED under the approved
absence-only exception. Mac-only inventory, physical storage/backup, broader cleanup and
product acceptance gaps remain separately open; this receipt does not mark all features complete.

## 2026-10-31 — Clean RD-Agent bootstrap qualification

The existing foundation backlog's clean-environment and pinned-source acquisition checks now
have executed evidence. `ALPHA_CLOUD_FOUNDATION=1 ALPHA_CLOUD_RDAGENT=1 bash scripts/cloud_setup.sh`
explicitly acquires the fixed RD-Agent Git commit when absent, installs the previously omitted
isolated launcher environment, then creates and validates the existing closed rule/economics
profiles. Default root/browser setup and foundation-only non-fetching behavior stay intact.

A fresh host workspace with empty task caches and a separate digest-pinned Python container
both built from fresh public ALPHA/RD-Agent checkouts without existing project virtualenvs.
Each passed 20 native-loop conformance tests; re-entry retained its two profile identities without
refetching or recreating environments. The container reused locked download caches only and
exited 0 at 02:11:42 UTC. The initial Dockerfile build failed before execution on a read-only
client-state path; direct use of the pinned prebuilt image required no authentication, proxy,
network-policy or protection changes. Detailed commands, pins, profile identities and limits
are in the [bootstrap execution record](work/archive/2026-10/2026-10-31-clean-rdagent-bootstrap.md).

Focused setup regressions passed 26 tests with one host-specific fontconfig skip. Repository
full qualification, independent review and hosted checks remain required for delivery of this
candidate. README remains owned by its separate task. Archive bytes, upstream's whole dependency
API, private coverage and Mac readiness remain UNVERIFIED; provisioning confers no execution,
scientific or product authority. Historical failure and gate records remain preserved.

## 2026-10-31 — Non-destructive checkpoint retention and branch recovery

The existing gate now has an explicit dry-run checkpoint inventory and opt-in verified archive
copy operation. Current/recent receipts, incomplete staging and invalid/symlinked entries remain
excluded; every original remains intact. Archive members are verified against the allowlisted
manifest, and changed sources or conflicting existing archives fail closed. This prepares a
bounded hot-set proposal without pretending total disk retention has been pruned. The
[harness guide](operations/claude-code-harness.md#checkpoint-retention-without-evidence-loss)
contains exact commands and separate-directory restoration instructions.

At observed main `2a8aa50b`, all 56 remote tips are preserved by exact local recovery refs and a
verified Git bundle. The proposed separate-review batch includes 43 ancestor heads and eight
historical delivered slices; five main/backup/active-work heads are excluded. Twenty targeted
source/regression comparisons confirm historical successor preservation. No remote deletion,
main mutation, private-test read or scientific/trading authority follows from this work. Mac-only
state remains unverified. Focused tests cover archive round trips, corruption, source changes,
symlink/path rejection and dry-run exclusions. Final exact-tree qualification and independent
review are required before the guarded commit; private tests remain UNVERIFIED under the
existing task-scoped absence-only approval. See the
[retention plan](work/archive/2026-10/2026-10-31-checkpoint-retention.md).

The first independent review blocked substituted FIFO manifests/archives that could hang the
new inventory. Bounded probes reproduced both failures. The repair rejects nonregular opened
descriptors without blocking and adds bounded real-CLI and archive-copy regressions; the original BLOCK and
its source-bound gate evidence remain preserved. No failing check is waived by private-suite
absence. Publication requires fresh qualification and review of the repaired source.

## 2026-10-31 — README maintenance implementation candidate (not deployed)

Added a bounded plain-English README reader guide and a merge-triggered Codex assessment workflow
candidate. Generated updates are README-section-only, SHA-bound, schema-validated, independently
isolated from delivery credentials, and delivered through the existing full gate/Git guards and
normal docs PR review. Existing CI gains explicit manual dispatch and stale README branch checks;
no application authority or trading behavior changes. Technical setup content remains intact.

Focused fixture tests and qualification results are recorded in the
[feature plan](work/archive/2026-10/2026-10-31-readme-maintenance.md); activation and recovery are in the
[runbook](archive/readme-maintenance.md). The workflow is not active, and no live inference,
hosted trigger or README PR has been demonstrated. No Actions inference credential is available
in this task environment; repository secret availability is unverified. The private review suite is
absent and prior delivery exceptions do not cover this new protected workflow. Full/public checks
and normal independent review are still required; private coverage is UNVERIFIED, not PASS.

## 2026-10-31 — Codex-session README upkeep replaces the API architecture

Hunter's 01:53 UTC instruction supersedes the earlier API workflow candidate. The revision keeps
the reader-friendly guide and moves upkeep into the existing Codex coding task before delivery.
Native `gate.py attest --kind readme` evidence records updated/no-change reasoning and binds the
final branch tree, main comparison and changed scope; installed Git guards require it. It checks
local file links and freshness, not semantic truth, and makes no guarantee over arbitrary pushes.
Existing full, independent-review and quant guards retain their normal authority.

The separate inference workflow/schema/helper/tests, secret dependency and extra CI dispatch/
Actions capability are removed. No new API use, credentials or spending setup is introduced.
Old PR/head/run receipts remain superseded historical evidence. PR102 stays draft for the revised
same-purpose implementation; the existing publication approval and scoped private absence-only
exception cover necessary corrections. Private coverage is UNVERIFIED. Revised focused tests,
exact-tree full qualification and independent review are required before its next guarded commit.
See the [existing plan](work/archive/2026-10/2026-10-31-readme-maintenance.md) and
[worked delivery workflow](archive/readme-maintenance.md).

## 2026-10-31 — Combined foundation follow-on preparation

The coordinated candidate combines retained bootstrap `8051ac33`, checkpoint retention `c260c513`
and native README review `3db13037`. The README source's full branch delta preserves its reader
guide and removes the superseded API scaffolding; `.github` has no net change from main. The
checkpoint inventory/archive and README attestation registries both remain active. A focused
archive regression preserves the new README evidence bytes without restoring them as current
acceptance. Root README now explains the explicit clean-bootstrap mode and non-deleting evidence
commands, while retaining product authority and incomplete-scope boundaries.

Each source's dated evidence and failures remain intact. Final Atlas output, a native README
session decision, one coherent full gate and independent review must accept the assembled tree;
individual source passes are not aggregate acceptance. Original heads remain preserved as
ancestors through normal guarded merges. See the [integration execution record](work/archive/2026-10/2026-10-31-clean-rdagent-bootstrap.md#coordinated-foundation-integration--2026-10-31).
# 2026-10-31 — Packet 3 daily rule prerequisites (unpublished, in progress)

Branch `codex/packet3-real-rule-v1`, base `ab0f6b75c2ff84c1563925721c33c50b1be36965`.
The existing [Packet 3 implementation](work/2026-10-31-packet3-daily-rule/02-plan.md)
adds exact causal source lag, an explicit UTC-day execution clock, a bounded verified Binance
spot daily price query and an inert typed study identity. Existing synthetic plan/launch checks
continue to reject a real study. Full native admission, execution, completion and V1 report are
unfinished; no market research has executed. The canonical W01–W19 scope is preserved.

Independent artificial references cover one-bar chronology, four hand-specified fills/cash,
full1096-day two-page source-to-normalized-to-query lineage and copied-store reopening.
Focused results and final qualification are recorded in the active plan. Cloud intake has no
configured bulk root/UUID and the current identity check is macOS-specific; no guard was bypassed.
Exact costs/sizing/resources await owner confirmation. Private test coverage is UNVERIFIED, with
no new product-task exception assumed. This entry is implementation progress, not delivery.


# 2026-10-31 — Packet 3 native vertical implementation (unpublished; market acceptance open)

The [active Packet3 record](work/2026-10-31-packet3-daily-rule/02-plan.md) now describes the
registered all-D1 daily route, exact owner/query/package/image/guard binding, existing native
reservation/ownership/cancellation, fixed-unit fractional spot execution and observed accounting,
immutable completion, missing-only evidence restore and existing CLI/API/UI report integration.
The full W01–W19 scope remains in its canonical checklist. No new scientific coordinator or
attempt/exposure ledger was added; old synthetic protocol bytes remain separately validated.

Artificial engineering evidence includes independent chronological/cash fixtures, actual pinned
LoopBase/LoopMeta five-stage execution under hard1 GiB physical container memory and oneCPU,
publication interruption/idempotent completion, missing-only reference restore preserving a later
authoritative reservation, cancellation and lost-owner quarantine. A killed host owner left its
container bounded by the original monotonic deadline; no clean outcome or refund was fabricated.
A prior1 GiB address-space probe failed from mapped library footprint and was preserved as a
failed engineering trial; the physical-memory container boundary kept the approved cap unchanged.

Independent review drove fixes for UI lag loss, provider substitution, authority relabeling,
pre-dispatch lost responses, critical approved code/image closure and exact aggregate final-marker
accounting. Portable Docker policy tests retain the unchanged93% coverage floor; focused module
coverage reached100%. Final whole-tree gate/review evidence belongs to the task handoff, not an
earlier prerequisite stamp. Earlier interrupted gates remain interruption history.

Hunter approved the fixed simulation terms and bounded Packet3 absence-only private-suite exception
through delivery (parent-forwarded2026-10-31 06:05UTC). Private coverage remains UNVERIFIED; no
private contents were read or edited. This exception excuses no public failure or authority bypass.

Real-study status: NOT STARTED. No actual dataset was acquired or numerical market study run; no
real-study allowance was consumed. `/workspace` is an observed overlay with unverified hosting retention; the conservative
mounted-root adapter refuses it, but the filesystem type alone does not prove disposability. The
portable contract requires operator-approved durable bulk and control/manifests/run roots on the
same pinned mount/device/owner, plus a hosting/retention decision. None is configured here. Provider
acquisition was not attempted without storage; no provider denial or uncertain download is claimed.
These are native implementation and artificial acceptance proofs, not a market conclusion or
completion of Packet3’s real-data demonstration.

**2026-10-31 — PR105 hosted contract-coverage repair.** The committed native slice passed the local
six-component gate at93.0732% public coverage. Its hosted backend passed7,108 tests with74 runtime
skips but failed the unchanged93% floor at92.38%; the other six hosted jobs passed, and automatic
advisory review reported no findings. Additional public portable tests now target real approval,
reservation, receipt, accounting, dispatch and restoration contracts through explicit artificial
external-runtime ports. They supplement qualified native-process tests; skips and acceptance
limits remain explicit. Production logic, coverage policy and the real-study storage blocker are
unchanged. Final repaired-tree qualification and hosted results are recorded in delivery evidence.

**2026-10-31 — PR105 shared daily root correction.** The portable coverage repair passed all six
local components at93.0664% with CI runtime selection and was published as`ee1635c4`. Automatic
review then identified that a root marker incorrectly pinned the entire data store to its first
daily project. New markers bind only root identity; strict legacy markers remain readable without
rewriting their bytes. Exact project/contract/job admission and same-study exposure guards remain
mandatory. New-launch workspace checks run before queue/job/reservation effects and again before
dispatch. Independent-project and invalid-binding regressions cover this correction. Its final
qualification is separate from the earlier passing repair tree. Real-study allowance remains zero;
Mac availability now permits separate storage inspection, not assumed Linux execution admission.

**2026-10-31 — Daily terminal valuation disclosure.** Default daily-rule comparison cells and plain
CLI summaries now place the last admitted opening quote, actual valuation event and final-decision
timestamps beside final equity. The read-only report projects existing validated policy and raw
clocks; it discloses no forced liquidation and the final decision without a next admitted quote,
without inventing an order. Missing older evidence remains explicitly not recorded. Numerical
artifacts, economics and authority are unchanged. Focused/final qualification and guarded delivery
are recorded in this follow-up's evidence; no real study or Mac access is involved.

## 2026-10-31 — Truthful durable cancellation publication candidate

The durable lease now completes cancellation only after verified child cleanup and a successful
terminal-journal callback. Failed cancellation publication raises a lifecycle error. Workstation
status prioritizes terminal errors over a local cancellation request. Uncertain terminal writes
use bounded `project job-show` readback within the original deadline; a matching recorded status
recovers a lost response. No second terminal transition is attempted. An uncommitted or unreadable
outcome retains durable capacity for reconciliation. Existing physical cleanup protections remain.

Public covering lifecycle/API tests: 92 passed through `scripts/run_owned_test.py`, including
SIGTERM-ignoring descendants, cleanup failure, publication failure before commit, lost response
after commit, readback failure/conflict and bounded actual CLI timeout. The original changed lease
regression failed before the fix. Final aggregate verification and independent review remain
separate delivery evidence; this entry does not assert either. Private coverage is UNVERIFIED
under the recorded task-scoped four-workstream absence-only exception. No real study ran.
See [plan](work/archive/2026-10/2026-10-31-durable-cancellation-publication.md).

### 2026-10-31 — Daily history inspection before Linux storage selection (candidate)

The runtime/storage candidate uses the existing Linux-native `cloud_root_identity` option
instead of adding a Mac/Linux UUID bridge. It adds `ControlStore.daily_rule_history()` and
an explicit-root operator script over one schema-checked read-only snapshot. Metadata
reports whole-store prior daily deep reservations beyond pagination and conservatively
retains unknown routing/unlinked job coverage; it grants no root-change or execution
authority. No schema, allowance, storage backend or actual history was changed.

Focused verification: 37 native fixture tests passed, ruff and mypy passed. Duplicate JSON
routing keys and embedded-NUL/byte-length cases found by independent advisory review were
fixed and covered. Full release verification and final independent approval remain pending;
two unchanged Linux-specific storage cases were unverified on the Mac host. Runtime storage
is not admitted: the source-only Linux probe failed the internal-disk reserve and Docker
denied the separate Expansion read-only bind. No security setting, real study, private
payload, protected test source or permanent cleanup was involved.

Plan: [Linux storage/history preparation](work/archive/2026-10/2026-10-31-linux-storage-history.md).

Candidate correction: fresh independent review reproduced offsets beyond SQLite's signed
integer range escaping as OverflowError. The reader now validates that bound before opening
history; API/script regressions reproduce the former failure and pass with the fix. Corrected
focused verification passed 41 tests; ruff/mypy passed. Earlier 37-test results remain the
previous candidate checkpoint. Full release qualification remains pending.

### 2026-11-01 — Read-only daily-history Linux integration

Integrated the retained reader onto fetched main `fcec79b9` without changing its authored
production semantics. The historical candidate entry above was appended after newer records;
the size-limited manual links existing README cloud/history guidance. Added public missing-DB,
corrupt-DB and live-writer nonmutation regressions; 54 focused history/read-only tests and all
28 Linux cloud-root fixtures passed. The earlier Mac storage limits remain historical evidence.
Final aggregate qualification, independent verdict and hosted results are retained by the
normal gate/review/PR workflow; focused tests alone confer no release or runtime authority.
Private coverage remains UNVERIFIED under the existing bounded absence-only exception. No real
history, Mac access, storage activation, study, allowance, credentials or security changes.

## 2026-11-01 — Fail early on invalid supplied cloud-bootstrap inputs

The existing cloud setup rejects a missing required derived-source setting, wrong supplied
RD-Agent pristine pin or dirty supplied checkout before cache setup, locked installs or Git-guard
changes. Full-bootstrap defaults and exact-pin acquisition remain explicit; acquired bytes are
validated before derived copying. Existing locked valid-source provisioning, foundation/default
non-fetching behavior and interrupted-environment evidence retention remain unchanged.

The seven invalid-input fixture expectations failed before the change; covering offline fixtures
also exercise fetched-source refusal and existing acquisition/re-entry/partial-preservation paths.
README and the operating manual explain early refusal. Final-tree full qualification, independent
review and hosted delivery evidence are separate requirements; this record claims no aggregate pass.
Private coverage remains UNVERIFIED. No live study, allowance consumption, Mac access or trading.
See the [existing bootstrap record](work/archive/2026-10/2026-10-31-clean-rdagent-bootstrap.md#supplied-input-validation-follow-up--2026-11-01).

## 2026-11-01 — Cloud setup public-fixture correction checkpoint

The first corrected-tree full gate failed in backend despite reaching 93.10% public coverage
(7,246 passed, five failed, 74 skipped, one error). Later components did not run. Bounded diagnosis
found a public closure-kill fixture's late safe-barrier cleanup race; a seven-line test-only repair
preserves its original injected failure while reaping the retained child without contaminating a
later test with an unraisable warning. Existing native no-start capture now includes unclaimed
failures, and web cancellation assertions retain bounded failure context. No production lifecycle,
deadline, assertion, coverage or runtime-profile change is included.

Consolidated focused checks: 44 passed, one host-specific skip, one web heartbeat-CLI-timeout
failure; targeted lint/format/types pass. Original aggregate and TMPDIR causes remain bounded
uncertainties, and no focused pass is aggregate acceptance. Reader-first reconciliation, pending
private-suite absence authorization and final-tree full verification remain required. Evidence and
limits are in the [existing bootstrap record](work/archive/2026-10/2026-10-31-clean-rdagent-bootstrap.md#bounded-public-fixture-repair-checkpoint--2026-11-01).

## 2026-11-01 — Narrow heartbeat CLI startup optimization

Measured heartbeat time was dominated by unused research-intake imports before journal entry.
The existing `project create` command now imports its intake function locally; heartbeat/status
paths keep their public behavior without eagerly loading intake/runtime dependencies. The three
new clean-process module-presence regressions failed before this move. Create execution, invalid
idea errors and existing workspace/projection-error behavior remain covered. No lifecycle,
authority, deadline, assertion or coverage policy changed.

The consolidated focused selection passed 62 cases with one host-specific skip using five workers.
Retained baseline/overlay timings are bounded diagnostic evidence, not performance guarantees or
aggregate acceptance. The original full-gate/TMPDIR/supervisor uncertainties remain recorded.
Reader-first base reconciliation, pending private-suite approval, fresh independent review and the
required final-tree full gate remain open. See the [existing bootstrap record](work/archive/2026-10/2026-10-31-clean-rdagent-bootstrap.md#lazy-intake-startup-correction-checkpoint--2026-11-01).

## 2026-11-01 — Cloud workflow correction reconciled after PR108

The bootstrap/lazy-intake/public-fixture candidate is reconciled onto reader main `4e3ca30d`.
Both source histories are retained, the shared manual keeps cloud/history guidance within its
size limit, and generated Atlas reflects the combined tree. Reader production bytes are untouched.
The owner approved the bounded absence-only private-suite exception through necessary corrections
and delivery; private coverage stays UNVERIFIED and all public gates, the unchanged 93% floor,
independent review and normal guarded/hosted delivery requirements remain mandatory.

The environment restart lost prior `/tmp` raw logs. Exact source preservation, surviving workspace
receipts/coverage and transcript-only historical results are explicitly distinguished. Fresh final
qualification evidence is retained under ignored workspace state. This entry records reconciliation
and scope, not a final pass. See the [existing bootstrap record](work/archive/2026-10/2026-10-31-clean-rdagent-bootstrap.md#reader-main-reconciliation-and-bounded-approval--2026-11-01).

### 2026-11-02 — Inert W09 planning identities and blocked readiness

Added CLI-owned typed metadata identities and finite component graphs for existing
v1 LightGBM and v2 fixed-rank recipes, with declared existing-record/input references.
The complete supported first-party worker/schema/project/lock fingerprint detects
stale dependencies; bounded unbuffered source reads reject oversize and mutation.
The existing snapshot helper retains its default behavior for prior callers.
Planning identifiers are not completed operations or fitted-state evidence. Readiness
remains blocked; no native registration, dispatch, ledger or worker computation changes.

Focused preparation passed 42 mocked tests, Ruff, mypy, import contracts and independent
source review; earlier failed preparation evidence is retained. The held patch reapplied
byte-identically after bootstrap merge `babd340e`; shared documentation and Atlas are
reconciled on that base. Exact-tree aggregate and delivery-review receipts are separate
required evidence, not inferred from focused tests. The owner-approved W09 absence-only
exception preserves private coverage UNVERIFIED and all public checks/floors/guards.
Ordinary synthetic engineering qualification is separate from native research execution.
No real-data fit, research allowance consumption, native Qlib admission or Mac operation.

Plan: [W09 planning contracts](work/archive/2026-11/2026-11-01-w09-planning-contracts.md).

### 2026-11-02 — W09 private invocation observations, delivery pending

Prepared opt-in observation hooks for existing v1 LightGBM/v2 fixed-rank worker calls,
using the retained FitTrace/FitInvocation seam. Actual fit state closes before prediction;
failed later calls preserve genuine earlier observations. Fixed assembly is not learning.
V1/v2 serialized outputs/artifact sets and v3/W11 computations remain unchanged.
CLI-owned structural binding joins diagnostic sequences to planned W09 IDs, rejects
request/fold/state/link/dependency drift, and keeps runtime identity unverified and all
admission, fitted-state, durable accounting, reuse and resource authority disabled.

Focused checks passed 64 root tests and 40 covering worker tests (38 mocked/unit plus two
unchanged real synthetic parity cases), including byte-identical
off/on artifacts from ordinary synthetic real-worker fixtures and existing W11 boundary
regressions. Targeted lint/types/import contracts pass; prior red/fixture correction logs
are retained. Atlas is regenerated. These are focused results, not aggregate qualification
or a new coverage claim. No full gate/publication is authorized by the earlier planning-only
private-suite exception; private coverage remains UNVERIFIED pending a new scoped decision.
Independent source review found an output-shape gap; four red-to-green regressions cover
the correction, and independent re-review found no remaining required source changes.
That focused assessment is not formal delivery approval. No native research run, data acquisition, policy,
ControlStore/ledger change, real-data fitting or Mac operation occurred.

Plan: [W09 invocation observations](work/archive/2026-11/2026-11-02-w09-component-observations.md).

### 2026-11-02 — W09 observation delivery approval and qualification boundary

After the prepared observation candidate and its independent source correction were
preserved, the owner explicitly approved this bounded slice's absence-only private-suite
exception and necessary corrections, plus normal guarded commit/push, draft PR, ready
transition and merge of `feat/w09-component-observations` into Project-ALPHA main after
all public checks, the unchanged 93% coverage floor and final independent review pass.
The earlier planning-only exception is not reused. The new reviewer scope record keeps
private coverage UNVERIFIED and every actual public failure, other unrunnable check,
exact-tree review/README/attestation requirement and Git guard blocking as before.

The preserved 13-path candidate patch was independently rechecked against base
`2a6aa175`; its SHA-256 was
`373d3a13c44d0c3f8488d290f73dba993c65ba789f5225e1de2337ca0574f30d`.
This entry records scope and final-tree preparation, not an aggregate pass. Normal gate
and review receipts provide final results. Native research execution, real-data fitting,
resource/retry/refund/reuse policy, durable accounting replacement and Mac activity
remain unauthorized; ordinary synthetic engineering qualification remains permitted.

### 2026-11-02 — Retail research canonical-v3 documentation reconciliation

The canonical checklist owner updated Library version 3 in place (120,666 bytes,
SHA-256 `f9c20abb705daac3b1189bea1d925176034288c6e214cff2a5138a1e9a6d6f33`).
This executor independently resolved its current Library metadata and verified the
supplied authored amendment SHA-256
`b8642ba3474a498c16ab378c85102deae85f26bc4ea6b60a4613f2f11b8120bb`.
DOCX byte/extraction and 58-page visual verification remain parent-supplied; local
materialization was unavailable. The existing mirror now reconciles RR01–RR06 and
source records, with private chat provenance redacted, plus the two under-one-month
TARGET-only schedule corrections. Every other historical body statement and existing
completion status is preserved. All proposed research acceptance fixtures remain NOT RUN.
Software Team qualification stays separate from Product research authority.

Focused text-preservation, source-record, navigation, preflight and diff checks passed;
independent review found no remaining semantic issue. The earlier full gate passed all
six components on the superseded prepared patch and is historical evidence only. The
owner now explicitly approved this docs slice's absence-only private-suite exception
and normal guarded delivery sequence, including necessary corrections. Private coverage
remains UNVERIFIED; full public qualification, the unchanged 93% floor, final independent
review and Git guards still apply. This entry records preparation and authorization,
not a final-tree aggregate pass or merged status; final receipts provide those results.

See the [canonical checklist amendment](context/feature-readiness-checklist-2026-10-27.md#retail-research-refinements-2-november-2026)
and [context index](context/README.md). No strategy or research workflow was activated.

### 2026-11-02 — Backend CI setup deduplication prepared

On main `5da0a965`, the hosted backend job repeated root setup before the canonical
component's lock check and locked sync. Its launcher now uses the stdlib-only,
non-project uv path so the unchanged component owns setup. Other jobs and all quality
commands, failure behavior and the 93% floor remain intact. The focused setup/runner/manual
checks passed 98 cases; this is not a final coverage or hosted speedup claim.
Cold/warm setup, missing-package repair, config/lock drift and real sync failure have
isolated offline fixtures. Final integrated Atlas generation, README attestation, full
qualification and independent review remain pending. Private coverage is UNVERIFIED;
no prior absence exception or publication permission is adopted.

Plan: [Backend CI setup ownership](work/archive/2026-11/2026-11-02-backend-setup-dedup.md).

### 2026-11-04 — Backend setup delivery authorization and reconciliation

The owner approved the bounded backend setup slice, necessary fixes, its own absence-only
private-suite exception and normal guarded delivery. The second integration owner verified
the original six-file patch/hashes before reconciling onto PR112 main `30246d08`; both
appended build entries survive the sole conflict. Application source, accounting, research
activation, worker setup and frontend behavior are untouched. The reviewer scope record
keeps private coverage UNVERIFIED and every real failure blocking. The unchanged full gate,
93% floor, README evidence and exact-final-tree independent review remain mandatory;
their receipts establish acceptance separately from the historical focused checks above.

### 2026-11-04 — W09 durable diagnostic integration and authorization

The bounded worker checkpoint and ControlStore association candidate preserves observed
prefixes in existing job events, with atomic cursor updates, exact scope validation,
idempotent delivery and failed/unknown recovery. It creates no attempt or second ledger
and changes no accounting, native admission, numerical recipe or v3 behavior. Existing
attempt/run references remain unverified. Historical source review independently passed
108 root and 62 worker cases, including crash, lost-acknowledgement and concurrent delivery;
original failed checks remain retained separately. These are not final-tree acceptance.

The owner separately approved this slice, necessary corrections, an absence-only private
exception and normal guarded delivery. Private coverage remains UNVERIFIED. After PR112
and PR113, the original ten-path candidate patch was verified against its retained SHA-256
`5d6ca04e78c39954af0e3efded186bf3239d99fa5b3a7bb3d2c4c18f437b32be`
and integrated without source conflicts onto main `df827032`. Shared README/manual/build
and generated Atlas reconciliation are included. Final exact-tree full public checks,
the unchanged 93% floor, independent review and normal guards remain mandatory; their
receipts establish acceptance separately from this preparation record.

Plan: [W09 durable diagnostic associations](work/archive/2026-11/2026-11-02-w09-durable-observations.md).

# Assistant cleanup candidate — 6 November 2026

The native-upstream documentation aggregate exposed a public watchdog failure: the model
child was still reported as `R` after its inherited lock became available. The repair keeps
the lock holder alive outside the model group and routes caller cancellation through that
watchdog. Group signalling precedes direct-child reap; no destructive signal follows release
of the leader identity. Cleanup waits for group disappearance and can remain blocked if an
OS reaper is unavailable. No model calls, credentials, trading authority or statistical
behavior change. The original failed aggregate and isolated passing diagnostic remain
historical evidence. This is an uncommitted candidate, not delivery or acceptance; the
[plan](work/archive/2026-11/2026-11-06-assistant-cleanup-barrier.md) records verification scope.

## 2026-11-05 offline Bybit funding-page contract (unpublished)

Isolated candidate on main `5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`, tree
`b795de4e9611035aa9c725a2604bf3bcf038f414`: an additive pure funding-page wrapper
binds exact instrument/category, inclusive requested bounds and aware acquisition
cutoff through the existing plan. The legacy parser/frame, raw receipt schemas and
full bounded-page refusal remain. No publication clock, fixed eight-hour cadence,
annualisation, complete-history or provider-qualification claim is added.

Focused synthetic evidence: 143 covering Bybit/backfill/native-acquisition/ingestion/
snapshot-query tests passed; three subsequent compatibility additions brought the
final funding-file selection to 24 passing cases. Ruff check/format, strict mypy
for the three Python files, 13 import contracts and plan validation passed.
Independent source review found no blocking defect. Initial missing-function test
collection and 14 test-helper typing errors were corrected and are recorded in the
scoped plan. No dependencies were installed. The original checkout is unchanged.

Full gate, aggregate coverage and protected-suite qualification are unverified;
no earlier task's private-suite absence exception is reused. No providers, credentials,
real datasets, studies, commits, pushes or external publication were used. Durable
budgets, pagination, raw-page-first retention and restore remain separate work.
Providers remain unqualified and QuantPad remains excluded.

Plan: [Offline Bybit funding page](work/archive/2026-11/2026-11-05-offline-bybit-funding-page.md).

## 2026-11-05 offline funding backward progression (unpublished successor)

The separately preserved single-page candidate has content SHA256
`59abb43c5f8bfed2f66ceecd1d8b10f7fe59fca0adeeb0a1b366aa9acc826aa2`.
This successor remains based on main `5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`.
An offline callback collector reuses its parser, fixes original inclusive bounds,
decreases the page upper bound by one millisecond after the oldest settlement,
and rejects repeated/conflicting/out-of-bound observations. Empty, lower-bound,
call-limit and byte-limit stops all retain `coverage_complete=False`; short pages
continue without assuming a historical funding cadence or publication clock.

Fresh final focused evidence: 145 public synthetic/regression tests passed (38 new
pagination cases, 24 predecessor funding cases and 83 existing Bybit/backfill/native
acquisition cases). Ruff check/format, strict mypy for the two new Python files,
all 13 import contracts, plan and diff checks passed. Independent read-only source
review found no blocking findings. Its two optional tests were added and passed.
Historical predecessor results remain separately labelled in its unchanged workspace.

The collector has no installed transport or CLI route. Callback work/allocation is
outside accepted-byte checks; production transport must enforce byte/deadline limits
and raw retention plus acquisition safeguards before integration. Existing production
full-page refusal, persisted receipts/frames and scientific defaults are unchanged.
No durable quotas/resume/storage, provider qualification or complete-history claim
is added. Full/Atlas/preflight gates, protected contents, provider calls, credentials,
dependencies/installations, commits and publication were not used. QuantPad remains
excluded. Original checkout and predecessor workspace remain unchanged.

Plan: [Offline Bybit funding pagination](work/archive/2026-11/2026-11-05-offline-bybit-funding-pagination.md).

## 2026-11-05 offline raw-first funding retention (unpublished successor)

Preserved predecessors: single-page content
`59abb43c5f8bfed2f66ceecd1d8b10f7fe59fca0adeeb0a1b366aa9acc826aa2` and pagination
content `3437646696187fd43242acf967ed18e2da3f07e258985f64d8792f571fa4e99e`.
The separate raw successor remains based on main `5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`.
An additive raw-only ingestion entry reuses existing staging/receipts/publication and
verification, including already-supported zero-byte evidence. Default ordinary
ingestion still refuses empty bodies. Offline funding composition freezes request
metadata, preflights existing root/reserve, retains exact bounded bodies, and verifies
raw evidence before collector decoding. Malformed/rejected/empty response bodies
remain raw-only evidence; no normalized data, quality acceptance or snapshot follows.

Fresh final focused evidence: 115 tests passed (19 raw-retention, 34 existing ingestion/
storage, 38 pagination, 24 single-page cases). Ruff check/format, strict mypy on three
Python files, all 13 import contracts, plan/diff checks passed. Independent source
review found no blocking findings; its two optional failure tests were added before
the final run. Initial absent-module collection and six test-helper typing errors
were corrected. Historical predecessor results are not fresh receipts for this tree.

Actual temporary filesystem writes, payload fsync, links/replacements, manifest/hash
checks and reopen were exercised; interruption points and UUID/capacity observations
were injected. Production reserves were not lowered. No real retained-root, power-loss
or concurrency qualification is established. Before manifest commit, exact original
inputs are needed to reconstruct receipt/request metadata; existing staged bytes do
not constitute a durable acquisition journal. No live route or production full-page
refusal changed. No quota/resume, snapshot restore, credentials, owner data, provider
calls, dependencies/installations, protected contents, full/Atlas/preflight gates,
commits/push/external publication were used. Coverage and providers remain unqualified;
settlement/publication clocks remain distinct, and QuantPad remains excluded.

Plan: [Offline raw-first funding retention](work/archive/2026-11/2026-11-05-offline-funding-raw-retention.md).

## 2026-11-05 injected bounded funding response reader (unpublished successor)

Preserves raw-retention content
`30a916523d4a6154ce57c452918399e5595cfc58798d3ebd04850ceaa71e8a87` on main
`5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`. An internal supplier requires an
injected urllib-style opener and monotonic clock. Closed funding requests, bounded
chunk/EOF reads, response validation, shared deadline checks and sanitized cleanup
compose with existing raw-first retention. No live opener, command, retry or provider
activation is added; production full-page refusal and persisted contracts remain.

Fresh focused evidence: 188 tests passed (39 transport, 19 raw, 38 pagination, 24 page,
68 existing wire/request-budget/Tiingo cases). Final transport-only rerun passed all
39 after fixture-header typing corrections. Ruff/format, strict mypy on two files,
13 import contracts and plan/diff checks passed. Independent review required fixes
for cancellation leaks and cleanup cancellation handling; both were corrected and
rereviewed without remaining required findings. Historical counts are not disjoint.

Accepted bodies are capped; conforming reads may consume one overflow/EOF probe byte
beyond the allowance. Timeout arguments and between-operation deadline checks do not
preempt blocking arbitrary code or prove actual socket behavior. No hard end-to-end
acquisition deadline, header/socket/RSS cap or power-loss guarantee is claimed. Complete
eligible bodies are raw-retained before decode; partial/invalid transport bodies are
not retained under a fabricated complete receipt. Live no-redirect/timeout qualification,
storage/rights admission and durable acquisition controls remain prerequisites. No
providers, credentials, real data, protected contents, prohibited gates, installs,
commits/push or external publication were used. QuantPad remains excluded.

Plan: [Offline bounded funding reader](work/archive/2026-11/2026-11-05-offline-funding-bounded-reader.md).

## 2026-11-05 integrated offline funding delivery candidate (unpublished)

Converges the existing page validation, backward collection, real raw-first storage
and mandatory-injected bounded response supplier into one reviewable candidate on
`5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`. Exact transport predecessor content
`11bd06fc3bb51ac1e0024e84c7ade68df1b6be31ff3e57bb2359f6938aff8ca6` is preserved
as an allowlisted source snapshot with its historical receipts; prior workspaces and
the original checkout remain unchanged. No additional capability slice was started.

New composed tests cover multi-page full/short/singleton progression with raw-before-
each-decode/reopen, second-page transport/cancellation failure, storage failure after
response cleanup and finite stops preventing another open. Existing tests continue
to cover malformed eligible bodies, incomplete/oversized ineligible bodies and
failure cleanup. Cross-layer review found a mutable-Request URL-binding defect;
the expected URL is now frozen before opener execution and a composed regression
requires rejection/cleanup/no raw publication after mutation.

The integrated patch, explicit allowlist/content inventory, candidate/base identities,
fresh combined focused verification and exact final independent review are separate
local delivery artifacts. Historical helper counts are not added to fresh results.
README now explains the working offline API and its production boundary, including
the owner's QuantPad exclusion; native README/review attestations remain pending.

This is not aggregate/release qualification or live-provider admission. No full,
Atlas/preflight or protected-content checks were executed; no absence exception was
invented. Candidate-local runtime packages and private-suite coverage are unavailable,
installations and publication are outside authorization, and the earlier external
Claude submission remains held. No live opener/command, reserve reduction, new
schema/ledger/quota/resume/restore, credentials, provider/network calls, owner data,
commits, pushes or external publication are added. Production full-page refusal remains.

Handoff: [Integrated offline funding delivery](operations/2026-11-05-offline-funding-delivery.md).

## Funding delivery successor after public component execution

The original funding tree `6ddac25c6578bb4d3d59ae66c584cec260cdea35`, original
receipts and separate inactive F5 successor remain preserved. Standard locked setup
succeeded. Original-tree frontend (including browser/SPA), literature, Qlib and eval
components passed; backend stopped at the 6,000-byte combined-manual guard (6,226),
and Atlas passed tests but found four stale generated outputs. These are historical
original-tree results, not final successor verification.

This delivery successor condenses manual wording without changing functional rules
or funding code, and regenerates Atlas through its supported workflow. The targeted
manual-size check passes at 5,995 combined bytes. Final public/full verification,
independent review and native README evidence must bind the final successor. Private
engineering-suite coverage remains UNVERIFIED. The owner later approved a funding-only
absence decision for the unchanged funding software, conditioned on full public gates
and genuine independent review. Prior BLOCK evidence remains preserved. Integration
onto merged PR #116 retains its assistant-cleanup changes and funding code/test hashes;
only documentation and generated-Atlas overlap is resolved. Final evidence binds that
actual integrated tree. Separate standing direction permits a qualified merge through
normal protections; no live-provider admission, trading or deployment is authorized.

## 2026-11-06 — Native Qlib and Nautilus Results previews (delivery pending)

The existing Results area has read-only views of separately executed synthetic upstream
Qlib 0.9.7 and NautilusTrader 1.228.0 artifacts. The Qlib view displays saved predictions,
constructed targets and diagnostics. The Nautilus view displays native orders/fills/closed
positions and all 31 account-balance events, preserving equal UTC timestamps. These balances
are not mark-to-market equity. Both views expose exact downloads and runtime/configuration
provenance without rerunning an engine, admitting research or mutating owner history.
Root README now includes genuine browser screenshots of both final views.

Scoped UI tests, application types/lint/build, real-backend browser checks and independent
advisory review are recorded in the candidate handoff; these are separate from full-gate
qualification. Delivery remains pending: the required full gate includes protected-source
static scans prohibited in this task and installation stages not authorized here. A GitHub PR
lookup returned Forbidden; it was not retried through another route. No full-gate stamp,
commit, push, PR, empirical performance or live-trading qualification is claimed.


### Follow-up qualification — public prerequisite restored

The earlier setup/protected-source assessment above was too broad. Necessary locked setup
was subsequently authorized and completed in isolated candidate-local environments. The
manual preflight is explicitly listed in `scripts/gate_preflight.py` as a public prerequisite;
its control-plane protection governs edits. The unchanged tracked test was restored from the
base and its required `test_core_is_small` check passed (1 test). Private holdouts remain
absent and UNVERIFIED. No protected fixture, private test or holdout was materialized.

Canonical frontend install, lint, build/types, coverage and API freshness passed; browser
qualification and final gate receipts remain separate. The canonical build refreshed the
committed SPA, and both native views passed fresh isolated real-backend browser checks against
that build. README screenshots were refreshed from those actual captures. Original failures,
scoped successes and predecessor trees remain preserved; no gate requirement was changed.


### Integration onto main after PR #116

The native Results candidate was reconciled in an isolated worktree onto main
`7824bebf2e9d10077e8ffdb92b9b6871ea482287`, preserving main's README changes and chronological
build entries. Authored UI and saved native data applied cleanly. The old-base run is historical:
6,785 tests passed, 1 public manual-rule test failed because its `tests/oracles/**` directory was
absent in that sparse checkout, and 73 tests skipped; coverage was 93.11% against the unchanged
93% floor. No stamp resulted. Ordinary tracked public prerequisites are populated in the
successor; hidden holdouts remain absent and UNVERIFIED. Generated SPA, screenshots, review
and qualification evidence bind the successor independently; old-tree results are not acceptance.


### Reconciliation after funding PR #117

Main advanced to `b94a8ac4b9a8c359a7438b52acefaeb0112527ea` after the UI tree
`acb3cbe48a8995be34e5149524e2338b3260af0d` passed all six local gate components and all
seven PR #118 checks. Those results remain bound to the earlier tree. An isolated successor
starts from funding main and incorporates published UI commit `896b6779d8fa6de574e5a9a08853409ac196258f`
as its second parent, preserving a normal fast-forward publication path. Funding source and
chronological notes are retained unchanged; shared Atlas outputs are regenerated from the
combined public source. Exact successor review and qualification receipts govern delivery.


# Opt-in backtest result card candidate — 6 November 2026

The isolated frontend candidate adds a default-off Backtest result card in Settings. It replaces
the report's summary table only when enabled, showing final server-computed drawdown as a
fraction of running peak equity, UTC Unix seconds and curve observation count. The source
is the existing typed equity endpoint over a v3 backtest's declared equity artifact; run/hash
ownership and invalid/missing evidence produce loading/unavailable states. Nonpositive initial
equity cannot turn the server's sentinel into a meaningful drawdown. No returns, currencies,
uncertainty, STE compliance, factual verification badge or trading authority are synthesized.

Focused verification passed: 25 model/settings tests; 478 frontend tests across 72 files;
coverage 93.23% statements, 83.87% branches, 96.41% functions and 95.13% lines; lint; production
build; five minimum-viewport browser cases. The initial browser fixture/settings-path failure
and initial TypeScript fixture failure are retained separately. Independent source review
approved after its required delayed-response test correction. Full qualification, other browser
projects, Atlas freshness and guarded commit/publication remain pending native UI integration.
No private test content was read; private-suite coverage is UNVERIFIED.

Plan: [backtest result card](work/archive/2026-11/2026-11-06-backtest-result-card.md).

## Backtest card parent-review corrections — 6 November 2026

Parent inspection identified a scope regression in the initial candidate: enabling the card
replaced unrelated run summaries. The revision restricts integration to the backtest family,
keeps unrelated summary and loading-error behavior, and restores the manual's UTC chart,
exact export and no-project browsing requirements. The final observation now shows readable
UTC for years 0000–9999 with explicitly disclosed whole-second display precision; Source keeps
the exact raw Unix seconds. Out-of-range timestamps fail safely. Unavailable states keep the
selected run identity and the artifact hash when known. No statistical formula changed.

Revised focused checks pass: 28 model/settings tests; all 481 frontend tests across 72 files;
unchanged measured coverage percentages; lint and production build; ten minimum-viewport
browser cases, including forecast/validation summaries, load errors, fractional UTC precision,
range rejection and late-response ownership. The earlier bundle/receipts remain historical.
Final-tree independent source review is recorded in the replacement delivery bundle. Integration,
Atlas freshness, the unchanged full gate and guarded publication still follow native UI delivery.

## Backtest card and original native Results integration preparation — 6 November 2026

The card source was overlaid in its own worktree on published PR118 commit
`896b6779d8fa6de574e5a9a08853409ac196258f`. Its tree
`acb3cbe48a8995be34e5149524e2338b3260af0d` exactly matches the supplied original UI candidate
tree; the publication commit metadata differs. The Library archive download failed before local
bytes were produced, so archive SHA verification remains unavailable. No transfer was retried.
The independently fetched repository tree supplied the source baseline. Only the append-only
build history conflicted; both histories were preserved. Native UI source, demo bytes and images
were retained, and SPA/Atlas outputs were regenerated for this isolated combination.

Focused overlay checks passed: 57 card/native-model/settings/shell tests; all 487 frontend tests
across 74 files; lint; production build; API generation/freshness; 12 minimum-viewport card cases
including two native-results coexistence cases; seven existing RunDetail race cases. The browser
shell API is mocked and the native views use packaged saved fixtures: these checks do not rerun
Qlib/Nautilus or establish empirical performance. Native Qlib retains 16 table rows and Nautilus
retains 31 account events while navigating card to native report and back. Independent integration
source review approved without required findings; final candidate identity and receipts are in
the integration handoff. Original failed/stale-tree receipts remain historical.

This is preparation against the original UI tree, not qualification of its funding-reconciled
successor or actual merged head. The UI owner's executor, branch and live gate were untouched.
Full gate, full browser matrix, merged-head README/review bindings and guarded publication remain
pending. Hidden holdout coverage is UNVERIFIED; no private content was inspected.

## Card preparation on qualified PR118 funding/UI head — 6 November 2026

A separate isolated worktree overlays the unchanged card implementation and coexistence tests
on exact PR118 head `d5af71a226419eabb0a9bbb30a8016b585e7ab8e`, verified base tree
`eaf3b458bc753d7970aaa4eb18adbae9650877b7`. The funding implementation, native UI/data and
backend equity-verification seam are unchanged. Existing funding instructions and all delivery
histories are retained. This head is not represented as merged main; the denied UI merge was
not retried. The earlier card preparations and their receipts remain historical.

Successor checks pass: 57 focused card/native/settings/shell cases; all 487 frontend cases
across 74 files; unchanged measured frontend coverage; lint; production build; API freshness;
12 minimum-viewport card/coexistence browser cases and seven existing RunDetail race cases.
Independent source review found no required findings. The browser shell API remains mocked,
using packaged saved native fixtures: no engine rerun, new empirical claim or authority follows.
Final staged-tree review binding and generated-output receipts accompany the replacement bundle.
Full-gate qualification of the actual delivery head and guarded publication remain pending;
qualification of the unmodified base is not acceptance of the overlay. Private coverage is
UNVERIFIED. No merge or external repository write was performed by this preparation.

**2026-11-06 card qualification follow-up — demonstrated runner startup cause:** The two
unchanged-tree full attempts remain failed (7 then 2 backend tests); the separate frontend
component failed one wide chart canvas-readiness assertion. On detached qualified UI baseline
`d5af71a2`, five covered parallel fresh imports of `run_child` loaded unused NumPy, SciPy,
Polars and validation and took 8.98–9.66 seconds before returning, beyond the original five-second
child-readiness window. Localized research-only imports preserve process cleanup, time budgets,
receipt verification and fingerprint algorithms. The new structural boundary test failed on
original source and passed after the change. Five covered parallel revised imports took
0.59–0.77 seconds without those packages. Existing source hashes legitimately change. This
is evidence for the import-before-spawn failure only; the separate half-second child marker
and aggregate browser failure remain under investigation. Final focused results, independent
review and aggregate qualification are pending for this revised tree. No budgets/assertions,
coverage floors, protected test contents or denied merge actions were changed.

The revised runner then passed 71 owned research execution/import-boundary/process-supervisor
cases, Ruff check/format and all 13 import contracts. The original assertions and budgets
remain intact; only the existing rule-specification fixture patch targets its actual validation
module after import localization. These focused passes do not replace the full gate. README
retains the accurate card opt-in and evidence limits; the internal startup fix adds no product
claim. Independent review of the code found no required defect; exact final-tree review and
aggregate qualification remain pending.

**2026-11-07 merged-main card/startup delivery preparation:** UI PR118 is merged on verified
main `8db344908f0530a03ed238c69bd9c1a40bf00afc`, tree
`eaf3b458bc753d7970aaa4eb18adbae9650877b7`, identical to the previous qualified base.
The card and startup fix transferred without a code conflict. Historical candidate tree
`6379c8fbc5a12971d5024fd196b75ea231b130ee` passed all six canonical components on one
stable tree (backend coverage 93.15%, configured 459-case browser matrix); independent review
APPROVE was bound to it. The paired wide comparisons passed 132 baseline and 144 candidate
cases. Unused research analysis imports were localized after a structural red/green regression
and covered startup probes; original process assertions, budgets and hash algorithms remain
unchanged. The original Bokeh delay and separate half-second marker failure causes remain
unresolved and did not reproduce in that successful full gate. No chart code changed.
Current merged-main delivery requires fresh native bindings and applicable qualification;
post-merge CI is not assumed complete. Private-suite status remains UNVERIFIED. The feature
remains default off, reversible in Settings, and carries no empirical or live-trading authority.


<!-- Preserved owner narrative: Qlib048dc0ae; historical claims apply only to that owner candidate, not the combined tree. -->

## 2026-11-07 — Joined native Qlib-to-Nautilus synthetic pipeline (candidate)

Implemented a bounded functional route from upstream qrun's own prediction artifacts to the
existing SignalReplay/native Nautilus harness and a third read-only Results view. It preserves
all 128 native predictions and explicitly consumes 16 SYN00 scores for SYN00.SIM. Session identity,
modeled +23-hour availability and the next synthetic opening quote remain separate. Fixed sizing
is one share, CASH long/flat; declared demonstration fees/slippage are 1/2 bps. The final opening
quote executes the final prediction without a phantom extra decision or invented liquidation.
Existing SignalReplay defaults, independent native previews, canonical stores/history and
admission/accounting policies remain unchanged.

Selected recorder: `18cf75367c094be4831ad653233eb301`. Observed output: 10 orders, 10 fills,
five closed positions and 27 quote/fill cash observations. The measured selected invocation
completed in 7.24 seconds with 421,982,208 bytes peak single-process RSS, below the existing 2 GiB
review ceiling. Six synthetic engineering fit attempts are retained from implementation; model,
seed and dataset stayed fixed, and no global research trial-history audit is claimed. An unavailable
`/usr/bin/time` invocation failed before execution; its receipt is retained separately and the
successful run was measured using standard-library time/resource. No dependency pins changed.

Public checks so far: 16 native backend tests, including future-score poison and its deliberately
leaky control; 11 frontend model tests; scoped Ruff and production mypy; frontend build/types;
real-backend browser checks at 1585/1280 widths. Browser verification matched every portable
artifact hash and the cash CSV button, retained all 16 score links, and rendered both prior demos.
The CSV line-ending regression and two independent-review findings were first reproduced as
failures, then fixed: exporter/base/instrument/fee source bindings and strict next-session/long-flat
consumer checks. Source review and final exact-tree qualification are still being finalized.

The native qrun model/dataset pickles stay producer-local. The display receives inert JSON,
CSV/Parquet and configuration only. This is one frozen LightGBM synthetic integration, not full
Qlib support, a real-data/paper-hypothesis result, scientific acceptance, promotion or live trading.
FitPlan/resource/protected-release policy is not adopted here. The 115 historical broad-run
failures remain unclassified; no opaque mixed diagnostics or hidden holdouts were read. Claude
code review is unavailable in this executor (no connector or desktop tool/capability exposed);
independent Codex source review is retained instead and does not claim Claude qualification.
The existing Qlib CI job also gains the actual bounded native pipeline command after its shared
worker gate; no new adapter matrix or dependency environment is added. Hosted execution of this
new step is pending publication. No commit, external publication, merge or deployment is
established by this entry.

A sixth bounded invocation used this checkout's cached, unchanged locked Qlib environment and
the actual CI command. Native execution passed in 12.60 seconds at 470,388,736 bytes peak
single-process RSS; its predictions are byte-identical to the selected fifth display run. A
supplemental verification wrapper initially looked for counts at the wrong JSON level and
failed after the successful native process. The checked-in CI already uses the correct
`pipeline` nesting; its postconditions then passed against the retained output without refitting.
The public frontend coverage command also passed all 492 tests across 74 files. These local
results do not establish hosted CI, the canonical full gate or private-suite coverage.

## 2026-11-07 — Native bridge complete-public-checkout qualification correction

Preserved the native Qlib-to-Nautilus candidate `7c345fc6d7e792341656904abd0c2f56570a080f`
and prepared an isolated successor on the same `3f7b23185c29b2542605bd41b9485016c2ef3e79`
base. The original sparse Atlas generation had recorded only one root test input;
complete approved public extraction records 541, with no private holdout input.
All 71 protected public source identities are unchanged, and their contents were
not displayed or edited. The native model, synthetic data and executed artifacts
remain unchanged; no additional native fit was performed for this correction.

The owner approved automated public-protected-file processing and the bridge's
absence-only private-suite review exception. Private coverage remains UNVERIFIED.
Fresh successor-bound public qualification, independent review and normal guards
remain mandatory. No full stamp, publication, merge, deployment, real-data acceptance
or trading authority is established by this preparation entry. The dated feature
plan records the bounded scope and preserved evidence.


<!-- Preserved owner narrative: Paper972e621d; historical claims apply only to that owner candidate, not the combined tree. -->

**2026-11-07 isolated paper-to-experiment candidate (focused verification only):** On branch
`codex/paper-to-experiment-20261107` from reconciled main
`3f7b23185c29b2542605bd41b9485016c2ef3e79`, typed `PaperResourceLinkV1` references are frozen
inside the existing content-addressed source pack and bound to a same-project owner-screened claim
revision plus a verified page anchor. Draft/revise accepts explicit mapping proposals to an existing
registered `rd_` dataset and analysis family in the frozen plan; contract approval revalidates the
source-pack identity, mappings, research-only dataset registration, and planned family. D1 records
the validated mapping projection. Code references remain provenance-only because no local code
registry exists; they are not acquired or executed. Missing or unavailable resources remain
`blocked_data`; links do not establish equivalence, acquisition, rights, reproduction, or code execution. An offline
synthetic-paper CLI-to-D1 path passed. Focused source-pack/schema tests passed (179 total), and the
CLI-to-D1 integration test passed (1); changed Python files passed Ruff lint/format and focused
mypy. The canonical aggregate gate disposition is recorded only by the tree-bound harness receipt;
this dated entry does not claim that disposition or empirical/provider validation. No external
resource retrieval, provider request, new dependency, migration, live trade, commit, merge,
deployment, or publication was performed.

### 2026-11-07 — Stock RDLoop continuation candidate (unactivated)

Isolated successor based on main `3f7b23185c29b2542605bd41b9485016c2ef3e79` adds
an actual pinned stock RDLoop diagnostic with deterministic native-interface
components. Existing owner/reservation references bind fixed worker identity and
reserved capacity. Native proposal/coding checkpoint continuation, interruption,
attempt exhaustion and tamper refusal are exercised; typed bounded artifact
validation projects one explicitly synthetic, unaccepted native trace. No custom
research scheduler, new ledger, dispatcher registration, model call or evidence
admission is introduced. Canonical reservation bytes remain unchanged.

Read-only references and same-process fixture counters do not establish durable
cross-process spend protection; reserved CPU is not an enforced CPU cap. Full
native deployment/process ownership, installed dependencies, real backend/model
qualification and full project gates remain unverified. The pre-existing protected
Atlas input restriction remains stopped; no private-suite/full-gate claim is made.
The original preserved candidates, studies, budgets and holdouts are untouched.
See `docs/work/2026-11-07-stock-rdloop-continuation/02-plan.md` and the worker
README for exact contracts and verification evidence.

Focused stock-loop checks: 5 tests and 9 subtests passed, including actual native continuation/interruption and adversarial artifact/request cases; all four changed Python files pass Ruff, the ALPHA module passes focused strict mypy, and 13 import contracts remain kept. Independent Codex source review APPROVE within synthetic-only scope; Claude route unavailable. Full qualification, activation and publication remain blocked/unperformed.

### 2026-11-07 — Retained stock dispatch/accounting successor (unactivated)

Separate successor to reviewed tree `403da80e554efcb36049ae0f0f0568e12e1167bf`
adds one exact closed StockFixtureLaunch identity to the existing internal
synthetic dispatcher. The existing owner retains Popen/lease/process-group cleanup;
canonical owner claims and reservation identity precede payload effects. One
protected `native_invocation` event commits before spawn in existing job_events;
no new ledger, budget reset, refund or history migration. Failure after commit
burns availability. Native starts require consumption; reconnect never respawns.
Strict bounded stock receipt validation binds returned bytes to their validated
hash. All outcomes remain synthetic and scientifically unadmitted.

The older model-allowance prototype remains separate and untouched; its fixed
scope cannot authorize stock dispatch. Current main remains the verified
3f7b2318 base. Original candidate trees are preserved. Live inference, production
activation, runtime dependency qualification, token/USD/CPU enforcement and
protected/full-gate qualification remain unverified. No protected Atlas retry,
new authentication, installation, other-host operation, commit or publication.

Retained stock successor focused checks: 16 tests plus 9 subtests passed, including actual retained-owner stock dispatch and three legacy boundary regressions. Post-insertion rollback, no-remint races, failed Popen, stop-after-commit, parser profile integrity and same-validated-receipt bytes are covered. Strict mypy passes all three touched control modules. Independent source review is scoped to synthetic functionality; final logs/tree binding accompany the handoff. Full qualification remains blocked.

### 2026-11-07 — Scoped automated control-test qualification

Approved automated processing of 65 unchanged control-test inputs enabled the
Atlas refresh for the retained stock-dispatch candidate. Protected source was
neither displayed nor edited, and each approved file matches its original Git
blob. Private holdout remains excluded and unverified. Six additional oracle
package/reference helper files remain outside this approval and excluded. The
three generated Atlas artifacts are refreshed; full acceptance and guarded
delivery remain conditional on the unchanged canonical gate and access scope.

The canonical full gate passed locked dependency validation, setup and manual
preflight, then stopped at 13 I001 import-order diagnostics in unchanged protected
oracle tests. Raw source diagnostics remain undisplayed; no protected tests or
lint configuration were edited. Six excluded oracle support files may affect
import classification; their processing is not covered by the 65-file approval.
No full pass or guarded delivery is claimed from the partial run.

**2026-11-08 isolated original-paper retention successor (focused verification only):** On
`codex/paper-original-pdf-retention-20261108`, based on `3f7b23185c29b2542605bd41b9485016c2ef3e79`
and carrying the separate paper-to-experiment candidate, owner-selected local PDFs are now retained
under `research/literature/source-pdfs/<source_id>.pdf`. The immutable source row's existing
content hash and source identity bind the bytes; no table or schema migration was added. Writes are
bounded to the existing 10 MiB intake limit, use a same-directory no-overwrite link after fsync,
and reads use a pinned directory, reject symlinks/non-regular files, recheck concurrent replacement,
and verify the exact PDF hash before reporting `available` in import or source-screen output.
Owner/project provenance is revalidated;
`missing`, `corrupt`, and `unavailable` remain explicit. Re-import can restore a missing original
from the newly selected local file, but it will not overwrite corrupt bytes. Extracted text keeps
the `UNTRUSTED_SOURCE` boundary and the existing page reader.

The combined synthetic focused selection passed 202 tests across local PDF import, paper resource
links, and research ControlStore. Ruff lint/format passed for the changed Python paths; configured
mypy passed on the two changed source files. Independent code review returned APPROVE; no Claude
review session/tool was available. Tests exercised the production import, storage, and page-read
functions with a synthetic worker fixture. The isolated literature parser subprocess was not run:
its locked worker environment is absent, and this slice did not authorize dependency restoration.
No live provider, paper fetch, full gate, private suite, migration, publication, or commit is claimed;
private coverage remains UNVERIFIED.

**2026-11-08 isolated source-reader successor (focused verification only):** The existing Research
Literature list can now check and download the retained original for a selected source. A read-only
HEAD route reports availability without returning PDF bytes; GET returns only bytes whose source,
project, size, PDF signature, and SHA-256 were revalidated by the existing CLI store and web API.
The UI exposes `available`, `missing`, `corrupt`, and `unavailable` states and enables download only
after a successful integrity check. OpenAPI/types and the committed Workstation build were
regenerated. Focused synthetic Python tests passed (26); the browser client tests passed (7), along
with TypeScript build, targeted Oxlint, Python Ruff, configured mypy, and OpenAPI generation.
An offline Chromium smoke against the built local FastAPI app downloaded the synthetic 47-byte PDF
with exact SHA-256 `e4bbc40ee9e4a69fbd027341718388015f9022f0cdfdaaa79e8eb5a171ce96b0` and verified
missing and cross-project responses. The canonical full gate and private suite were not run; no
provider access, external retrieval, source upload, publication, commit, or merge is claimed.
The Atlas client scanner now recognizes HEAD calls and its focused route-join test passes. Full Atlas
regeneration remains blocked in this sparse worktree because the required tracked source
`apps/alpha-mcp/src/alpha_mcp/server.py` is absent; its CLI cache still lists 233 commands while
the candidate CLI exposes 234, including `research sources original-pdf`. The generated Atlas
graph and CLI flow have not been refreshed or claimed fresh.

**2026-11-08 literature worker launcher correction:** The CLI now runs the checked-out
`literature_worker` module with `uv run --locked --no-sync`, Python safe-path mode, a closed
`PYTHONPATH` pointing only to the worker's `src`, network disabled, and existing process limits.
This avoids resolving the worker's unpinned Hatchling build backend at launch. Prepare its
environment separately with
`uv sync --project workers/literature --locked --no-dev --no-install-project`.
Six focused launcher tests and an actual offline synthetic-PDF import/page-read smoke passed
through the production launcher using the locked `pypdf==6.14.2` environment. No provider request
or full gate was run.


<!-- Preserved owner narrative: RD468304a9; historical claims apply only to that owner candidate, not the combined tree. -->

## 2026-11-08 — Shared authored-source integration (unqualified)

This reconciliation composes the selected authored-source candidates on exact base
`3f7b23185c29b2542605bd41b9485016c2ef3e79` (tree
`12640d9ef71932d3ce6cafddb27f5354a1ccc008`): Qlib048dc0ae,
Acquisition081e1776, RD468304a9, Paper972e621d and Science23cedef2.
The source composition contains 169 selected authored files before these three shared docs.
Two code overlaps merged cleanly: frontend `src/api/client.ts` (paper/science) and
`src/shell/documents.ts` (Qlib/RDLoop). Clean text merges are not runtime verification.
README merged cleanly; the manual keeps both native-bridge and stock-RDLoop boundaries.
The preceding owner narratives are preserved with their original dates and claims; their
focused checks, generated-output statements and qualification dispositions belong only to
those isolated owner candidates. They do not transfer to this combined tree.

Generated API, SPA and Atlas outputs, including the science synthetic-response fixture,
remain deferred. Fresh generated-output reconciliation, applicable independent review and
the unchanged canonical full gate are pending; no combined test, build, freshness, private-suite
or full-gate pass is claimed. The older acquisition accounting result of 36 passing tests at
4780 does not qualify the selected 081e successor. No tests or gate were run for this
reconciliation; no protected test source or generated output was read, and no commit,
publication, merge, deployment, empirical acceptance or trading authority is established.

## 2026-11-09 — Finance-math literature protocol successor (unqualified)

The existing literature-review protocol adds finance-math source-status and numerical-reuse
guidance, with its indexed hash updated. A companion guide preserves the 13 pictured titles,
unknown editions and missing slide, and exercises existing PCA on synthetic returns. No book
text was read or ingested, and no loader/schema, numerical code, dependency or authority changed.
The original loader tests and focused content/example checks are separate from full qualification;
the frozen combined/Dell handoff is unchanged. No activation or market-readiness claim is made.

## 2026-11-09 — Sparse generated-output successor (unqualified)

The pre-documentation working/index candidate retains canonical HEAD
`3f7b23185c29b2542605bd41b9485016c2ef3e79`. Its generated-output tree is
`21bd8fde7772d04887beac143f7774330e633139`, a separate successor to the
preserved sparse source candidate `618f1de8bf979e1f269c1e3279d68633367b587c`. These are
staged-tree identities, not new commits. This documentation change requires a
new final-tree identity; it does not extend the build evidence to edited bytes.

Two clean copies at different local source paths used the existing locked Python
and independently copied frontend dependencies. Canonical OpenAPI generation,
API-client generation, and the TypeScript/Vite/normalization build all passed in
both copies. The 55 regenerated output paths, modes, lengths, and SHA256 values
match exactly: OpenAPI, API client, and 53 SPA files. Two governance generated
documents remain unchanged. All 13 public assets match their copied outputs, and
the favicon/JavaScript/CSS references in index.html resolve. This is local
two-copy reproducibility, not cross-machine, UI, scientific, or full-gate acceptance.

The only generation delta is nine restored canonical demo-output files. All prior
44 SPA files, OpenAPI, and API client were freshly reproduced byte-identically.
The generator bound 82 ALPHA modules to each source copy. No source or lockfile
changed; predecessor source/index/objects and original dependency bytes remain
unchanged. Build warnings remain visible for Bokeh CustomJS direct eval and a
chunk larger than 1,500 kB. No dependency installation or additional test run occurred.

All 77 excluded paths retain their original object IDs/modes and remain absent.
Protected blob and parent-history closure remain incomplete; this is not a full
checkout. Complete public Qlib/RD-Agent/literature source and source-based UI
availability flags do not establish installed workers or successful training.
Atlas/protected processing, required independent exact-tree review, and the
unchanged full gate still require an authorized evaluation decision. Advisory
Claude/Codex participation is not a gate or review attestation. No activation,
publication, provider/model call, or trading authority is established.

## 2026-11-09 — Bounded finance-math source metadata and PCA checks (unqualified)

This separate revision preserves its predecessor and the frozen combined candidate. The existing
finance-math guide adds verified public bibliographic/access metadata, explicitly distinguishing
LADR fourth edition from the photographed third edition and preserving CC BY-NC conditions and
Harvard's disabled-download boundary. Original finite-matrix PCA derivations and focused reference
checks reuse unchanged numerical code. The literature protocol, its index and all 13 identities
are unchanged. No SourceAnchorV1, project-bound extraction or admitted book claim is created.
The later intake path requires a verified isolated worker, lawful owner-selected bounded source,
original-page provenance and the existing hash-verified claim workflow; no limit is weakened.
Focused test/lint/type evidence accompanies this isolated revision. No full-gate, production,
market, ingestion, screening, promotion, publication or trading qualification is implied.

## 2026-11-09 — Explicit partial Alpha158 feature correction (unqualified)

A separate successor preserves feature recipe 1 and adds explicit feature recipe 2. The new
recipe calls actual pinned Qlib 0.9.7 operators for eight families at five windows (40 columns);
118 columns and the typical-price VWAP proxy retain legacy behavior. Partial-window semantics
are recorded. This is not provider/calendar/corporate-action, full-handler or whole-Alpha158
parity. Canonical input alignment is unchanged. No historical artifact is relabeled or recomputed.

The existing producer/CLI/worker/request schemas and typed web projections now accept explicit
v2. Default v1 request bytes and digests match the preserved predecessor on the frozen synthetic
fixture; old readers reject v2. Prediction config hashes reject cross-recipe lineage reuse.
New implementation fingerprints are genuine new code identities. Complete predecessor seven-file
refit inventories remain plannable for v1; v2 requires the complete expanded inventory. Old frozen
code is not treated as current code. Capability/v2 projection changes require a coordinated
worker/web service upgrade. Legacy capability and tear-sheet response shapes remain accepted.

Fresh focused evidence: 36 worker cases and 46 root cases passed, with no skips, on the current
source. Coverage includes all five windows, finite values and NaN masks separately, independent
numeric anchors, causal prefixes/future changes, cache isolation, original default behavior,
versioned contracts, mocked pre-model dispatch, legacy response shapes and frozen-source refit
planning. Exact predecessor-source inventory and old-reader probes passed separately. OpenAPI
freshness, generated TypeScript/application type checking and changed-source lint/types passed.
Expected test-first failures, one API regression subsequently fixed and a diagnostic exception-
handling correction are retained in the external execution evidence rather than hidden as a
single-run pass. Source review is read-only engineering advice; final frozen-tree review is
recorded separately with the delivery receipt.

No real model training/inference, provider initialization, market/broker access, owner-store
operation, GPU work, package change, commit or publication occurred. Full gate, Atlas/protected
suites, end-to-end fitting, UI visual qualification and scientific/economic acceptance remain
unverified. See the [scope plan](work/2026-11-09-alpha158-versioned-correction/02-plan.md).

## 2026-11-09 — Configured Matplotlib web-to-CLI environment

The web-to-CLI default-deny process environment now permits only one additional
name, `MPLCONFIGDIR`, for Matplotlib configuration and cache placement. A configured
server-process string passes verbatim; unset stays absent. No default, path
validation/normalization, request override, other environment-filter expansion or
worker/model environment change is introduced. The renderer's Agg selection and
rcParams-default initialization are unchanged.

All 36 focused public cases passed: 24 original web invocation cases, 11 new
configured/unset/literal-value/stdlib-child cases and the existing cache-seam
no-heavy-import node. The test-first predecessor behavior failed seven configured
forwarding assertions while four unset controls passed. Scoped Ruff/format and
strict changed-file mypy passed. This verifies the direct environment contract,
not an actual Matplotlib render or chosen cache location. Required documentation
and the unchanged combined manual size limit are retained.

This separate uncommitted successor preserves frozen selector tree
`deb10cc217a7a7359f08e38a6cd4cc1542b9971e` and its evidence. Independent frozen-source
review remains separate; selector browser cases/negative control, actual renderer
verification, default/browser lanes and full qualification remain unrun here.
Future rendering checks require fresh empty owned writable absolute configuration
storage and a verified owned CWD without `matplotlibrc`. This is not whole-home,
font-discovery, other-library/descendant-cache or network isolation, nor a sandbox.
No owner configuration/data, provider/model workload, installation, history repair,
commit or publication was used. See the
[contract plan](work/2026-11-09-web-matplotlib-environment/02-plan.md).

**2026-11-10 scoped candidate — deferred risk UI fixture capture:** Added a version-1
capture command for the previously deferred public synthetic risk-metric-basis input.
It uses the existing artifact/TestClient/CLI path over two fixed artificial equity
curves, checks documented anchors/conventions, independently calculated base returns
and drawdowns, strict schemas/finite JSON and complete legacy parity before immutable
publication. The fixture sidecar distinguishes fresh captured UI inputs from independent
numerical expectations and binds inputs, source/run/artifact hashes, runtime and output.
The 31 focused producer cases, scoped Ruff/format and strict mypy passed. Existing
application code and the four original source-mounted browser assertions/config are
unchanged. Independent final review and the dedicated browser run remain separate;
default browser-suite routing is still unresolved. No full gate, protected tests,
providers/models/owner data, installs, commits or publication. See
[the capture plan](work/2026-11-10-risk-basis-fixture-capture/02-plan.md).

## 2026-11-10 — Bounded browser-lane routing successor

The existing mandatory frontend browser command now dispatches four fixed existing
fixtures: ordinary/default, source-mounted risk basis, raw-Vite synthetic risk live,
and the exact native-result pytest driver. Only the three incompatible specs are
excluded from default discovery, paired in the same candidate with positive routes.
Original browser specs, dedicated configs/drivers, project policies and gate/CI
ordering remain unchanged. Fresh listing/execution identity binding prevents partial
results being credited, and skipped/missing/wrong native JUnit cannot pass.

This is scoped source/test/docs work on a distinct uncommitted successor of frozen
`b38bda23a9db0ecdc6b7c5fc55889bc4e69b7901`. Public stub tests and scoped checks
verify orchestration only. Full/default/native execution and project qualification
remain unrun; installed native selectors remain a named prerequisite, not an accepted
skip. Predecessor browser evidence is preserved at its original narrow scope.
The [routing plan](work/2026-11-10-browser-lane-routing/02-plan.md) records
prerequisites, immutable evidence, README/manual review and remaining acceptance.
