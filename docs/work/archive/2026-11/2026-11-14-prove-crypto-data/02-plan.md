# Prove "Download crypto market data" end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-crypto-data`; done when its pull request merges.
**Build class:** standard — six files, test harness plus one provider error message; no read path changes.

Filed straight into the archive, as `2026-11-14-crypto-snapshot-duplicates` was: the
work-in-progress ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A new automatic check downloads crypto data with the real `alpha` program the way you would,
  from a recorded copy of Binance's answers instead of the internet, and reads it back as of a
  date. "Download crypto market data" can now count as Working.
- When Binance does not have a month, the error now says so ("HTTP 404") instead of a bare
  "request failed".
- Nothing for you to decide here.

```json
{
  "schema_version": 1,
  "title": "Prove Download crypto market data end to end",
  "context": "crypto-data is Partial: only in-process tests with monkeypatched fetchers exist. No smoke check can run `alpha crypto-data acquire` offline, because every provider host is pinned (https://data.binance.vision/data/, https://api.binance.com/api/v3) and there is no recorded-provider switch. Python's urllib honours HTTPS_PROXY (CONNECT tunnel) and OpenSSL honours SSL_CERT_FILE, so a loopback CONNECT proxy holding a test certificate authority can answer recorded bytes for the exact pinned URLs with zero product changes.",
  "assumptions": [
    {"statement": "The installed alpha, run with HTTPS_PROXY pointing at a loopback CONNECT proxy and SSL_CERT_FILE at a test CA, downloads a Binance monthly kline archive and its checksum through that proxy with real TLS and the provider's own host checks.", "verified_by": "prototype run on the Dell, 2026-11-14: acquire binance market_bars BTCUSDT --period 2024-01 returned state qualified; an unrecorded month exited 2 with 'Binance archive request failed'"},
    {"statement": "The cloud bulk root refuses /tmp, /var/tmp, /run and /dev/shm (root_identity._DISPOSABLE_ROOTS), so the crypto smoke home must live outside pytest's default temporary directory.", "verified_by": "scripts/storage_settings.py write in /tmp refused: 'cloud bulk root cannot be a disposable temporary directory'"},
    {"statement": "scripts/storage_settings.py write --apply is the step scripts/setup.sh runs to configure a data folder; its reserve floor is 10 GB of real free space.", "verified_by": "scripts/setup.sh lines 176-195; alpha_cli/crypto_bulk_store.py RESERVE_FLOOR_BYTES"},
    {"statement": "cryptography is installed in the root environment (transitive, 49.0.0).", "verified_by": "uv run python -c 'import cryptography'"},
    {"statement": "No code matches the text 'Binance archive request failed'.", "verified_by": "grep over the repository"}
  ],
  "alternatives_considered": [
    "An ALPHA_* environment switch that makes providers read recorded files: rejected, it adds a product path that could label synthetic bytes as Binance data in a real store.",
    "A base-URL override for the Binance hosts: rejected, it loosens the pinned host checks the provider invariants require.",
    "Seeding the store with a test helper as tests/smoke/conftest.py does for stocks: rejected, the download step would not run through the installed program, so the feature would not be proven.",
    "Recording real Binance bytes into the repository: rejected, Binance's terms forbid redistributing the raw files and the repository is public; the recordings are synthetic, Binance-format bytes made in the test."
  ],
  "pre_mortem": [
    "The proxy forwards a request to the real internet: it never opens an outbound socket; a CONNECT to any host other than the recorded ones is refused with 403 and an unrecorded URL is answered 404, and the test asserts the exact list of URLs requested.",
    "The smoke leaves data in the repository's tmp/ folder: the fixture removes its home in a finally block, and the home path is unique per test.",
    "CI's runner has less than the 10 GB reserve free: the store then refuses loudly before any write, so the check fails visibly instead of passing quietly.",
    "The certificate authority leaks into other tests: it exists only in the child process environment of this check."
  ],
  "slices": [
    {"title": "Archive errors name the HTTP status", "verify": "uv run pytest -q tests/unit/test_crypto_binance.py", "expected": "all pass; the new HTTP-status tests fail on main", "rollback": "revert binance.py and its test", "status": "pending"},
    {"title": "Offline recorded provider and the crypto-data smoke check", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_data_smoke.py", "expected": "2 passed", "rollback": "delete the new smoke files and revert _harness.py and conftest.py", "status": "pending"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md", "docs/reference/checks.md", "docs/reference/project/components/data-layer.md", "tests/CONTEXT.md"],
  "out_of_scope": ["apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "apps/alpha-web/src/alpha_web/_catalog.py", "packages/alpha-research/src", "packages/alpha-validation/src", "stored data"],
  "files": [
    "packages/alpha-data/src/alpha_data/crypto/providers/binance.py",
    "tests/unit/test_crypto_binance.py",
    "tests/smoke/_harness.py",
    "tests/smoke/conftest.py",
    "tests/smoke/_recorded_provider.py",
    "tests/smoke/test_crypto_data_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [crypto provider invariants](../../../../reference/invariants/crypto-providers.md) | Shared fetch boundary; Binance | always |
| [command line crypto data](../../../../reference/invariants/cli-crypto-data.md) | Provider-native datasets; Bulk storage | always |
| [smoke harness](../../../../../tests/smoke/_harness.py) | — | always |
| [smoke homes](../../../../../tests/smoke/conftest.py) | — | always |

## Slices

### 1. Archive errors name the HTTP status

In `packages/alpha-data/src/alpha_data/crypto/providers/binance.py`:

- `_fetch_archive_resource` (used by `fetch_binance_checksum` and the non-resumable
  `fetch_binance_archive`) passes `report_http_code=True` to `fetch_bounded`, so an HTTP error
  reads `Binance archive request failed with HTTP 404` (the existing `_wire` wording).
- `_resume_binance_archive`: an `urllib.error.HTTPError` raised by `urlopen` becomes
  `DataError(f"Binance archive request failed with HTTP {exc.code}")` chained from the error,
  instead of "interrupted; rerun to resume". Every other transport error keeps the existing
  "interrupted; rerun to resume" message. Nothing else changes.

Tests first, in `tests/unit/test_crypto_binance.py`, following the file's existing style for
faking `urlopen`: a 404 on the checksum and a 404 on the resumable archive each raise a `DataError`
whose message contains `HTTP 404` and whose `__cause__` is the `HTTPError`; a connection reset
during the resumable download still says "rerun to resume". They must fail on main by assertion.

### 2. Offline recorded provider and the crypto-data smoke check

`tests/smoke/_recorded_provider.py` (new, test-only):

- `RecordedProvider`: a context manager that starts a loopback CONNECT proxy on
  `127.0.0.1:<free port>` in daemon threads and stops it on exit (close the listening socket; join
  threads with a timeout).
- On enter it makes, in a directory the caller names, a throwaway certificate authority and one
  server certificate for `data.binance.vision` and `api.binance.com` (subject alternative names),
  EC P-256, SHA-256, fixed validity 2026-01-01 to 2036-01-01, using `cryptography`. Files: `ca.pem`,
  `server.pem`, `server.key`.
- The proxy accepts only `CONNECT <host>:443` for those two hosts (anything else, including plain
  `GET http://...`, gets `403` and is recorded in `refused`). After `200 Connection established` it
  wraps the client socket in TLS with the server certificate and serves HTTP/1.1 `GET` requests on
  that tunnel with `http.server.BaseHTTPRequestHandler`, keyed by the exact URL
  `https://<host><path>`. It never opens an outbound connection.
