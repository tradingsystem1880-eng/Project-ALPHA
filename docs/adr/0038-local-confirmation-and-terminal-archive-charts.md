# ADR-0038: Local action confirmation and terminal archive charts

Status: Accepted by explicit owner direction, 2026-09-30.

Supersedes ADR-0030's mandatory biometric ceremony for ordinary Workstation research actions. The owner requested simple click confirmation and restoration of the Windows-style terminal references.

## Decision

The default UI obtains an expiring, random, single-use confirmation token from the existing closed owner-action challenge endpoint. A native confirmation dialog displays the server-bound action, consequence, project and reason. Perform revalidates the token, payload, artifact and case revision. Semantic receipts and events remain atomic. Domain admission and CLI checks still decide whether an action can run. Cancellation performs no action.

Challenge and perform require the canonical localhost Host and Origin, JSON content type, and same-origin fetch metadata when present. Tokens expire after 60 seconds. This is a trusted local confirmation mechanism, not biometric or cryptographic proof of a human's presence. Local software, same-origin scripts and browser automation can confirm actions. The owner explicitly chose this tradeoff. No new MCP, broker, order, holdout or live-capital authority is added.

ControlStore schema V6 records authorization_method=local_confirmation, a null credential and actor owner:local-confirmation. Historical WebAuthn receipts retain their original fields and gain authorization_method=webauthn. Migration checks an exact verified V5 backup, preserves referenced receipt identities, validates foreign keys and rolls back atomically on failure. Existing WebAuthn enrollment and verification remain compatible optional paths.

The shell uses compact grey Windows-style chrome, workflow tabs and a chart workspace with watchlist/navigation docks. The external archive selector exposes exact dataset windows independently of canonical strategy context. Ordinary discovery uses manifest metadata; opening a chart verifies the selected normalized artifact and raw lineage. Only qualified supported Binance spot and Bybit spot/linear/inverse OHLCV with explicit UTC interval-start conventions and units are accepted. Incomplete bars are excluded at the requested cutoff. Archive history is reconstructed history, not a point-in-time research admission. It cannot silently become a strategy snapshot, paper signal, comparison input or backtest source.

## Verification

Migration preservation, rollback/retry, concurrent migration, single-use races, payload/revision/expiry guards and origin rejection are covered by local-confirmation tests. Archive tests cover selected-artifact/parent integrity and completed-bar cutoffs. Browser checks cover archive identity versus strategy context, volume units, cancellation and owner actions. Current execution evidence belongs in the delivery audit; this ADR alone is not a passing gate receipt.
