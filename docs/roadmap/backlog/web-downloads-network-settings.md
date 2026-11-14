# Web-started downloads ignore proxy and certificate settings

**Status:** Idea
**Rough size:** S

## Problem / why

Found on 2026-11-14 while proving `crypto-data` end to end. The Workstation starts every `alpha`
command with a short allowlist of environment settings (`apps/alpha-web/src/alpha_web/_catalog.py`,
`_cli_environment`). That list has no `HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY`, `SSL_CERT_FILE` or
`SSL_CERT_DIR`. A download that works from the command line on a machine that needs a proxy or a
company certificate bundle therefore fails when started from the Crypto Data Center page, and the
smoke check cannot send a web-started download through the offline recorded provider (it proves
the page's read routes only).

## What "done" looks like

- Commands that call a provider (`crypto-data acquire`, `backfill`, `profile-run`,
  `profile-resume`, `data pull`) receive those five settings; no other command does.
- A proxy address that carries a user name or password is never logged or echoed in a job record.
- The crypto-data smoke check adds a web-started acquisition through the recorded provider.

## Dependencies

A decision that network-routing settings may cross the web-to-command boundary (it is a security
boundary; today only named provider keys do).
