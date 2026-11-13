# Unified crypto asset picker

**Delivery state:** Completed

The owner found that the primary picker exposes only four canonical symbols while the mounted
archive has 50 instruments and 102 chart series. BTC-USD and BTC/USD are repeated pair labels,
not evidence of identical provider bytes. All available price data must be accessible from the
main picker; exact source, market, quote and native interval remain selectable.

1. Add a pure grouped selection model: one pair row, exact stored/archive child choices, explicit
   base/quote for archives. TDD alias grouping, distinct USD/USDT and manifest preservation.
2. Connect read-only archive discovery to AssetSelect as an opt-in, with visible loading/error
   states and keyboard selection. Keep downloads and strategy inputs canonical only.
3. Make App's existing archive state authoritative for the main chart. Add explicit archive
   navigation; header shows selected venue/interval. Stored/scan/run/profile/project navigation
   clears archive identity; pinned charts remain canonical. Test top selection from another task,
   exact manifest candles/overlays, no fallback on archive errors and return to canonical context.
4. Expose the same selector from Market Watch. Non-price data remains in its typed data views;
   provide an accessible link to all crypto datasets rather than pretending it is OHLCV.
5. Update operating docs before freezing the tree. Build and stage deterministic generated
   output, independent review, then canonical full gate. Do not create reports during the gate.

DAG: frontend orchestration only, reuses CLI-backed discovery and verified chart reads. No data
merge, deletion, statistical change or research/execution authority. Alias grouping is display
only; source symbol and manifest are unchanged. Archive metadata is not artifact verification.

```json
{"feature":"unified-crypto-asset-picker","status":"delivered","slices":["grouped-model","discovery-picker","controlled-chart-navigation","watch-navigation","verification"],"dag_impact":"frontend-only","lookahead":"unchanged-verified-chart-reads","determinism":"exact-symbol-or-manifest-preserved"}
```

Verification: three grouped-model tests, 36 targeted browser journeys across three viewports and
36 document accessibility/visual checks passed. Independent reviewer findings are resolved.
The current live inventory produces 52 groups and retains every one of its 102 archive choices.
Canonical full gate follows this frozen delivery record; no aggregate pass is claimed here.

Full-run correction: the real navigation journey now asserts the asset dialog closes on selection
instead of waiting for its obsolete Done click. First aggregate run passed 264 browser tests;
three instances of that same stale expectation failed and four tests did not run. The corrected
real navigation journey passed all three viewports. A fresh full gate on the corrected frozen
tree is required; prior backend results are not a final-tree stamp.
