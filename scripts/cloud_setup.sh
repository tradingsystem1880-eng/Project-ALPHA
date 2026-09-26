#!/bin/bash
# Install every Project ALPHA dependency in a Claude Code cloud session.
#
# Idempotent: a synced tree costs seconds. Launched in the background by the
# `session-start` hook (scripts/claude_hooks.py) and, optionally, by the cloud
# environment's setup script so the environment snapshot carries warm caches.
# No-op outside cloud sessions. See docs/operations/claude-code-harness.md.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
failed=()

step() {
  local name="$1"
  shift
  echo "== cloud-setup: ${name}"
  if "$@"; then
    echo "== cloud-setup: ${name} OK"
  else
    echo "== cloud-setup: ${name} FAILED (exit $?)"
    failed+=("${name}")
  fi
}

frontend_install() {
  cd "${root}/apps/alpha-web/frontend" || return 1
  if [ node_modules/.package-lock.json -nt package-lock.json ]; then
    echo "node_modules is current"
    return 0
  fi
  npm ci --no-audit --no-fund
}

# torch is locked from download.pytorch.org / download-r2.pytorch.org; both hosts
# must be in the environment's allowed domains or this step fails loud.
step "uv sync (workspace)" uv sync --locked --directory "${root}"
step "uv sync (workers/qlib)" uv sync --locked --directory "${root}/workers/qlib"
step "uv sync (workers/literature)" uv sync --locked --directory "${root}/workers/literature"
step "npm ci (frontend)" frontend_install
# Playwright pins its own chromium revision; the image's /opt/pw-browsers copy is older.
step "playwright chromium" bash -c "cd '${root}/apps/alpha-web/frontend' && npx playwright install chromium"

if [ "${#failed[@]}" -gt 0 ]; then
  echo "== cloud-setup: FAILED: ${failed[*]}"
  exit 1
fi
echo "== cloud-setup: all steps OK"
