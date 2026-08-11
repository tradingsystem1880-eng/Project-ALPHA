# Data Discovery

**Protocol id:** `data-discovery` · **Packet kind:** `research_case`

## Purpose
Establish which already-governed data can answer the research question, and name the real gaps
instead of assuming availability.

## Method
1. From the packet's chart fingerprint, list the exact instruments, sessions, bar durations, and
   date ranges the hypothesis needs.
2. Inventory what exists: stored symbols, source status and qualification state, snapshots, and
   provider capabilities (data-inventory tools; before they ship, the packet's availability
   markers say what cannot be checked yet).
3. For each candidate dataset note: source authority (authoritative vs comparison-only), raw vs
   adjusted semantics, calendar coverage, known quality flags, and point-in-time validity.
4. Identify gaps precisely: missing symbols, insufficient history, wrong granularity, unqualified
   sources. State what acquiring each would take under the governed adapters.
5. Never treat scratch or unqualified data as if it were canonical; say which lane it is in.

## Output contract
A dataset-candidates-and-gaps note (`completeness_review`) plus, where a candidate is viable, a
registration proposal for the owner (`alpha research data register` once the data plane ships).

## Boundaries
No fetching, no downloads, no network. Discovery reads inventories; acquisition stays behind
receipts and owner action.
