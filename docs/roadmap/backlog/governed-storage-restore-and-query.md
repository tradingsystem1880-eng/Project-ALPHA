# Governed storage restore and query for real-data native studies (W19)

**Status:** Scoped
**Rough size:** L

## Problem / why

The first real-data native investigation (W08) needs qualified storage: typed query receipts,
atomic publication, catalog-plus-artifact restore and a bounded workload performance check.
Immutable snapshots and bounded query foundations exist; restore, publication and parity are open.
The real-data study itself is tracked by the live Packet 3 plan, which is blocked on legitimate
durable hosting and admitted retained storage.

## What "done" looks like

W19a–W19c bounded first-slice qualification: ownership, typed query receipts, atomic publication,
catalog-plus-artifact restore and a passing bounded workload, without assuming an engine/server
migration.

## Dependencies

W01–W04 for design; W05 qualified fixtures for numerical acceptance.

## Sources

- [Checklist W19](../../archive/research-notes/feature-readiness-checklist-2026-10-27.md#w19-qualify-data-storage-and-governed-queries)
- [Checklist: Governed storage subpackets](../../archive/research-notes/feature-readiness-checklist-2026-10-27.md#governed-storage-subpackets)
- [Checklist Packet 3](../../archive/research-notes/feature-readiness-checklist-2026-10-27.md#packet-3-complete-one-real-native-rule-and-control-study)
- [Packet 3 daily rule plan](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/2026-10-31-packet3-daily-rule/02-plan.md)
