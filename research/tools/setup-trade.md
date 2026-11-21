---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/setup_trade.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_exits.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_costs.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_controls.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_trade_figure.py
  - apps/alpha-cli/src/alpha_cli/setup_cmds.py
verified: df1f9b55c93b174d
---
# Setup trade

**Reach for it when** the recorded matches are right and the question includes stops or targets.
```text
uv run alpha setup trade <find_id> --json
uv run alpha setup trade <find_id> --recheck --json   # no write; exit 4 if it differs
uv run alpha results cite <trade_id> setup_trade_mean_net_return --json
```
**How to read it** in Workstation → Research → Setup Lab
- In `[exit]`, set `direction` to `"long"` (default) or `"short"`. Stops and targets accept percent,
  ATR distance, or a numeric expression or named reference evaluated at the trigger close.
- Enter at the next open. A short stops above entry and targets below. A stop wins a both-touch bar.
  Stop gaps fill at the worse open. Target gaps fill at the target. An `opposite` condition exits next open.
- `time_bars` exits at the final held bar’s close (default 250, labelled `no-time-exit`). One position per asset.
  Skipped, invalid and still-open entries are counted separately. Only completed trades enter averages.
- Each side pays fees plus slippage in bps: stocks/ETFs 1 + 2, crypto 10 + 5. Unknown markets use crypto costs (`costs-assumed-high`).
- `short-costs-assumed` adds 50 bps/year stock borrow (365 days) or 3 bps/day assumed crypto funding.
  Charge calendar days held, including weekends and an exit day held past its open. Crypto shorts require a perpetual (`short-needs-perpetual`).
- Initial risk is the absolute entry-to-stop distance divided by entry. R is net return divided by that risk.
  Read mean R (expectancy per trade), median R and the share above zero. Without a stop, R is not recorded.
- A result of +0.4 R means that, risking 1% of the account per trade, the average trade made 0.4%. No currency position sizing is simulated.
- Compare the mean with all eligible dates and 2,000 spaced random draws, each half against its own history.
  The uncounted opposite-direction control compares mean return and mean R on exactly the same entries with mirrored exits and its own costs.
- The figure shows entries, net returns, random dates and R. Quote the evidence word and "Setup trade K of N" as for a [study](setup-study.md).
- A new direction or exits counts another trial; a repeat adds none. A find that used reserved bars is refused (`RESERVED_PERIOD_SEEN`).
The trade run checks the inputs again before simulating exits. A failed report requires a reason on this invocation. [Data health](data-health.md)
**What it cannot tell you** Currency position sizing, dividends, actual borrow or funding rates, portfolios or confirmation
on reserved data. Unusual dates are not proof that the setup can be traded.
**Next** Cite the stored reading and labels and inspect the halves before proposing another test.
