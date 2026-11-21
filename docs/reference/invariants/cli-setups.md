---
owner: command line runs and validation
sources:
  - apps/alpha-cli/src/alpha_cli/setup_cmds.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_*.py
  - tests/unit/test_setup_*.py
  - tests/unit/test_reading_ledger_setup.py
verified: dadd174c4194dee6
---

# Command line setup invariants

Rules for `alpha setup find`, `alpha setup study`, `alpha setup trade` and `alpha setup show`. Other run rules are in [cli-runs.md](cli-runs.md).

## Setup show
- `alpha setup show <id> [<id> ...]` only reads: it writes nothing and counts nothing.
  It prints the stored outcome's reading ([rule](cli-rule-readings.md#rule-test-readings)).

## Setup find
- `alpha setup find` resolves daily spec assets in order, honours `@store`, and records no outcome after the entry open.
- Per-asset errors remain visible; all failed assets produce `FIND_FAILED`. Invalid specs and unknown selections fail loud. Events at most ten bars
  apart share a cluster; draw only its first accepted day. Counts and facts retain matching days and occurrences.
- Sheets stop at the trigger plus entry open; rejected samples stop at their decision boundary. Pending and warm-up rows are not drawn.
- Accepted sheets are capped and labelled when truncated; rejected sheets sample at most four reasons and four days per reason.
- Find ids bind spec, context (60 bars by default), asset fingerprints and health evidence, never sheet limits; unchecked finds keep a free or
  matching old id. The atomic manifest is last; repeats append a ledger row, rewrite nothing. A `setup_find` row is an uncounted look, no verdict.
## Setup study
- `alpha setup study FIND_ID` reads accepted cluster-first candidates without detecting again or changing the find.
- Reload successful assets through the same point-in-time loader; changed fingerprints or providers require another find.
  Find and reload cut at 2023-12-31. A find with held-back bars records `reserve` and its label, and study and trade carry them.
  A find without `reserve` whose last bar is on or after 2024-01-01 is refused (`RESERVED_PERIOD_SEEN`) before any bar loads.
- Recorded next-open entry to close h−1 positions later, less per-asset round-trip `setup_costs` (stocks/ETFs: 1+2 bp per side; crypto: 10+5 bp); no exits,
  dividends or sizing.
- Incomplete outcomes are excluded per horizon. Drift uses every post-warm-up eligible date; random controls use 2,000 spaced uniform subsets.
- SHA-256 seeds exclude health metadata. Draw dates uniformly over 10 bars apart. Tail (b+1)/(2,000+1). Pool by complete occurrence counts.
- Only pooled primary outcomes are tested; other horizons carry `not-primary`. Each chronological half uses controls from its own years, no p-value.
- `setup-studies/<id>` binds find id, `setup-study-2` and new health evidence. Old folders read with `older-cost-rule`.
  Re-studying a find with an older-rule study is labelled `remeasured-new-cost-rule` and counts again: a new cost assumption is a new look, never a free one.
- Publish outcomes, summary and a deterministic 1600 × 900 figure before the atomic, hash-bound manifest; verify sidecars before reading.
- Facts support `results cite|check`; a stored `total_trials` records observed ledger rows plus this study, preserving the draft check's requirement.
- Words: the study prints `too little to read` (under 30 occurrences), `not clear of chance` or `some evidence` (p ≤ 0.05, positive excess,
  agreeing halves). The words live in `spine/reading.py`. Never `clear of chance`: the p-value is not corrected for the setup variants tried,
  and the text says so.
  The text adds "Setup study K of N recorded for this idea" and the random-date figure "adjusted for the N studies recorded for this idea
  (false-discovery method)": the `benjamini_hochberg` q over the stored p of every counted study of that kind and idea text.
  That q is the lowest false-discovery rate at which this study would still be picked; for the smallest p it is p × N.
  Repeats count once. A missing stored p, or a run not in the family, prints "not adjusted".
  The family is matched by idea text (case and spacing ignored), so the text always adds "Variants saved under another idea text are not counted."
- `summary.json` keeps `outcome` as written and adds `evidence`; an old summary is read through its old word, noted once.
  No rule version, id, seed or stored number changed.
- `setup study|trade|find` print `executed`: `true` if computed this time, `false` if the stored result came back (`repeat` label).
  `setup study|trade <find_id> --recheck` computes again with `compute_study`/`compute_trade` and compares the summary and every
  row of the stored table with the stored ones (not `facts`, `total_trials`, `data_health`, `data-health-*` labels).
  It writes no ledger row or file; exit 4 on a difference. A changed stored file fails its hash check first.