- `record(url, body, content_type)` adds an exact response (200, `Content-Length`, no
  compression); an unrecorded URL is answered `404 text/plain` and both are appended to `requests`
  (a thread-safe list of URLs, in order).
- `env()` returns the child-process settings: `HTTPS_PROXY`, `https_proxy`, `HTTP_PROXY`,
  `http_proxy` = `http://127.0.0.1:<port>`; `NO_PROXY` and `no_proxy` = `""`; `SSL_CERT_FILE` =
  the CA file; `SSL_CERT_DIR` = an empty directory beside it (so system roots are not used).
- Synthetic Binance-format builders (module functions, deterministic bytes, nothing real):
  `binance_monthly_klines(symbol, year, month)` returns `(archive_url, zip_bytes, checksum_url,
  checksum_bytes)`: one CSV member `<SYMBOL>-1d-<YYYY>-<MM>.csv`, a fixed `ZipInfo` date, one row
  per UTC day of that month with millisecond open and close times (close = open + 86_400_000 - 1),
  finite prices that change each day, and a sidecar `<sha256>  <file name>\n`. The archive URL is
  built with `alpha_data.crypto.providers.binance.archive_url("spot", "klines", symbol, "1d",
  "YYYY-MM")`. `binance_spot_exchange_info(symbols)` returns exchangeInfo JSON bytes that
  `parse_binance_exchange_info(category="spot")` accepts (read it for the fields it needs).
  `binance_rest_klines(symbol, start_ms, end_ms)` returns REST kline JSON bytes for each day from
  start to end inclusive, and the URL `binance_public_api_url("spot", "klines", {...})` builds for
  the exact parameters `_fetch_binance_tail_pages` sends on its first page (`symbol`, `interval`
  "1d", `limit` 1000, `startTime`, `endTime`).
