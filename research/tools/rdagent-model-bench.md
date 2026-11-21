---
owner: command line application
sources:
  - apps/alpha-cli/src/alpha_cli/rdagent_bench_cmds.py
  - apps/alpha-cli/src/alpha_cli/rdagent_bench_model.py
  - apps/alpha-cli/src/alpha_cli/rdagent_bench_score.py
verified: 0000000000000000
---

# RD-Agent model replay bench

**Reach for it when** you want to compare candidate models on the same stored RD-Agent prompts before you change the live model.

**Commands** `alpha rdagent bench plan --prompts DIR --models a,b --prices prices.toml --samples 2 [--stages proposal,feedback]`
prints the call count and the cost estimate. It refuses a plan over 60 calls or 10 USD per run, or 50 USD per month. It writes and calls nothing.
`alpha rdagent bench run` (same options, plus `--store DIR` outside git, and `--fixture` or `--gateway model=URL`) sends each prompt to each model.
A stored output is kept, so a second run resumes. `alpha rdagent bench report --prompts DIR --models a,b --store DIR` prints the readings.

**Inputs** A prompt file is JSON: `id`, `stage`, `messages`, `prompt_tokens`, `completion_tokens`. Prices are TOML: `[model]` with
`in_per_mtok` and `out_per_mtok`. A missing price or token count refuses the plan; it never counts as zero.

**How to read it** Each model shows its refusal rate (closed idea family or a repeated dropped idea), its buildable share
(parse and schema checks only), its cost per call and its median latency. The no-future-data prefix check is named as not run.
Each pair shows the within-prompt difference over the prompts both models answered. There is no winner label.

**Limits** 30 pairs can show a large gap, about 3 prompts in 10 or more. They cannot show a small gap, and they say nothing about trading results.
The bench is not a research trial. It has no ledger or memory option and writes only to its store.
**Next** Read the model's own outputs for the prompts where two models differ most, before you trust any rate.
