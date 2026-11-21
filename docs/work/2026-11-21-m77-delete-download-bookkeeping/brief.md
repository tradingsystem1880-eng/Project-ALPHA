# Brief: delete the download bookkeeping code

Branch: `chore/m77-delete-download-bookkeeping`. Rules: `docs/work/_common-rules-2026-11-21.md` (deletion-only build).

The owner decided on 2026-11-21 to delete the download bookkeeping (receipt and quota accounting for data downloads): no command passes it.

Delete (verify each first): `apps/alpha-cli/src/alpha_cli/_crypto_http_replay.py`, `_crypto_http_accounting.py`,
`_crypto_backfill_accounting.py`, `_market_data_acquisition_accounting.py`; their tests (`tests/integration/test_bound_http_replay*.py`,
`test_accounted_*`, `test_complete_http_accounting.py`, `test_market_data_acquisition_*`); the optional accounting parameters that no
command passes in `_crypto_backfill.py` (around lines 29-35 and 432-454) and the one import in `crypto_data_cmds.py` (around line 54: if it
imports an exception type that live code raises or catches, move that one type to the module that uses it); the capability
`download-bookkeeping` in `docs/roadmap/capabilities.toml`; the rows in `docs/ARCHITECTURE.md` and other docs. The data download commands
themselves must behave exactly as before: run their tests, and add one test that a backfill with no accounting argument gives the same
result as on main.

Done: as in brief m76.
