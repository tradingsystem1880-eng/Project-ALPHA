# Project ALPHA

ALPHA is one person's private, non-commercial quant-research platform: it tests whether a market
idea survives point-in-time data, costs and out-of-sample statistics, and records the owner's
decisions. Python 3.12 with uv; there is no hosting, no distribution and no live trading.

## Never break these

- Every data and strategy read is point-in-time at an aware-UTC `as_of`.
  [Rule](docs/reference/invariants/research-integrity.md#point-in-time-reads)
- Decide on the close of bar t, fill at the open of bar t+1.
  [Rule](docs/reference/invariants/research-integrity.md#decide-at-close-fill-at-next-open)
- Invalid, non-finite or disordered data and degenerate statistics fail loud; never swallow errors.
  [Rule](docs/reference/invariants/research-integrity.md#invalid-data-fails-loud)
- Runs, snapshots, receipts and admitted evidence are immutable and hash-bound.
  [Rule](docs/reference/invariants/research-integrity.md#immutable-hash-bound-artefacts)
- Seeds and execution fingerprints are deterministic; D0/D1 seeds are frozen.
  [Rule](docs/reference/invariants/research-integrity.md#deterministic-seeds-and-identity)
- Research before strategy; only the owner promotes, on verified evidence.
  [Rule](docs/reference/invariants/research-integrity.md#research-before-strategy)
- Owner acts need explicit local owner confirmation; no route reaches live capital.
  [Owner](docs/reference/invariants/research-integrity.md#owner-authority),
  [capital](docs/reference/invariants/research-integrity.md#no-live-capital)
- UI, MCP, model output, account state and passing checks confer no authority; infer no approvals.
  [Rule](docs/reference/invariants/research-integrity.md#owner-authority)
- Obey the layered import DAG (`uv run lint-imports`); web and MCP call `alpha_cli` as a subprocess.
  [DAG](docs/reference/invariants/engineering.md#import-layers),
  [subprocess](docs/reference/invariants/engineering.md#subprocess-boundary)
- Never weaken bias guards, oracles or the guarded `tests/holdout/` path to make a change pass.
  [Rule](docs/reference/invariants/research-integrity.md#protected-and-hidden-tests)
- Bytes under `packages/alpha-research/src` and `packages/alpha-validation/src` feed approval
  hashes and the quant tier: no cosmetic edits.
  [Bytes](docs/reference/invariants/engineering.md#hash-bound-source-bytes),
  [tier](docs/reference/invariants/engineering.md#quant-tier)

## Check and land

- One check: `uv run python scripts/gate.py check`.
- Loop: branch → check → commit (`type(scope): summary`) → pull request → CI green → merge commit.
  CI on the pull request is the merge gate ([ADR-0039](docs/adr/0039-ci-is-the-merge-gate.md)).

## Start here

Start at [`CONTEXT.md`](CONTEXT.md): it routes your task to one workspace, whose `CONTEXT.md`
names exactly what to read (Claude Code also loads it when you open a file in that workspace).
Why each part exists and what the owner decided: the [project layer](docs/reference/project/overview.md).
Each fact has one home, listed in `CONTEXT.md`: update that document, never copy the fact.
`uv run python scripts/fs.py orient` lists the areas, `fs.py search "words"` finds documents,
`fs.py stale` lists documents whose sources changed since they were verified.
