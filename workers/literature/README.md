# alpha-literature-worker

The one research network surface (ADR-0024): an isolated worker that looks up
scholarly metadata (OpenAlex, Crossref, Unpaywall, arXiv — Google Scholar stays manual) and
fetches open-access or owner-provided documents, driving every URL, redirect, and response
through the fail-closed acquisition primitives (HTTPS-only, IDNA host allowlist, global
addresses only, MIME/size/magic checks). Stored objects are content-addressed with a
`SourceReceipt` labelled `UNTRUSTED_SOURCE`. Pinned `pypdf==6.14.2` extracts bounded,
content-addressed page text; encrypted, malformed, image-only, and truncated documents remain
honest non-evidence states, and document text never carries instruction authority.

Deliberately not a root workspace member (ADR-0016 isolation pattern): own lockfile, no
credential or shell context, no alpha-* imports. `src/literature_worker/_acquisition.py` is a
pinned copy of `apps/alpha-cli/src/alpha_cli/research_acquisition.py`; a repository test fails
loud if the two drift.

Gate: `cd workers/literature && uv lock --check && uv sync --locked && uv run ruff check . &&
uv run ruff format --check . && uv run mypy && uv run pytest -q -m "not network"`.