- One counted trial; repeats append an uncounted row. [Family rules](cli-trial-ledger.md); [controls and limits](../../../research/tools/setup-study.md).
## Setup trade
- `alpha setup trade FIND_ID` shares verified find inputs; missing/empty exits raise `SPEC_HAS_NO_EXIT`. [Details](../../../research/tools/setup-trade.md).
- Freeze percent, evaluator ATR and numeric/reference levels at trigger close; entry is the recorded next open. CLI aliases preserve original hashed names.
- Both directions check stop gap at open, stop touch, target at target, opposite at next open, then time at close. A both-touch bar counts as a stop.
- Entry is bar one; exits at an open exclude that new bar from duration. No time limit implies 250 bars and `no-time-exit`.
- One position per asset, including the exit bar. Count skipped/invalid/open-at-end separately; only completed trades enter tested means.
- Mark open-at-end to final close. Adverse move sees only an open or stop fill on that exit, otherwise the adverse extreme (low for long, high for short).
- Costs use the dataset asset class, then slash pairs or a crypto provider (any `:` part), then a stock provider (yfinance, alpaca, tiingo, stooq);
  unknown markets use crypto costs with `costs-assumed-high`. Short borrow/funding assumptions are stored per asset; a short without its carry fails.
- Drift starts after every eligible bar, without occupancy. Random controls draw occurrence counts, apply occupancy, weight assets by completed trades.
- Use 2,000 spaced draws. Missing comparisons carry reasons. An uncounted control replays the same entries in the opposite direction with its own costs.
- Halves use their own entry-date ranges. `some evidence` requires 30 completed trades, positive excess, p ≤ 0.05, agreeing halves and available
  controls; exploratory only. The trade prints the same evidence, family and figure lines as the study.
- Hash find id with `setup-trade-1`; publish parquet, summary and deterministic 1600 × 900 PNG before a hash-bound manifest in `setup-trades/<trade_id>`.
- Repeats preserve records. New exits or direction count in `setup:<idea>`. R divides net return by initial stop risk. No currency sizing.
- Find output derives `outcomes-viewed` from sibling study/trade manifests without rewriting its folder.
## Setup context
- A spec may add `[context]`: alias → `series@key` (a [derived series](data-context.md#derived-series-and-the-one-join); the key is declared, `SELF` is the
  asset's own symbol). Aliases are number sources in `event`, `filters`, `trigger` and `reference`, not in `[exit]`. An alias may not be a price
  source, a function or a filter or reference name. Without `[context]` the spec keeps its old identity, ids and files.
- `spine/setup_context.py` makes the only call to `attach_context` (cut 2023-12-31) and hands plain `ctx_<alias>` columns to `alpha_study`, which
  imports no data code. The rule-test gate (`_context_gate`) uses the same `attach_bindings` call. The used rows hash includes the
  alias name, so in Setup Lab a renamed alias gives a new context fingerprint; the rule gate hashes under canonical names.
  Context holds its own warm-up as null, so aliases add no warm-up. A null never makes a condition true:
  `for_bars` and `within_bars` over context are three-valued, so `not` of a window with a missing value is not true.
  `[exit]` refuses an alias with a plain error: exits run on the price bars alone (a current limit, not a safety rule).
- A filter that reads a context value older than its limit rejects the event as `context-stale`. Other nulls (not yet known, delayed release,
  series warm-up) are `warm-up` and are not drawn. Each find asset records `context`: nulls by reason and bars with a value
  (they add up to the bars), the span with a value, and for each condition the bars where it was true and its separate spells.
  The text always says days overstate the sample.
- Label `short-context-history` when the span with a value is under 3 years. Study and trade carry the label, the block and the sentence.
- Identity: a context spec adds the hash of the rows used and the recipe version to each asset's data key, never a table file hash, so rows added after
  the reserved day do not make a new find or test. The spec change itself is a new test in the same `setup:<idea>` family.
- Study and trade attach again and compare that hash with the find's. A difference is `DATA_CHANGED_SINCE_FIND`; `--recheck` raises it too.
  Random controls sit in each asset's own span: from its first to its last bar where every alias has a value. A short stale
  gap inside the span stays drawable for controls (the draw needs one unbroken run of bars); the block counts those bars.
- Reading only: no pass or fail, no advice, never `clear of chance`. [Tool card](../../../research/tools/setup-find.md).
