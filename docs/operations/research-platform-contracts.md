# Research platform contracts

This is the domain-detail companion to [CLAUDE.md](../../CLAUDE.md), extracted during the
2026-09-16 engineering simplification. It records continuing constraints, not a new delivery or
acceptance claim. The [ADR index](../adr/README.md), path rules and cited designs govern changes.

## Data, execution and identity

- Strategies and backtests read through `as_of`. Daily execution uses an open-priced QuoteTick
  at the bar timestamp and a close-stamped decision Bar (+23h); `bar_execution=False` makes quotes
  the fill events. Decide at close t, fill at open t+1 (ADRs 0003, 0005).
- Corporate actions use `announce_date` (otherwise `ex_date`) for knowledge and `ex_date` for price
  application. Known future splits do not rescale current prices. Dividends are engine cash events
  at `pay_date` for the pre-ex holding, including short debits and Tier-2 paths; Tier-1 remains
  price-only. Yahoo split-adjusted OHLCV is reconstructed into raw prices (ADR-0004).
- Seeds normally derive from `AlphaSettings.random_seed` (default 7); v3 stochastic namespaces
  use semantic family/tier/fold/iteration identities, never list positions. Run identity binds
  normalized configuration, snapshot, seed and strategy/execution fingerprints. Completed run
  directories are immutable; matching identity with conflicting bytes fails loudly (ADR-0013).
- Polars is default. pandas is confined to yfinance parsing, QuantStats-Lumi tear sheets and
  the Kronos facade. NumPy/SciPy and deterministic Matplotlib are allowed in research/validation;
  NumPy/Torch may remain within forecast internals. Public forecast values are plain floats/tuples.
  Keep documented mypy overrides for vendor stubs and Nautilus Cython bases.
- Crypto authority is dataset-family/venue-specific: Binance native CEX history, Bybit advanced
  derivatives/options, CoinGecko identity/reference, GeckoTerminal DEX pools and reviewed
  Coin Metrics Community metrics. Coinbase/CCXT is comparison. Never merge USD/USDT/USDC,
  join by ticker alone, synthesize universal prices or silently fall back across evidence/units.
  Existing `ccxt:binance` snapshot/paper warmup bytes remain compatible (ADR-0032).

## Research and control-store boundaries

- Raw observations use the Research Scientist workflow before strategies or hypothesis sweeps.
  Each new project captures a research-required case; only pre-launch projects present during
  the v2 migration are grandfathered. Screening artifacts confer no research-gate authority.
- D0 acceptance readers recompute exact registered evidence and bind its SQLite selector to the
  current manifest. Detector/fixture/power/runtime constant changes require a `_D0_FIXTURE_VERSION`
  bump. Foreign generations receive generation-mismatch errors, not false tampering diagnoses.
  D0 and D1 protocol seeds remain frozen at 7; settings must not alter acceptance recomputation.
- D1 executes the frozen registered plan on discovery data. D2 requires owner approval and reads
  the sealed share once; exact re-execution governs crash recovery. Implementation or data drift
  can contaminate the sealed share; evidence-free or D0-only decisions cannot claim support.
  Promotion requires supported evidence, the owner disposition and the complete linked dossier.
  Gate overrides remain append-only owner events with permanent run watermarks.
- SQLite control schema v5 retains supported historical migrations. Preserve migration writer
  locking, exact checked backups, lossless receipt rebuilds and immutable semantic-event hashes.
  Credential counter, challenge, receipt and semantic event commit atomically. Canonical reads
  verify linkage/transitions in one read snapshot. Missing protected v5 objects fail closed;
  committed-v5 forensic recovery requires owner approval and a forward migration, not healing.
- `alpha-study` owns deterministic projection contracts, not persistence, CLI execution, owner
  decisions, D1/D2 transitions or promotion. Semantic reads are byte-bound and blind to post-cutoff
  identity/clocks/values. Masking and readiness stay server-authoritative, never browser-derived.
- Generated project workspaces contain identifier/hash references, twelve indexes, immutable
  revisions and an atomic current pointer. Explicit quarantine recovery never relocates raw
  evidence, rewrites SQLite or grants authority (ADR-0035).
- Owner Touch ID is separate from actor labels and engineering checks (ADR-0030). Paper acceptance
  requires mechanically verified receipts; legacy producer flags and elapsed time do not pass it.
  No live-capital route exists. Monte Carlo scenario/path-risk evidence cannot establish edge.

## Design navigation

- [Baseline architecture](../superpowers/specs/2026-06-14-project-alpha-v1-design.md)
- [Provider control plane](../superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md)
- [Daily data and IBKR paper](../superpowers/specs/2026-08-03-daily-data-ibkr-paper-hardening.md)
- [Research Scientist program](../superpowers/specs/2026-08-06-research-scientist-program-design.md)
- [Research-first workstation](../superpowers/specs/2026-08-07-research-first-workstation-design.md)
- [Capability and authority inventory](../governance/capability-authority-matrix.md)
- [Provider terms and third-party notices](../governance/2026-07-19-dependency-license-matrix.md)

Path-scoped rules retain the CLI/module maps and implementation-specific commands. Dated delivery
history stays in [BUILD-STATUS.md](../BUILD-STATUS.md); it is not current acceptance evidence.
