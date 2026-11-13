# Working style (always loaded)

Project rules: `docs/reference/invariants/engineering.md` § Working style; the steps of a change:
`workflow/CONTEXT.md`.

1. Think first: state assumptions; name competing readings; if unclear, stop and ask.
2. Simplicity: minimum code; no unrequested features, configurability or single-use abstractions.
3. Surgical: touch only what the task needs; match style; remove only orphans you created.
4. Goal-driven: turn the task into a check (failing test first); loop until it is verified.
