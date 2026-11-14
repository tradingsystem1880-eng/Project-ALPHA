## What changed for you

- The charts stored with research runs (D0 detector, D1, D2 and the crypto research charts) and
  the charts inside tear sheets now have the same bytes whatever ran earlier in the same Python
  process and whatever a local Matplotlib config file says. Before, once anything restyled
  Matplotlib (QuantStats does when the first tear sheet is made), every later research chart in
  that process came out different, so an evidence hash could depend on process history.
- A clean process makes exactly the same bytes as before: stored figures still verify and no
  renderer version changed.
- **You must re-approve research contracts once.** One file under
  `packages/alpha-research/src` (`rendering.py`) changed behaviour, so the research
  implementation code hash changed. Every research-lane approval made before this change (D1, D2
  and crypto research contracts, scheme 1 and scheme 2) stops verifying until you re-approve it.
  Fixed-rule and daily-rule approvals are not affected; `tearsheet.py` is not approval-bound.
  New research and backtest runs get new run ids (code fingerprints); stored runs keep theirs.

## How to see it

Nothing visible: internal.

## Checks run

From [04-verify.md](04-verify.md): reproduction (one rcParams key, or `import quantstats_lumi`,
changed the research PNG; a matplotlibrc did in a fresh process), test-first failures on the old
source, clean-process bytes identical old vs new (research chart, tear sheet, PNG image data of
every golden flow), `handoff.py` checks including `gate.py check --all`, `gate.py determinism`.
Not run locally: slow oracles (no oracle covers these modules), smoke and browser tests, macOS.

Where it can happen in real use: one `alpha` command per process renders at most one of the two
kinds (only `validate` and the backtest portfolio and cross-sectional commands make tear sheets;
no research command does), the web app renders figures through the CLI subprocess and the MCP
server imports no Matplotlib. So in real use today the trigger was a local matplotlibrc (none on
this machine), and process history mattered in tests and any future long-lived in-process
renderer. `render_figure` was already immune and its figures are a cache, not run artefacts.

Wider scan, same class, non-figure hash-bound artefacts: canonical JSON with sorted keys in every
hashed writer (`_canonical.py`, `gate_packet.py`, research publishers); no set iteration into
outputs; no wall-clock reads in the quant packages; no `setlocale` anywhere and ASCII `strftime`
codes (QuantStats' `%b` stays C locale); time stamps formatted in UTC; Parquet bytes identical
under 1 and 8 Polars threads and another time zone; module caches hold only frozen values.
Residual risk: large square BLAS products differ by thread count; the product's tall-thin
`lstsq` and small `eigh` were identical at 1 and 6 threads.

## Who built and who reviewed

- Builder: Codex `gpt-6-astra`, effort high, class hard, 1 round, 0 fix rounds, no fallback,
  13m03s, 1.94M input tokens (1.86M cached), 14k output. Claude wrote the golden's image-data
  pinning and the two review fixes.
- Reviewers: `quant-verifier` (Opus) PASS; `reviewer` (Opus) APPROVE, one medium and one low
  finding, both fixed; Codex review (`gpt-6-astra`, medium) 0 findings; Claude review found the
  raw PNG digest would tie the golden to every code-hash change, fixed.

## The one document updated

`docs/reference/invariants/research.md` (Figures and charts) and
`docs/reference/invariants/validation.md` (Reports and verdicts), one fact each.

## What I am unsure about

- The tear sheet replays QuantStats' private `quantstats_lumi._plotting.core` module; a QuantStats
  upgrade that moves it fails loudly, and a fresh-process drift test holds the style equal.
- QuantStats asks for Arial first: a machine with Arial (a Mac) renders a different tear sheet.
  Not changed here (cross-machine, would change bytes).

## Protected files touched

None.
