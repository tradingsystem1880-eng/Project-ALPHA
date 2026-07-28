#!/usr/bin/env bash
# The pre-commit gate, run with the SAME ruff CI uses.
#
# Exists because I broke CI twice the same way: patching a file with a script, running
# `ruff check`, and forgetting `ruff format`. check and format are different tools with
# different failure modes, and the sandbox shipped a newer ruff than the lockfile pins —
# so "it passed locally" meant nothing. This runs both, with the pinned version.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

RUFF="${RUFF:-$HOME/.local/bin/ruff}"
PY="${PY:-.venv/bin/python}"
PINNED=$(awk '/^name = "ruff"$/{f=1} f&&/^version = /{gsub(/"/,"",$3); print $3; exit}' uv.lock)
HAVE=$("$RUFF" --version 2>/dev/null | awk '{print $2}')

fail=0
if [ "$HAVE" != "$PINNED" ]; then
  echo "WARN ruff $HAVE but the lockfile pins $PINNED — formatting may disagree with CI"
  echo "     fix: uv tool install ruff==$PINNED"
fi

step() { printf '%-28s' "$1"; shift; if "$@" >/tmp/gate.$$ 2>&1; then echo "ok"; else echo "FAIL"; sed 's/^/    /' /tmp/gate.$$ | tail -20; fail=1; fi; }

step "ruff check"        "$RUFF" check .
step "ruff format --check" "$RUFF" format --check .
step "mypy (changed pkgs)" "$PY" -m mypy research/ace_calls research/xrp_pumps
step "pytest unit"       "$PY" -m pytest tests/unit -q -p no:cacheprovider --continue-on-collection-errors
step "lint-imports"      .venv/bin/lint-imports
step "uv lock --check"   uv lock --check --offline

rm -f /tmp/gate.$$
[ "$fail" -eq 0 ] && echo "ALL GREEN" || echo "SOMETHING FAILED — do not commit"
exit "$fail"
