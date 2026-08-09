# New-Idea Intake

**Protocol id:** `new-idea-intake` · **Packet kind:** `research_case`

## Purpose
Turn a raw market observation into research questions — never into trading rules. The owner's
exact wording is already captured; your job is to understand the phenomenon, not to trade it.

## Method
1. Read the paired `research_case` packet: the raw idea verbatim, the provisional thesis, and the
   open material questions.
2. State the tentative falsifiable claim in one sentence: population, condition, outcome, horizon,
   expected direction.
3. Name the candidate mechanism and at least two competing explanations that would produce the
   same surface observation (calendar effects, volatility regimes, survivorship, data artifacts).
4. Search prior internal evidence for the instruments involved (`search_asset_evidence`) and note
   anything that supports, contradicts, or contextualises the idea.
5. Identify what data would be needed to observe the phenomenon point-in-time, and whether the
   event is even knowable when it must be acted on.
6. If (and only if) the instrument, event availability, or outcome definition is materially
   ambiguous, prepare at most one batch of ≤3 closed material questions with the consequence of
   each choice spelled out.

## Output contract
Tentative claim, mechanism, and alternatives land as answers feeding `alpha research draft`;
commentary lands as a `critique` or `test_design` note. Nothing here is evidence.

## Boundaries
Never propose entry rules, stops, targets, position sizing, or parameter values. Never claim the
idea is tradable. An idea that cannot be made falsifiable is reported as such — that is a valid
outcome.
