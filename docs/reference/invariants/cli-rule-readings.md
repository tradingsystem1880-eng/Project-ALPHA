---
owner: command line runs and validation
sources:
  - apps/alpha-cli/src/alpha_cli/spine/reading.py
  - apps/alpha-cli/src/alpha_cli/spine/reading_read.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_file.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_file_text.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_map.py
  - tests/unit/test_idea_file.py
  - apps/alpha-cli/src/alpha_cli/spine/run.py
  - apps/alpha-cli/src/alpha_cli/test_cmds.py
  - apps/alpha-cli/src/alpha_cli/_context_gate.py
  - apps/alpha-cli/src/alpha_cli/_context_plan.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_context.py
  - tests/unit/test_rule_context_gate.py
  - tests/unit/test_rule_context_plan.py
  - tests/unit/test_rule_context_identity.py
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
  - apps/alpha-cli/src/alpha_cli/report_cmds.py
  - apps/alpha-cli/src/alpha_cli/spine/report_readings.py
  - tests/unit/test_report_readings.py
  - apps/alpha-cli/src/alpha_cli/next_cmds.py
  - tests/unit/test_reading_rule.py
  - apps/alpha-cli/src/alpha_cli/spine/trial_record.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_reading.py
  - apps/alpha-cli/src/alpha_cli/ledger_cmds.py
  - tests/unit/test_reading_ledger_setup.py
  - apps/alpha-cli/src/alpha_cli/backtest_cmds.py
  - apps/alpha-cli/src/alpha_cli/optim_cmds.py
  - apps/alpha-web/frontend/src/explain/gates.ts
verified: 655e0dfacb1217f3
---

# Command line rule-test readings invariants

