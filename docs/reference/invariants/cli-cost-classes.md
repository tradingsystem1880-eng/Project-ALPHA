---
owner: command line runs and validation
sources:
  - apps/alpha-cli/src/alpha_cli/spine/cost_classes.py
  - apps/alpha-cli/src/alpha_cli/spine/spec.py
  - apps/alpha-cli/src/alpha_cli/toolbox/families/costs.py
  - tests/unit/test_cost_classes.py
  - tests/unit/test_cost_classes_pins.py
verified: 0000000000000000
---

# Command line cost classes invariants

Default costs and annualisation by asset class for rule tests. The one home of the numbers is `ROWS` in `spine/cost_classes.py`;
the table below is that text. Every number is a working assumption of the owner's lane, not a venue quote. Not verified.

## Table

| Class | Fee per side | Slippage per side | Borrow per year | Periods per year | Source |
|---|---|---|---|---|---|
| US large ETF | 1 bp | 1 bp | 30 bp | 252 | Fee: the old flat default. Slippage: about half the spread of a liquid fund. Borrow: easy-to-borrow fund. |
| US stock | 2 bp | 5 bp | 50 bp | 252 | Fee: small-order regulatory and exchange fees. Slippage: spread and impact of a mid-cap or small-cap. Borrow: the setup lane (`SHORT_BORROW_BPS_PER_YEAR`). |
| Crypto spot (taker) | 10 bp | 5 bp | none: a spot position cannot be shorted | 365 | The setup lane (`CRYPTO_FEE_BPS`, `CRYPTO_SLIPPAGE_BPS`). |
| Crypto perpetual | 5 bp | 5 bp | 1095 bp (3 bp a day of funding, times 365) | 365 | Fee: a common taker schedule. Funding: the setup lane (`SHORT_CARRY_BPS_PER_DAY`). |

## Rules

- The class comes from the store's dataset identity (`asset_class` and `venue`): US `etf` is the large ETF row, US `stock` the stock row,
  `crypto` the spot row. Without an identity, a slash pair or a crypto provider is crypto spot. Nothing else is read, never the ticker text.
  A perpetual cannot be told from spot in the record, so no asset maps to it today.
- A class that is not known takes the most cautious row (highest cost of one side: crypto spot) and the run is labelled `cost-class-assumed`.
- A spec that states its costs keeps them. Its hash, test key and numbers are as before (`tests/unit/test_cost_classes_pins.py`).
- "No costs stated" cannot be told from "the default stated": both dump `{"fee_bps":1.0,"slippage_bps":2.0}` and share one hash. So a
  spec without costs keeps the flat default of 1 and 2 basis points. Changing it would give old and new results one identity.
- `costs = "class-default"` in a spec asks for the class row. The spec dumps `mode = "class-default"`, so it has its own hash. The run
  is labelled `class-default-costs`, and stores the numbers it used in `spine.costs`. `alpha follow` refuses such a test.
- Every new run stores `spine.costs` (`line`, `fee_bps`, `slippage_bps`, `asset_class`, `periods`) and the reading carries `costs`
  with the `line` and `periods` text. A run from before this change has `line: null` with a reason. `alpha report` prints the line.
- Periods per year: stays derived from the stored bars, snapped to 252 or 365 (`spine/stores.annualisation`, which reads the two
  constants from `cost_classes`). Stock runs are unchanged. The run states which number it used and, when the class is known, the rule.
- `costs.break_even` adds `result_after_borrow`, `borrow_charge` and `borrow_note` for a run with short trades: a plain sum of
  rate x entry value x days held / 365, at the class rate (the highest rate when the class is unknown). A long-only run has none of them,
  with a reason; the value is never zero. The rule-test engine does not short, so this reads runs from the older lane.
