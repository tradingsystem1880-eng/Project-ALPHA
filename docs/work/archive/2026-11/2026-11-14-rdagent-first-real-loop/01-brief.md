# One real RD-Agent loop, end to end

## What the owner wants

The first goal after the clean-up: one real RD-Agent loop, connected to a model through Codex,
that proposes one idea, builds it, backtests it and judges it, with every step actually executed
([owner decisions](../../../../reference/project/owner-decisions-2.md#2026-11-14-first-goal-one-real-rd-agent-loop)).
On the same day the owner accepted losing RD-Agent's "temperature" setting on the Codex route
"For now" ([log](../../../../reference/project/owner-decisions-2.md#2026-11-14-accept-losing-temperature-on-the-codex-route-for-now));
the paid route stays off.

The earlier attempt ([gateway verification](../2026-11-14-rdagent-model-gateway/04-verify.md))
stopped at the backtest step because Qlib was not installed, and coded on made-up data.

## What done looks like

- RD-Agent's own factor loop (pinned `484776c`, unmodified) runs propose, code, run (Qlib
  backtest), feedback and record once, through the model gateway, within its budget caps
  (60 calls and 10 USD per run).
- It runs on real data: the 15 coins of Binance daily bars already on the Dell, read only.
- Every step is real: no stand-in step, no supplied answer. Whatever it produces is labelled
  exploratory, not admitted and not yet confirmed.
- An honest account of what the backtest measured, and what stands between this and a routine loop.

## Out of scope

Changing RD-Agent, its templates or ALPHA's research guards; admitting or promoting anything;
the paid route; ALPHA's own Qlib worker ("W09") and Nautilus backtests of RD-Agent ideas.
