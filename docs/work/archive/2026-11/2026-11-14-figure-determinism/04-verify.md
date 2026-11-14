# Verification: hash-bound figures depend only on their inputs

## Commands run

All in `/home/hunta/alpha-clean-base/wt-det`, branch `m4/figure-determinism`.

- Reproduction on `origin/main` (8d8bcc64), before any change: the reference research chart
  rendered, then `matplotlib.rcParams["xtick.major.size"] = 6.0` (one key), then rendered again:
  sha256 `54e7e068…` became `318e410b…`. `import quantstats_lumi` alone: `54e7e068…` became
  `eef99a53…` (34 rcParams keys change at that import, through `seaborn.set`). A matplotlibrc
  (`MATPLOTLIBRC` holding one line) changed the bytes in a fresh process. `pyplot` or `seaborn`
  imports alone changed nothing. `render_figure` was unchanged under all of these.
- Golden flows on `origin/main`: with `quantstats_lumi` imported first, every research PNG changed
  (detector-validity 60278 → 69649 bytes, d1 87726 → 121436, d2 93496 → 103176).
- `handoff.py build` (commit 330acecc): every check PASS, including `gate.py check --base
  origin/main`, the three slice `verify` commands and `gate.py check --all`.
- Test-first, source reverted to `origin/main` with the new tests in place: 7 of 21 failed by byte
  mismatch (research chart × 4 pollutions, tear sheet × 2, the style drift test); after the
  review fix the tear-sheet pollutions fail 3 of 3 on the old source and the rcParams-leak test
  fails when only the `rc_context()` around the QuantStats import is removed.
- Clean-process bytes, old source vs new, fresh processes: reference research chart
  `18538bf6…` both; tear sheet `7d0caab1…` both; PNG image data (IDAT) of all golden-flow PNGs:
  digest `9cde1f3e…` on old source clean, new source clean and new source after `import
  quantstats_lumi` (old source after that import: `fae0fcf0…`). Confirmed independently by the
  quant verifier and the reviewer.
- `uv run pytest -q -p no:randomly tests/integration/test_tearsheet_html.py
  tests/unit/test_figure_history_determinism.py tests/integration/test_research_cmds_golden.py`
  in one process (tear sheets first): 34 passed.
- `gate.py determinism` (run by the reviewer): 2 passes green over 11 files.
- `gate.py mutate` on both modules and `gate.py check --all` on the last commit: results in the
  pull request.

## End-to-end check

`tests/integration/test_research_cmds_golden.py` runs the research command flows through the CLI
and now pins each PNG's size and the raw sha256 of its image data; it passes alone and after a
tear sheet in the same process.

## Not run

- Slow oracles locally: no oracle covers either touched module (neither is a statistic); CI's
  `quant` job runs them.
- Smoke, browser and web tests: nothing they exercise changed.
- macOS: not available; cross-machine font differences are out of scope.

## Review findings

- Built by Codex (`gpt-6-astra`, effort high, 1 round, no fix rounds, no fallback; 13m03s).
  The golden pixel pinning and the review fixes were written by Claude.
- `quant-verifier` (Opus): PASS; no statistic or shown value changed; clean bytes identical.
- `reviewer` (Opus): APPROVE with two findings, both fixed in 580c5a0f:
  medium — the rcParams-leak test only worked when it was the first QuantStats import in its
  worker; now it runs in a fresh process. Low — the tick-size pollution never reached the tear
  sheet; replaced by facecolour and grid colour.
- Codex review through the bridge (`gpt-6-astra`, medium): 0 findings.
- Claude's own review: the builder's golden change kept the PNG file digest raw, which embeds
  run and contract hashes in its text metadata, so any bound-code or lock change would have
  broken the golden; changed to tokenise that digest and pin the image data instead.