- A header comment says the bytes are synthetic, made in the test, and why no real Binance bytes
  are recorded (Binance's terms forbid redistribution; the repository is public).

`tests/smoke/_harness.py`: `alpha()` gains a keyword-only `env: Mapping[str, str] | None = None`
merged into `child_env(home, ...)`; `web_server` already takes extras. No other change.

`tests/smoke/conftest.py`: a function-scoped fixture `crypto_home` that creates a unique home
under `<repository root>/tmp/smoke-crypto/` (outside the disposable roots the store refuses;
`tmp/` is git-ignored), creates `data/bulk`, and runs the same step `scripts/setup.sh` runs:
`sys.executable scripts/storage_settings.py write --apply --data-dir <home>/data --bulk-root
<home>/data/bulk --durable-hosting-reference "smoke check home (disposable)" --reserve-gb 10
--decided-by owner --decided-on 2026-11-14 --decision-record "smoke check: ADR-0043 floor"`
(fail with its output if it exits non-zero). It yields the home and removes it in `finally`,
then removes `tmp/smoke-crypto/` if empty. Note in its docstring why the home is not in `/tmp`.

`tests/smoke/test_crypto_data_smoke.py` (new; `pytestmark = [pytest.mark.smoke,
pytest.mark.usefixtures("owned_test_process")]`):

1. `test_binance_listing_archive_and_tail_download_through_recorded_provider(crypto_home)`, with
   one `RecordedProvider` holding the BTCUSDT and ETHUSDT listing, the BTCUSDT January 2024
   archive and a BTCUSDT REST tail for 2024-03-01 to 2024-03-04; every `alpha` call gets
   `env=provider.env()`:
   - `crypto-data catalog --json`: `market_bars` has provider `binance`, role `primary_acquisition`.
   - `crypto-data acquire binance market_membership spot --base NONE --quote NONE --category spot
     --json`: state `qualified`.
   - `crypto-data market-catalog --query BTC --json`: one market, provider symbol `BTCUSDT`.
   - `crypto-data acquire binance market_bars BTCUSDT --base BTC --quote USDT --category spot
     --frequency 1d --period 2024-01 --json`: state `qualified`; keep `normalized_manifest_id`.
   - `crypto-data acquire ... --start 2024-03-01T00:00:00Z --end 2024-03-04T00:00:00Z --json`
     (same instrument options, no period): state `qualified`.
   - `crypto-data coverage --json`: both manifests listed, the archive one with 31 rows from
     2024-01-01 to 2024-01-31, the tail one with 4 rows.
   - `crypto-data quality <archive manifest> --json`: state `qualified`, no failures.
   - `data candles BTCUSDT --manifest-id <archive manifest> --start 2024-01-10 --end 2024-01-12
     --json`: the bars are exactly 10 and 11 January (the 12 January bar closes after the cutoff),
     their open and close equal the recorded rows, and `provenance.quality_status` is `qualified`.
   - `crypto-data acquire ... --period 2024-02 --json` (not recorded): exits 2, output contains
     `HTTP 404`; `coverage --json` still lists exactly two `market_bars` manifests.
   - `provider.requests` is exactly the expected URL list in order and `provider.refused` is empty.
2. `test_workstation_serves_the_downloaded_coverage(crypto_home)`: after the archive download as
   above, `web_server(crypto_home)` serves `GET /api/crypto-data/coverage` with that manifest
   (31 rows, `qualified`) and `GET /api/crypto-data/market-catalog?query=BTC` with `BTCUSDT`. The
   web server needs no provider settings: these routes read the store only.

Do not change product code in this slice. If the installed program does not behave as listed,
stop and report the exact output instead of adjusting the expectation.

## Test plan

Slice 1's tests fail on main. Slice 2 is the end-to-end proof; run it outside any sandbox (it binds
loopback sockets and starts the installed programs). Existing smoke checks must still pass.

## Look-ahead, determinism and import impact

No read path changes. The as-of read in the smoke check asserts that a bar is visible only after
it closes. Recorded bytes are deterministic. Test-only imports of `cryptography` and of
`alpha_data` URL builders; no package import changes.
