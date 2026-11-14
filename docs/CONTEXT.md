---
owner: documentation
sources:
  - docs/README.md
  - docs/adr/README.md
  - scripts/roadmap_index.py
  - scripts/fs_stale.py
  - tests/unit/test_docs_links.py
  - tests/unit/test_plan_schema.py
verified: bdd1a2a989f8
---

# docs workspace

## Purpose

The project's documentation: the file system's reference material (`docs/reference/`), decision
records (`docs/adr/`), the architecture reference, operations runbooks, governance records, plans
and history. Documents describe the code; they never grant authority. Every fact has one home and
other files link to it.

## Read first

| Read | Section | When |
|---|---|---|
| [documentation invariants](reference/invariants/documentation.md) | — | always |
| [documentation index](README.md) | Lifecycle | always |
| [documentation index](README.md) | Folders | deciding where a new document goes |
| [documentation invariants](reference/invariants/documentation.md) | Decision records | writing or superseding an ADR |
| [documentation invariants](reference/invariants/documentation.md) | Feature plans | writing or closing a plan |
| [command reference](reference/commands.md) | — | documenting a command (link here; never copy it) |
| [what this part is for](reference/project/components/delivery-and-agent-tooling.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

- Reference documents (`docs/reference/**`) and every `CONTEXT.md` follow the contract in
  `tests/unit/test_filesystem_contract.py`: front matter `owner`, `sources`, `verified`; at most 80
  lines for a CONTEXT file and 200 for a reference file; no line over 160 characters; no paragraph
  repeated across files.
- When the code a document describes changes, fix the document and set `verified` to the commit
  you checked it against; `uv run python scripts/fs.py stale` lists the documents to re-check.
- Generated pages are never edited by hand; their commands are listed in
  [docs/README.md § Generated files](README.md#generated-files).
- Check: `uv run pytest -q tests/unit/test_docs_links.py tests/unit/test_filesystem_contract.py`,
  then `uv run python scripts/gate.py check`.

## Outputs

- The one owning document updated, links resolving, generated pages regenerated.
- The owning document for these rules: `docs/reference/invariants/documentation.md`.
