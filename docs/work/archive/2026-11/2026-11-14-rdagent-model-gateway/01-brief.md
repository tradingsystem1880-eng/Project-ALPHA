# Give RD-Agent an AI model to talk to

## What the owner wants

"Around 50 usd a month for api credits. That's only if we can't get codex to work in the rd agents
info structure." And, on RD-Agent's models: prefers the ChatGPT subscription with strong models,
with a cheap model on an API key as the fallback, "As long as it doesn't drop quality or
capability" ([owner decisions](../../../reference/project/owner-decisions.md#2026-11-14-rd-agents-ai-models)).

In one sentence: RD-Agent's own model calls go, unchanged, to the Codex program already signed in
with the owner's ChatGPT plan, through a small local connection ALPHA owns, with ALPHA's budget,
honest records of every call, and measured quality.

## What done looks like

- RD-Agent can call a model and an embedding model without any key on disk.
- Every call is recorded (which route, which real model, which settings were honoured or not,
  tokens, time), with no prompt text in the records unless asked for.
- A hard cap on calls per run and per month, and on dollars for the paid fallback (50 US dollars a
  month at most), that stops calls when reached.
- A measured table of answer quality on RD-Agent's own prompts, and a record of how far one real
  RD-Agent step gets through the connection.

## How they will see it

`python workers/rdagent/model_gateway.py status --data-dir <your data folder>` prints the budget;
the decision and the measurements are in ADR-0044 and this task's `04-verify.md`.

## Out of scope

No change to RD-Agent's own code, to how approvals work, to CI, or to the closed synthetic fixture
loops. No research run on real data, no evidence or approval from any model output. The
unofficial LiteLLM ChatGPT route is not built.
