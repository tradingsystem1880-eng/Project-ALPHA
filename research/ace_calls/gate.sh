#!/usr/bin/env bash
# The pre-commit gate, run with the SAME ruff CI uses.
#
# Exists because I broke CI three times the same way: patching a file with a script, running
# `ruff check`, and skipping `ruff format`. They are different tools with different failure
# modes, and this sandbox ships a newer ruff than uv.lock pins — so "it passed locally" was
# not evidence of anything.
#
# The pytest step deliberately measures against a BASELINE rather than demanding zero failures.
# This sandbox cannot install torch/typer/nautilus/fastapi (download.pytorch.org is blocked), so
# a pile of collection errors and two torch tests are permanently red here and green in CI. A
# gate that always says FAIL teaches you to ignore it; this one only complains when the count
# moves.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

RUFF="${RUFF:-$HOME/.local/bin/ruff}"
PY="${PY:-.venv/bin/python}"

# Known-red here, green in CI. Update deliberately, never to silence a real regression.
# Re-baselined after the container reset: restoring the workspace's editable installs let far more
# tests collect (errors 61 -> 9), which in turn let more of them run and fail on the deps this
# sandbox still cannot install (torch, nautilus_trader, typer, fastapi). Every one of the 14 is in
# a forecast/kronos/portfolio/optim module; all are green in CI, which has the real dependencies.
BASELINE_FAILED=14
BASELINE_ERRORS=9
# Non-environmental mypy errors under CI's full scope (`mypy packages apps tests`). Almost all are
# `untyped-decorator` from typer being absent here; CI has typer and sees none of them. The count
# is what matters — it must not grow.
BASELINE_MYPY=93

PINNED=$(awk '/^name = "ruff"$/{f=1} f&&/^version = /{gsub(/"/,"",$3); print $3; exit}' uv.lock)
HAVE=$("$RUFF" --version 2>/dev/null | awk '{print $2}')
fail=0

if [ "$HAVE" != "$PINNED" ]; then
  echo "WARN  ruff $HAVE but uv.lock pins $PINNED — formatting may disagree with CI"
  echo "      fix: uv tool install ruff==$PINNED"
  fail=1
fi

step() {
  printf '%-26s' "$1"; shift
  if "$@" >/tmp/gate.$$ 2>&1; then echo "ok"; else
    echo "FAIL"; sed 's/^/    /' /tmp/gate.$$ | tail -15; fail=1
  fi
}

step "ruff check"          "$RUFF" check .
step "ruff format --check" "$RUFF" format --check .
step "mypy research"       "$PY" -m mypy research/ace_calls research/xrp_pumps research/xrp_deep
step "lint-imports"        .venv/bin/lint-imports
step "uv lock --check"     uv lock --check --offline

# CI runs `mypy packages apps tests`; this gate only ran `mypy research/...`, so a type error in a
# new test file sailed straight through to a red CI. Mirroring CI's scope is the whole job of a
# pre-commit gate, and "it passed locally" meant nothing while the scopes differed.
printf '%-26s' "mypy full vs baseline"
mypy_out=$("$PY" -m mypy packages apps tests 2>&1)
got_m=$(grep -E "error:" <<<"$mypy_out" \
        | grep -vcE "import-not-found|import-untyped|Cannot find implementation" || echo 0)
if [ "${got_m:-0}" -le "$BASELINE_MYPY" ]; then
  echo "ok  (${got_m:-0} real errors, baseline $BASELINE_MYPY)"
else
  echo "FAIL  ${got_m:-0} real mypy errors vs baseline $BASELINE_MYPY"
  grep -E "error:" <<<"$mypy_out" \
    | grep -vE "import-not-found|import-untyped|Cannot find implementation" | tail -12 | sed 's/^/    /'
  fail=1
fi

printf '%-26s' "pytest vs baseline"
out=$("$PY" -m pytest tests/unit tests/bias_guards -q -m "not network" \
        -p no:cacheprovider --continue-on-collection-errors 2>&1 | tail -1)
got_f=$(grep -oE '[0-9]+ failed' <<<"$out" | grep -oE '[0-9]+' || echo 0)
got_e=$(grep -oE '[0-9]+ error' <<<"$out" | grep -oE '[0-9]+' || echo 0)
if [ "${got_f:-0}" -le "$BASELINE_FAILED" ] && [ "${got_e:-0}" -le "$BASELINE_ERRORS" ]; then
  echo "ok  (${got_f:-0} failed / ${got_e:-0} errors, baseline $BASELINE_FAILED/$BASELINE_ERRORS)"
else
  echo "FAIL  ${got_f:-0} failed / ${got_e:-0} errors vs baseline $BASELINE_FAILED/$BASELINE_ERRORS"
  echo "    $out"
  fail=1
fi

rm -f /tmp/gate.$$
[ "$fail" -eq 0 ] && echo "ALL GREEN" || echo "SOMETHING FAILED — do not commit"
exit "$fail"
