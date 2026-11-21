# Brief: cost defaults by asset class, stated on every run

Branch: `feat/m71-costs-by-asset-class`. Rules: `docs/work/_common-rules-2026-11-21.md`. Workspace: `apps/alpha-cli/CONTEXT.md`
(rule-test and costs rows), `docs/reference/invariants/cli-rule-readings.md`, the costs tool card under `research/tools/`.

## Why

An audit found one cost default for every asset: fee 1 basis point and slippage 2 basis points, for a large ETF, a small stock and a
crypto pair alike (backlog note `per-asset-cost-and-annualisation-defaults.md`: find it under `docs/`). A retail swing trader's real
costs differ by asset class, and a result that ignores this reads better than it should.

## Build

1. One table, in ONE new module, of default costs per asset class: US large ETF, US stock, crypto spot (taker), crypto perpetual; each
   row: fee per side, slippage per side, and for shorts a yearly borrow rate; each number with its source in a comment and in the docs
   page. Asset class is taken from the store's asset record (find how `spine/stores.py` / the asset-kind inference label names it); when
   the class is not known, use the most conservative row and label the run `cost-class-assumed`.
2. A rule-test spec that states its own costs keeps them, byte-identical to today (spec hash, test key, numbers: pin with tests BEFORE
   changing code). A spec that states NO costs today uses the old flat default: decide by reading the spec model whether "no costs
   stated" is distinguishable from "default stated"; if it is, new runs of such specs use the class default and carry the label
   `class-default-costs`; old stored runs are never re-labelled. If it is not distinguishable without changing identities, do not change
   behaviour: add the class table, the label for explicit use (`costs = "class-default"`), and report.
3. Every run's reading and `alpha report` state the costs used in one plain line ("Costs: 2 basis points fee and 5 slippage per side,
   the default for a US stock"). The Workstation reading block shows the same line (display only).
4. Periods per year for annualising: the same module names the rule per asset class (252 sessions for stocks, 365 days for crypto) and
   each run states which was used. Find where runs annualise today and make them read this one home; numbers for existing stock runs must
   not change (test).
5. Shorts: no engine change. Add the fact "result after borrow at the class rate" beside the existing break-even cost tool
   (`costs.break_even` in the toolbox) for runs that held short positions; for long-only runs it is absent, not zero.

## Tests

Golden pins for existing specs; the class lookup; the assumed-class label; the cost line in the reading; annualisation unchanged for
stocks and right for crypto; the borrow fact on a synthetic long-short run from the old lane.

## Done

Draft pull request, `ci-ok` green, `report.md` in this folder: the table with sources, the decision on item 2, what is unverified.
