# Report: costs by asset class (M71)

## Decision on item 2
"No costs stated" is NOT distinguishable from "the default stated". `Costs` always dumps `{"fee_bps":1.0,"slippage_bps":2.0}`, so a spec without costs and one that
states 1 and 2 share one hash, one test key and one run identity (pinned in `tests/unit/test_cost_classes_pins.py::test_default_and_stated_default_are_one_spec`).
So behaviour is unchanged: a spec without costs keeps the flat 1 and 2. I added the table, the label for explicit use and the lines.

## What changed
1. `spine/cost_classes.py`: the table (`ROWS`), the class lookup (`asset_class`), the most cautious row, the cost and periods lines, the borrow fact.
2. `costs = "class-default"` in a spec. The spec dumps `mode = "class-default"` and so has its own hash. The run takes the class row, is labelled
   `class-default-costs` (plus `cost-class-assumed` when the class is unknown) and stores the numbers in `spine.costs`.
   `alpha follow` refuses such a test (it needs stated costs); the toolbox replay reads the stored numbers.
3. Every new run states "Costs: ..." and the periods per year in its reading (`reading.costs`), in `alpha test` and `alpha results show` text, in `alpha report`
   and in the Workstation reading block (display only). A run from before this change shows "not recorded" with a reason.
4. Annualisation: still derived from the stored bars and snapped to 252 or 365; the snap constants now come from `cost_classes`. Stock numbers do not change
   (pinned). The run says which number it used and, when the class is known, the rule.
5. `costs.break_even` gains `result_after_borrow`, `borrow_charge`, `borrow_note`. They are absent (null with a reason) for a long-only run. The rule-test engine
   does not short, so this reads runs from the older lane. The golden `tests/fixtures/toolbox_run_level_checks.json` got the three new keys; no old value moved.

## Table (numbers per side; every number is an assumption, not a quote)
| Class | Fee | Slippage | Borrow a year | Periods | Source |
|---|---|---|---|---|---|
| US large ETF | 1 bp | 1 bp | 30 bp | 252 | fee: old flat default; slippage: half a spread of a liquid fund; borrow: easy to borrow |
| US stock | 2 bp | 5 bp | 50 bp | 252 | fee: small-order regulatory fees; slippage: mid/small-cap spread and impact; borrow: setup lane |
| Crypto spot (taker) | 10 bp | 5 bp | none (cannot short spot) | 365 | setup lane constants |
| Crypto perpetual | 5 bp | 5 bp | 1095 bp (3 bp a day x 365) | 365 | fee: common taker schedule; funding: setup lane |

## Fail-first evidence
- Pins (`test_cost_classes_pins.py`) passed on the old code before any change (commit 9fd5299).
- `test_cost_classes.py` first failed at collection: `ImportError: cannot import name 'costs_line' from 'alpha_cli.spine.report_readings'`, then failed on the
  missing module, spec value and borrow outputs until each was built.

## Unverified / limits
- No number in the table was checked against a broker or venue schedule (no network or keys). Treat them as working assumptions.
- A perpetual cannot be told from spot in the store record, so no asset maps to the perpetual row today. Crypto reads as spot (higher fee).
- An equity source without a dataset identity does not say stock or ETF, so it is "assumed" (most cautious row, crypto spot). That is cautious, not accurate, for a stock.
- The borrow charge is a plain sum (rate x entry value x calendar days / 365), not compounded; entry value is derived from stored pnl / return.
  An unknown class takes the highest borrow rate (the perpetual's).
- Fixture and golden change for `costs.break_even` is an output addition. The frontend line was tested with vitest; no browser check.
- `fs.py stale` lists documents whose sources changed; per the rules I did not verify them.
