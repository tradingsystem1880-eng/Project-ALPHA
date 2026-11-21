# Report: model replay bench (m73)

## Answer first
The bench commands are built and tested with a fake model client. Two parts of the brief could not be built:
both live in `workers/**`, which the common rules protect. No real model was called.

## What was built
1. `alpha rdagent bench plan|run|report` (`rdagent_bench_cmds.py`, `_model.py`, `_score.py`).
2. `plan` prints the call count and cost from recorded token counts and your prices. It refuses over 60 calls, 10 USD per run, 50 USD per month.
   It writes and calls nothing. A missing price or token count refuses the plan.
3. `run` stores each output once (exclusive create), so a rerun resumes. It has no ledger or memory option. The store must be outside git.
   The fake client (`--fixture`) needs no network. The real client posts to one local gateway per model; the token comes from `ALPHA_BENCH_GATEWAY_TOKEN`.
4. `report` shows, per model: refusal rate, buildable share, cost per call, median latency. It shows the within-prompt difference per pair
   with the prompt count, and a plain sentence on what 30 pairs can show. No winner label. A missing value shows its reason.
5. Docs: tool card `research/tools/rdagent-model-bench.md`, a section in `rdagent.md` and `cli-native.md`, `alpha next` line, `commands.md` regenerated.

## Decisions
- R1 uses `workers/rdagent/idea_families.py` in a child process (standard library only), so no ALPHA package imports the worker.
  Closed families and dropped names come from `--closed` and `--dropped`.
- R3 is parse and schema only: a proposal needs JSON `name`, `description` and the declared direction, clock and reason; code must parse.
- R4 (prefix check) is named "not run" in every report. It needs `alpha_factor_data.check_prefix_invariance`, the factor runtime and a frozen panel.
- The month cap counts spend recorded in the bench store only. The gateway keeps its own month budget.

## NOT built (protected path `workers/**`)
1. `log_content = true|false` in the run config. The gateway already has `--log-content` (`model_gateway.py:127,805,1248`), but it writes only
   `ts`, instructions, prompt and reply to `content.jsonl`. It does not write stage, model, provider, tokens, cost or latency. The launcher
   `factor_loop_launch.py` has no `--log-content` option, so a config key would put an unknown flag on its command line. Needs a worker change.
2. The stage-label defect. Labels come from `label_calls` (`factor_loop_launch.py:84`). It picks the latest-starting step interval that holds a
   call's timestamp, across ALL loops. When two loops overlap, a call can take the other loop's step. This is my reading from the code only;
   I did not reproduce it, and I did not find the design note the brief names. No fix and no test were written.
   Fix idea for the worker owner: match the call to the loop that made it (carry the loop in the request), then add a test with two overlapping loops.

## Fail-first evidence
`uv run pytest tests/unit/test_rdagent_bench.py` first failed at collection: `No module named 'alpha_cli.rdagent_bench_model'`. It now passes (11 tests):
plan arithmetic, over-cap refusals, missing price and tokens, stage filter, resume, no ledger or memory change, store inside git refused,
paired scoring, refusal rules, null handling, plan writes nothing.
Not tested because the code is not mine to change: recording off by default, stage labels true.

## Commands for your machine (once the worker part exists)
(a) Record prompts on nightly runs: add `log_content = true` to `rdagent.toml`. This does NOT work yet; see item 1 above.
(b) Bench with real models, one gateway per model, prompts exported to `PROMPTS/*.json`:
1. `alpha rdagent bench plan --prompts PROMPTS --models m1,m2 --prices prices.toml --samples 2`
2. `export ALPHA_BENCH_GATEWAY_TOKEN=<gateway token>`
3. `alpha rdagent bench run --prompts PROMPTS --models m1,m2 --prices prices.toml --samples 2 --store ~/alpha-bench --gateway m1=http://127.0.0.1:PORT1 --gateway m2=http://127.0.0.1:PORT2`
4. `alpha rdagent bench report --prompts PROMPTS --models m1,m2 --store ~/alpha-bench --closed "<family>"`

## Unverified
- The real gateway client was never run: its request and response shape (`provider`, `usage`) is assumed OpenAI-style.
- Provider pinning is the gateway's job; the bench only records what the call reports.
- No converter yet from the gateway's `content.jsonl` and `calls.jsonl` to the prompt files.
- The `verified:` stamp on the new tool card is a placeholder; `fs.py stale` will list it.
