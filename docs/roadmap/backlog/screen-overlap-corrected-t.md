# Overlap-corrected t statistic for the quick screen

**Status:** Idea
**Rough size:** S

## Problem / why

`alpha scan hypotheses` reports a plain IC t statistic, mean / sample std times the square root of
the number of dates. For horizons over one row the forward returns of neighbouring dates overlap,
so the daily IC values are strongly autocorrelated and the plain t is inflated by roughly the
square root of the horizon. On the free Yahoo snapshot (16 symbols, 1990-2026, 2026-11-14) the
21-day `vol_63` row shows t = +22.15 and `mom_12_1` t = +14.21; neither is anywhere near that
significant. The output says the overlap is not corrected, but an owner ranking ideas reads the
number, not the caveat.

## What "done" looks like

Each screen row also carries a Newey-West (Bartlett kernel, `horizon - 1` lags) t statistic of the
daily IC series, or the Hansen-Hodrick equivalent, with the lag rule stated in the result; the
plain t stays for continuity. A differential oracle checks it against an independent
implementation (statsmodels is not installed, so the reference is a transcribed formula checked
on a published worked example, or a new pinned test-only dependency the owner accepts).

## Dependencies

None in code (it lives in `apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py`); a dependency
change touches the root `uv.lock`, which is approval-bound while the first real study is pending.

## Sources

- Task record: pull request #171 (its `04-verify.md`)
- Newey and West (1987), Econometrica 55(3), DOI 10.2307/1913610
