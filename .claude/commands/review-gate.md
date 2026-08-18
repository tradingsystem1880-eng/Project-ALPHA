---
description: Independent review of the risk-tier diff, then attest the verdict
---

1. Compute the risk-tier diff: `git diff HEAD` restricted to quant paths plus
   `packages/alpha-backtest/src` and the seven risk-tier `alpha_cli` modules
   (_gauntlet, _optim, _seeds, _identity, _surrogate, _synth, _runner). If
   empty, say so and STOP.
2. Get the current tree hash:
   `uv run python -c "import sys; sys.path.insert(0,'scripts'); import gate; print(gate.compute_tree_hash(gate.repo_root()))"`.
3. Dispatch the `independent-reviewer` subagent with the diff and that tree
   hash — give it the diff only, never your reasoning or justifications (its
   independence is the point). Optionally fold in `invariants-auditor` findings
   as additional input.
4. Pipe the returned ReviewVerdict JSON verbatim to
   `uv run python scripts/gate.py attest --kind review`.
5. On BLOCK: fix every finding, then restart from step 1 for a fresh review.
   BLOCK findings are never argued away, and the reviewer is never re-prompted
   to change its mind about the same diff.
