---
owner: web frontend
sources:
  - apps/alpha-web/frontend/src/panels/**
  - apps/alpha-web/frontend/e2e/**
verified: 73e344d3cc83031c
---

# Web run detail invariants

How the run detail, RD-Agent journey and Setup Lab panels bind to the selected run. The other frontend rules are in [web-frontend.md](web-frontend.md).

## Run detail binding

- `panels/rundetail/index.tsx` tags every async result with the `runId` and request id that asked for it, and renders only results
  for the currently selected run and its latest request. A previous run's summary, figures or trades must never show or export
  under the new run.
- States are explicit: no run selected → "Select a run"; error → the error; pending → "Loading run…". A trades request error stays
  distinct from a genuinely empty trades list. Enforced by `e2e/rundetail-trades-race.spec.ts`.
- `reportModel.summaryRows` shows recorded manifest values only (`not recorded` otherwise) — no client arithmetic.
- `reportModel.reportTree` keeps empty leaves visible with their reason. In the figure overlay a Copy the browser cannot do is
  disabled with the reason, and question, uncertainty and caveat prose stays in the DOM in both explain modes.
- The rule-test Summary takes its headline dates from the first executable open through the final tradable open. Loaded dates
  appear below. Each dated row reads its own stored returns, annual growth, worst drop, closed trades, Sharpe and price basis from
  the manifest. Row one is “Whole period the rule could trade”; “Scored test periods only” uses the walk-forward portfolio and its
  trade count. Each row has matching comparison and drawdown figures, stored light for new runs. Old runs keep saved figures and a
  full-history disclosure. Missing period values read “not recorded”. A catalogue request distinguishes loading, failure and
  missing figures. Flags and variants precede closed setup and audit disclosures. Audit rows retain each identifier, status and
  detail. Only variants subtract Sharpe scores. Covered by `ruleTestModel.test.ts`, `rundetail/RuleTestSummary.test.tsx` and
  `e2e/rule-test-summary.spec.ts`.
- The rule-test Summary lists “Checks run on this test”: each stored toolbox result (plain name, stored reading, labels in words,
  time) or “could not run: <stored error code>”, from GET `/api/runs/{id}/checks`. With none it quotes
  `alpha tool run-set market-context <run_id>`. Nothing is computed in the browser. Covered by `rundetail/RuleTestChecks.test.tsx`.
- Rule tests and Setup Lab show a non-pass data health line under the headline; old runs read “Data health: not recorded.”
- The backtest result card is opt-in (`backtestResultCard` defaults to `false`). With malformed, legacy or failed evidence it
  renders as unavailable. Enforced by `e2e/backtest-result-card.spec.ts`.

- The RD-Agent picker shows each idea's name, recorded verdict in plain words and publication state. The run summary omits missing
  values or shows “This run stored no summary.” Ledger absence appears in technical detail. Selecting an idea reads its journey in
  place. Responses and disclosures belong to that run and idea. The header repeats the recorded exploratory label from the last
  fact of step seven. The seven steps keep their stored order, actor and wording. Each headline number uses its stored display
  string and a visible gloss. A step shows its PNG on a light card, or its recorded reason in muted text. The card sits below the
  text in a narrow pane. Code keeps its indentation and wraps long lines with a hanging indent. Source files, the agent's own
  words and code beyond twelve lines use closed disclosures. Missing values read “not recorded”. A missing journey shows the local
  build command. The browser starts no build. Covered by `RdAgentPanel.test.tsx`, `RdAgentJourney.test.tsx` and `e2e/rdagent-
  journey.spec.ts`.

- Setup Lab is Research → Setup Lab (`SetupLabPanel`, both profiles): GET routes only, each response bound to the selected find.
  Stored figures have value tables. Trade return and initial risk display as percentages beside direction and R. The timeline
  keeps rejected matches grey. Values round only; no curve or total is calculated. Unstored parts say "not recorded". Tests:
  `SetupLabPanel.test.tsx`, `setupLabModel.test.ts`, `e2e/setup-lab.spec.ts`.

## Reading block

- The rule-test Summary and Setup Lab show a reading block, never a letter grade, "supported", "rejected" or
  "inconclusive" (`components/ReadingBlock.tsx`, `panels/readingModel.ts`).
- Order: fact checks, the stored sentence, evidence strength (a four-step scale in neutral tokens, the current step
  named and marked, the `because` facts), against the aim (relation words and a range picture of the 95% interval
  with the aim as a tick), measures, counts, footer.
- A fault replaces the block: "Fault: ... Fix this first. No reading." Its numbers sit behind a closed disclosure.
- Each measure has a plain-words hint, and the default aim line is two short sentences. The audit rows read sound, flag or
  not checked. The run list and the Summary "Reading" row show the stored word, else the old grade, muted.
- A run with no reading and an old letter says "graded <letter> under the old rules", muted.
- The reading comes from the checks request, as the CLI states it. The browser derives nothing.
- Tool results show a declared or exploratory chip and the CLI's count line.
- Setup Lab shows the evidence word and scale, the stored sentence and "Setup study K of N recorded for this idea".
  Old records add "(old wording)". The old outcome word is hidden.
- Covered by `ReadingBlock.test.tsx`, `readingScan.test.tsx` and `e2e/reading-block.spec.ts`.

## Readings in the remaining places

- No screen shows a letter grade, a PASS or FAIL result, "passed", "verdict" or a good or bad colour for a run. The JSON fields `verdict`,
  `passed` and `overall` stay for machines. The words come from `panels/readingModel.ts`: `runWord`, `manifestWord`, `toastDetail`, `paletteHint`.
  The browser re-derives no word.
- A run in a list shows its evidence word, else "graded X under the old rules", muted: the Navigator run list
  (`navigatorModel.ts`: the word after the short id, no result column), Pipeline (`PipelineLatest`), the activity feed
  (`ActivityFeedView`), toasts, the command palette.
- Summary has a "Reading" row and no "Passed" row. The edge review has a "Reading" row and no verdict or gate-result row. A Monte
  Carlo run adds one row per family: stored percentiles in words, no letter and no stage word.
- Gates tab (`explain/gates.ts`, `Gates.tsx`, `ExplainCard`): each check is a FACT (walk-forward: the icon and "computed", "fault"
  or "not checked", with the hint "computed means the check could run; it does not say the result is good") or a STAT (the numbers
  and the plain comparison, such as "the interval includes zero" or "random data did as well in 3.0% of draws"). A STAT card adds
  one muted line: "The level used by the old grade: X". A STAT with no input reads "not computed: <reason>" and no old level. Each
  card puts one plain sentence first, then the numbers, then a closed "How this check works" disclosure that holds the method and
  the long reading. No card is coloured good or bad. The one classification is in [command line readings](cli-rule-
  readings.md#report-cite-and-the-gates).
- The Stress test tab shows scenario numbers; its terms in `explain/glossary.ts` carry no grade bands. The glossary lists the old
  grade as "retired".
- Covered by `readingEverywhere.test.tsx` (words and a lone letter, old and new style) and `e2e/readings-everywhere.spec.ts` (light, dim, dark).
- The grade display code (`explain/bands.ts`, `explain/verdictStory.ts`, `util/verdict.ts`, the `--verdict-*` tokens) is deleted.

## Gates check charts

- Each Gates card also shows one small chart of that run's own recorded data, between the plain sentence and the numbers
  (`rundetail/walkForwardModel.ts`, `checkChartModel.ts`, `nullChartModel.ts`, `WalkForward.tsx`, `CheckCharts.tsx`, `NullChart.tsx`).
  The browser draws; it computes nothing. Walk-forward: the price carries the meaning. One shaded band per fold's tested period
  (`folds[].test_*_ts`), two alternating tints, a divider between folds, and the fold's out-of-sample Sharpe in the band when it
  fits (else on hover or focus). Price before the first band is unshaded, "before the first test". Under the price is a staircase,
  one row per fold: that fold's own warm-up (hatched) then its tested part. With more than 8 folds it shows the first 3 and last
  2 rows, "… N folds in total" and a "show all folds" button; the bands stay for all folds. The hatch reads "warm-up: rules fixed,
  nothing re-tuned" for `oos_semantics` `fixed_rule_evaluation_no_refit` (with the sentence "The rules never change in this test"),
  "rules tuned here" for `fold_by_fold_refit`, else "training window". A fold whose own training dates run past its tested start
  shows a labelled "tuned and tested periods overlap" mark. Axes: three price ticks, year ticks, both end dates.
  Price is `GET /api/candles` for the run's symbol from its first date to its last recorded date, or its `research_cutoff` when
  that is earlier: nothing after the run's window or inside the held-back period is asked for (`useCheckChartData.test.ts`,
  `tests/integration/test_web_api_candles.py`). The legend says the bars are those stored now; the run's own bars are not saved.
  With no stored bars the bands and staircase still draw and the note reads "price not available: no stored bars for <symbol>".
  Null: per tier from `GET /api/runs/{id}/nulls`, plain tier name first, the recorded Sharpe marked, the recorded p-value as the
  share. A tier with 20 or more draws is a histogram; with fewer it is one tick per draw and says "only N random series: a rough
  picture". Tiers share one size, at most 160 px tall. Bootstrap: zero, the interval bar and the point. Deflated Sharpe: two bars
  on one scale, both "per trading period"; the yearly figure in brackets only when the run recorded `periods_per_year` (times the
  square root of it), and the line "The deflated Sharpe (x) is a probability from 0 to 1, not a Sharpe ratio." Cross-validation:
  the recorded mean and spread ("mean ± one standard deviation") only; per-split Sharpes are not stored. Missing or non-finite
  input reads "Chart not available: <what is not recorded>"; a read that fails or takes over 20 s reads as missing, never
  "Loading chart…" for ever. Each chart has an `aria-label` with the same facts. Covered by `walkForwardModel.test.ts`,
  `checkChartModel.test.ts`, `nullChartModel.test.ts`, `CheckCharts.test.tsx` and `e2e/check-charts.spec.ts`.

## Workstation recorded fields

View → RD-Agent and the command palette open the read-only panel in either market profile. Runs are direct child
folders of `<data dir>/../runs` (override: `ALPHA_RDAGENT_RUNS_DIR`); the ledger is
`rdagent-trial-ledger/rdagent-factor-trials.jsonl` inside it. It cannot launch, approve, call models or read keys.

| Response fields | Recorded source (relative to the run folder unless noted) |
|---|---|
| Identity, start/end, outcome | `receipt.json`: `run_id`, `started_at`, `ended_at`, `exit_status`, `loop_reason`; folder name |
| Rounds, calls, embedding calls | Receipt: `memory.rounds_completed`, `counted_calls`, `local_embedding_calls`, `provider_embedding_calls` |
| Spend, caps, month snapshots | Receipt: `gateway_status.this_run.usd`, `.caps`, `.months`; month selected by receipt end time |
| Cache and providers | Receipt: `call_split.chat_usage`; no new rate calculation |
| Funnel and list stage totals | Receipt `funnel` if present; else ledger factors plus `rounds.jsonl` refusals and provider losses |
| Factor name, description, status | Shared ledger: `run_id` or folder name, schemas V1–V3; fixed web-owned status sentences |
| Clock figures, deflation, write-offs | Ledger: `clocks.*.screen`, `.spread`, `.replay`, `.replay.deflated_sharpe`, `.replay.deflated_sharpe_family` |
| Universe, gaps, ticker corrections | `panel/panel-receipt.json`: instruments, disclosure, gap counts, `identity_breaks`, `identity_rescales` |
| Refusals and timing | `rounds.jsonl`: refusal status and families; `steps.jsonl`: step start and end times; minutes = end minus start, labelled |
| ALPHA notes | Receipt cap/cache/memory notes, panel disclosure, `evaluations.jsonl` → `feedback_text` |

New rows show declared choices, cutoff/counts, diagnostic p/q, deflation, twins and expected chance passes. The funnel
adds "shortlisted (passed all but the many-tries correction)" before the deflation stage. Shortlisted is not a pass,
not a candidate, and not evidence of profit; missing flags mean "not recorded". Lineage R², regressor count and
convention are recorded diagnostics; suspects say "looks like a blend of earlier tries". The [shortlist
policy](../../../workers/rdagent/judge-rules.md#shortlist-bookkeeping) leaves every gate and count unchanged. Old
failed-deflation candidates read DEFLATION_FAIL (derived); stored deflation is labelled "old rule (fewer looks
counted)". Absent facts stay null. Counts come from recorded rows, never candidate status; step minutes need two
timestamps. New factor rows store family and critic status. Older rows can lack both. The panel was opened headless on
real runs; owner acceptance remains pending.