What must not break when changing the reading of a rule test. Owner decision 2026-11-19: results are readings in context, not
grades. The stored run files are in [command line runs](cli-runs.md#stored-facts-and-diagnostics).

## Rule-test readings

- A new run manifest stores `reading` (`AlphaReadingV1`, `spine/reading.py`) beside the old `verdict`. Both stay in the file.
  The reading only arranges numbers the gauntlet stored. It computes no statistic and changes no id, trial count or threshold.
- Parts: `checks` (sound, fault or not-checked), `measures`, `evidence` (word and reasons), `aim`, `counts`, `sentence`.
- Four evidence words. Their one home is `WORDS` in `spine/reading.py`; the list below is that text, and
  `tests/unit/test_reading_rule.py` fails when the two differ. The precedence is the list order from the bottom up:
  `too little to read` wins, then `not clear of chance`, then `some evidence`; `clear of chance` needs every check.
  - `too little to read`: Under 30 closed trades or under 100 out-of-sample observations, or either count was not stored. This word wins over every other.
  - `not clear of chance`: The Sharpe is not above 0, its interval includes 0, random data did as well as the rule in more than 5%
    of draws, or the deflated Sharpe after counting trials is under 0.95. A missing interval, null test or deflated Sharpe reads
    the same way.
  - `some evidence`: The Sharpe interval is above 0, every null test holds and deflated Sharpe is at least 0.95, but
    cross-validation, a plausibility caution or a plausibility check that did not run, or trials not counted from a ledger family
    hold back the top word.
  - `clear of chance`: Every check holds after counting all trials: each null test at 0.95, the 95% Sharpe interval above 0,
    deflated Sharpe at least 0.95 with the trials counted from the ledger family, cross-validated mean Sharpe above 0, and the
    plausibility check ran and raised nothing.
- Only the deflated Sharpe counts trials. The bootstrap interval and the null tests do not. So no positive word is printed when the
  trial-corrected figure is under its line or missing, and a missing number never makes a word stronger.
- The aim today is buy-and-hold over the same scored days, on the run's price basis, with no costs. The relation uses the strategy's
  stored 95% bootstrap Sharpe interval: an aim below it reads `above the aim`, above it `below the aim`, inside it
  `within the uncertainty of the aim`. The benchmark's own uncertainty is not included, and the basis line says so. With no
  same-days benchmark or no stored interval there is no aim row.
- A statistic that could not be computed, a look-ahead flag in the audit, or a failed data check is a fault:
  "Fault: ... Fix this first. No reading." Fact checks stay hard.
- A manifest without `reading` gets one derived from its stored numbers on read. A ledger row with only a letter reads
  "graded C under the old rules". Owner text for rule tests never prints a letter grade, "supported", "rejected", "pass", "fail" or "profit".
- `--json` keeps `verdict` and adds `reading`.
- A run id hashes every `alpha_cli` source byte, so any edit moves it. `tests/unit/test_reading_rule.py` holds that input fixed and
  proves the reading changes no id.

- Each reading also carries `costs`: the one costs line and the annualisation line the run used. Rules and the table:
  [cost classes](cli-cost-classes.md).

## Ledger words

- A new rule-test ledger row adds `evidence` (the reading's word, or `fault`) and `aim_relation` (or null) to every field it had.
  An error row carries both as null. The letter stays in `verdict`; machines still read it. No stored row is rewritten.
- On read, `TrialRecord.outcome` is the owner word: the row's `evidence`; for an old row with only a letter,
  "graded <letter> under the old rules". `machine_outcome` keeps the old four-way word and `raw_status` the letter, in `--json` only.
  `alpha ledger` text never prints the letter. `--outcome` still accepts the old machine words.
- Counting reads none of this. `counts_for_deflation`, the labels `repeat` and `error`, `make_test_key`, `row_test_key`, the
  same-asset count and `n_trials_used` never read an outcome word. `tests/unit/test_reading_ledger_setup.py` runs them on
  a ledger with and without the new fields and requires equal results.
- A setup row reads the same way: its `evidence` word, or its old word mapped to the evidence word it came from, with the note
  "recorded under the old wording". The reader accepts the three old words and the three new ones.
  `alpha setup show <id> [<id> ...] [--json]` is the one read of it, any number of ids in one call (the ledger is read once): `readings`,
  one per id with evidence word, `old_wording`, and the family (place, count, adjusted figure). The web relays that output in one call
  per find and keeps no copy. An unknown or badly shaped id fails the call with `UNKNOWN_SETUP_OUTCOME`. With no ledger file the family
  count and place are null (not recorded); an empty ledger counts 0.
- RD-Agent wording unchanged for now: RD-Agent rows keep their old words, and the proposer's ledger text is byte-identical
  (a test pins it). That is a separate change.
- `--outcome` takes an evidence word or an old word; both match, and the help text says so.

## Recheck

- `alpha test <spec> --recheck [--json]` computes each asset again with the current code and data, then compares it with the newest
  stored non-error run of the same test key (`row_test_key`: spec hash, asset, store, data fingerprint, window, bar size) and the
  same engine settings (`--quick`, seed, gauntlet knobs, no-diagnostics). "Recheck" means "computed again and compared with the
  stored result". It is a system check, not a trial and not a new observation.
- It calls the normal `prepare_asset` and `write_run` into a scratch folder that is removed afterwards, also on a crash. It uses
  the stored run id (it seeds the price-noise copies) and the ledger rows before the first row of the stored run, so the trial
  counts are the stored run's. It writes no ledger row, run folder, manifest, figure or lock file. `--check-data` is refused with
  it (a health report is a file). Held-back period, point-in-time reads and data health are as in a normal run.
- Compared: every field of the manifest, the diagnostics and `spec.json`, and every value of every parquet table (trades, folds,
  fills, equity). Left out: the code fingerprints (reported as `code_changed`), the health record and `data-health-*` labels,
  `spine.test_id`, file bytes (`sha256`, `size_bytes`), the HTML report, and the folder named in a "no macro data" detail.
  A field or file on one side only is a difference. Integers, words and labels are equal. Floats are equal within
  `rel=1e-9, abs=1e-12` (another summation order); `bit_identical` says if every float was equal. Two NaN are equal.
- Per asset: `recheck: {compared_with, computed, seconds, match, bit_identical, differences (first 10), code_changed}`. `code_changed` is true
  when the stored run's execution fingerprint differs from now; it never excuses a difference. With nothing to compare with:
  `computed: false, match: null`, nothing is computed or created, and `reason` says why (nothing stored; the stored bars
  changed; only other engine settings stored). Exit 0 on a match or nothing to compare; exit 4 on a difference.
- Normal results also carry `executed` (`true` if the engine ran this time, `false` if the stored run came back), not in the ledger
  or any identity hash. `repeat` still means the same test by key. `alpha setup study|trade <find_id> --recheck` does the same for
  the setup tests: the summary and every row of the stored table compared; ledger count, health record, health labels and facts
  left out; `code_changed` is null ("not recorded"). Setup find reports `executed` only.

## Context gate plan

- A spec may carry `context` (`{alias: "series@key"}`) and `when` (a condition over the aliases). `when` needs `context`, and
  `context` needs `when`, and `when` must read every alias. Aliases follow the Setup Lab rule (`check_aliases`): lowercase,
  never a price source or a function, so an alias cannot shadow a price. A bad alias, series, key or condition fails when the spec loads.
- Canonical form (`_context_gate.canon`): each alias becomes `c0`, `c1`, ... in the sorted order of the bound `series@key`
  texts, and `when` is printed again from its parse tree. The spec hash takes this form; the stored `spec.json` keeps the text as
  written. So alias names and spacing make no new test; a new series, key, threshold or structure does. A spec without context
  hashes and dumps exactly as before (a test pins three hashes and the stored bytes).
- `build_gate` attaches through `setup_context.attach_bindings` (the one call to `attach_context` for Setup Lab and the rule
  gate; daily bars; reserve cutoff) under the canonical names, then reads canonical `when` with `compile_expr` and the canonical
  names as context sources. The language is three-valued: a missing value never makes the condition true, also under `not`,
  `within_bars` and `for_bars`. A null gate is false on that bar and is counted by reason (`not-yet-known`, `stale`, a derived
  reason, `series-warm-up`, `expression-undefined`). True, false and null bars add up to the bar count. The gate is a map from
  bar timestamp to a boolean, never an index.
- `context_fp` is the sha256 of the used rows hashes (from `attach_context`, under the canonical names), the recipe, the
  staleness limits and canonical `when`. The data id is `idea_id(spec hash, sha256(source fingerprint + context_fp))`. Source
  table hashes are provenance only. Rows after the reserve or not known by the cutoff are not used rows, so adding them changes
  no test key. The family stays `spine:<rule kind>`: ten thresholds are ten tests in one family.
- `alpha test <spec> --plan [--json]` reads bars and context and prints, per asset: the context span (bars where every series has
  a value), gate true and false bars, the separate spells, null counts by reason, labels (`short-context-history` when the span is
  under 3 years), the test key and one sentence. It runs no engine and writes no ledger row, run folder or lock file; a test lists
  every path with size and mtime on each branch.
- `alpha test <spec>` without `--plan`, and `--recheck`, refuse a context spec: "the gated engine is not built yet; use --plan".
  `assemble_run_spec` also refuses a context spec, so no path runs the ungated rule. `--plan` on a spec without context is
  refused. The words are readings: no pass, fail or advice.

## Idea file

- `alpha idea file <card id> [--json]` prints one page per idea. It joins records that exist. It computes no statistic.
- Read-only: no file under the home changes, no ledger row, no network, no model call.
  The ledger is read with `read_trials_readonly`, which never creates the lock file.
  A test compares the home before and after, with no lock file present.
- Order: the card; the map; readings oldest first; counts; open points. `--json` keys: `card`, `map`, `readings`, `counts`, `open_points`.
- Each reading is the one `spine/reading.py` stores or derives, with the evidence word unchanged. A fault prints as a fault.
  Check results print with their declared or exploratory word. No best result is picked.
- The map is facts, never a gate. A line is `done` with its evidence ids, `not yet`, or `not recorded` when linked runs cannot be read.
  A run that is a fault does not count towards a map line.
  - Examples: a setup find is linked. Controls: a setup study of a linked find, or a stored random-data test.
  - Baseline: an aim row in a reading. Settings: stored variants tried, or more than one setting of the same rule linked.
  - Costs: a stored `costs.break_even` result. Out-of-sample numbers recorded: stored out-of-sample numbers; this is not an independent replication.
  - A setup study that cannot be read does not count. The study sentence prints; its outcome word does not (old wording), and the page says so once.
  - Held-back confirmation and following forward on paper read `not built yet`. The forward-use code is not read.
- Text caps at 20 readings: the first 10 and last 10 print, the middle is counted. `--json` carries all.
- Text for the owner never prints a letter grade, "supported", "rejected", "pass", "fail" or "profit". A scan test holds this.

## Report, cite and the gates

- `alpha report <run>` prints `reading: <word> (old grade: X)` for a gauntlet run: the stored reading's word, or one derived from the stored
  numbers, with the old letter muted after it. A manifest with a grade but no numbers prints `reading: not recorded (old grade: X)`.
  The lines `verdict: PASS/FAIL`, `grade:`, `null[...] -> PASS/FAIL` and `gate[...]: PASS/FAIL` are gone. Manifest and `--json` keep every field.
- A Monte Carlo family prints its stored percentiles and the share of paths below zero: no risk grade, no stage status word.
- `alpha results cite <run> verdict` prints the evidence word, then `(old grade: X)`, on one line. `--json` keeps the letter.
  `cite <run> evidence` gives the word alone (`fault` for a fault; derived for an old run). Both are in `spine/facts.py`.
- A stored basis that says "realized profit" is shown as "realized gain or loss" by `plain_basis`. No stored file is rewritten.
- The gate classes below are the one home. A FACT gate keeps a state word. A STAT gate shows its numbers and the plain comparison,
  then the old level, muted, as "the level used by the old grade". A TASTE level is only a number, against the aim when one exists.

| Gate | Class | `alpha report` line |
|---|---|---|
| `walk_forward_oos` | FACT | sound with the Sharpe (the Workstation says "computed"); fault if it could not be computed; not checked if absent |
| `randomized_price_null` | STAT | share of random runs that did as well, per tier; old level 0.95 |
| `bootstrap_ci` | STAT | the Sharpe interval; it includes zero, is above zero or is below zero |
| `deflated_sharpe` | STAT | the deflated Sharpe and the number of tries counted; old level 0.95 |
| `cpcv_oos` | STAT | mean Sharpe across folds and the share of folds above zero |

- Standard trading terms stay: profit factor (gross gains divided by gross losses), P&L, realized profit, take-profit. The rule is to never promise
  or imply profit. The word scans look for promise phrases (will profit, profitable, make money, guaranteed), not the bare word.
- The drawdown, ruin, Sharpe and sample-size bands of the old grade are TASTE or STAT levels of the grade itself. No screen or line prints them as a result.
- `alpha validate` prints `reading <evidence word>` from the shared reading code, with the OOS Sharpe and the null percentiles.
- `alpha backtest holdout` and `alpha optim grid|mcpt` print no PASS/FAIL. Each old word judged a result against a level (a taste or stat
  level, not a fact about a rule), so the line gives the number, the plain comparison and "The level used by the old grade: X".
  The holdout line compares the Sharpe with `--min-sharpe`; `optim grid` names deflated Sharpe, PBO and SPA levels; `optim mcpt` the
  percentile level. Manifests keep `passed`. A prop-firm challenge is passed or failed by its own rules; "pass probability" stays.
- The Workstation walk-forward card counts windows once, in `foldCounts` (`explain/gates.ts`). With a window that has no Sharpe it says
  "N windows. A were above zero, B were at or below zero, and C had no Sharpe recorded"; the manifest stores no cause per fold, so none is
  stated. The chip reads "A of N (C with no Sharpe)". The CLI prints no walk-forward above-zero count.
- The HTML tear sheet is written by `alpha_validation/tearsheet.py` and still prints the old PASS/FAIL words. It is not changed here.
