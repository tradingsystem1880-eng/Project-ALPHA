# Data Audit

**Protocol id:** `data-audit` · **Packet kind:** `asset`

## Purpose
Validate that a registered dataset is fit for the hypothesis before any analysis touches it —
data quality failures found after results exist contaminate everything downstream.

## Method
1. From the asset packet, read the dataset's provenance: source, receipts, qualification state,
   snapshot hashes, and any recorded quality findings.
2. Plan descriptive checks that cannot leak future information: coverage vs the expected session
   calendar, gap structure, duplicate/disorder detection, distributional sanity (returns, ranges,
   volumes), split/dividend consistency, and stationarity red flags.
3. For intraday data, verify session boundaries, timezone semantics, and bar-construction
   assumptions against the contract's chart fingerprint.
4. Propose the audit as a bounded `run data-audit` descriptive run so results become immutable
   artifacts with lineage, not ad-hoc notebook output.
5. Classify each finding: blocking (dataset unusable for this claim), limiting (usable with a
   stated caveat), or clean. Recommend explicitly.

## Output contract
An audit plan and, after the run, a data-quality review note (`completeness_review`); findings
feed the scorecard's data-quality dimension through recorded artifacts only.

## Boundaries
Audits describe data; they never estimate the hypothesis effect. No repair or mutation — data
problems route to the governed quarantine/repair CLI.
