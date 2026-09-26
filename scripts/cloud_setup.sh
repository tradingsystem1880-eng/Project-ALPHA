#!/bin/bash
# Install every Project ALPHA dependency in a Claude Code cloud session.
#
# Idempotent: with a warm uv cache a full install takes seconds. Launched in the
# background by the `session-start` hook (scripts/claude_hooks.py) and, optionally,
# by the cloud environment's setup script so the environment snapshot carries warm
# caches. No-op outside cloud sessions. See docs/operations/claude-code-harness.md.
#
#   bash scripts/cloud_setup.sh          install (writes .claude/state/cloud-setup.status)
#   bash scripts/cloud_setup.sh --wait   block until a running install finishes
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
status_file="${root}/.claude/state/cloud-setup.status"

if [ "${1:-}" = "--wait" ]; then
  while [ "$(cat "${status_file}" 2>/dev/null)" = "running" ]; do
    sleep 2
  done
  echo "cloud-setup: $(cat "${status_file}" 2>/dev/null || echo 'never ran')"
  grep '^== cloud-setup' "${root}/.claude/state/cloud-setup.log" 2>/dev/null
  exit 0
fi

mkdir -p "$(dirname "${status_file}")"
echo running >"${status_file}"
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

# torch is locked as `+cpu` from download(-r2).pytorch.org. When the environment's
# network policy blocks those hosts, install everything else exactly as locked and
# the same torch version from PyPI (CUDA build; runs on CPU). `uv sync --locked`
# keeps failing in that mode, which is why the gate's full tier cannot stamp.
workspace_sync() {
  cd "${root}" || return 1
  uv sync --locked && return 0
  local version
  version="$(python3 -c 'import tomllib; d = tomllib.load(open("uv.lock", "rb")); print(next(p["version"] for p in d["package"] if p["name"] == "torch" and "+" in p["version"]).split("+")[0])')" || return 1
  echo "== cloud-setup: FALLBACK torch==${version} from PyPI (pytorch index unreachable)"
  uv sync --locked --no-install-package torch && uv pip install "torch==${version}"
}

frontend_install() {
  cd "${root}/apps/alpha-web/frontend" || return 1
  if [ node_modules/.package-lock.json -nt package-lock.json ]; then
    echo "node_modules is current"
    return 0
  fi
  npm ci --no-audit --no-fund
}

# Playwright pins a chromium revision. When its CDN is blocked, alias the newest
# chromium already in PLAYWRIGHT_BROWSERS_PATH under the pinned revision.
playwright_chromium() {
  cd "${root}/apps/alpha-web/frontend" || return 1
  npx playwright install chromium && return 0
  local browsers="${PLAYWRIGHT_BROWSERS_PATH:-}" rev old
  [ -n "${browsers}" ] || return 1
  rev="$(python3 -c 'import json; print({b["name"]: b["revision"] for b in json.load(open("node_modules/playwright-core/browsers.json"))["browsers"]}["chromium"])')" || return 1
  old="$(find "${browsers}" -maxdepth 1 -type d -name 'chromium-[0-9]*' ! -name "chromium-${rev}" | sort -V | tail -1)"
  old="${old##*-}"
  [ -n "${old}" ] && [ -x "${browsers}/chromium-${old}/chrome-linux/chrome" ] || return 1
  echo "== cloud-setup: FALLBACK aliasing chromium ${old} as ${rev} (Playwright CDN unreachable)"
  mkdir -p "${browsers}/chromium-${rev}" "${browsers}/chromium_headless_shell-${rev}/chrome-headless-shell-linux64"
  ln -sfn "${browsers}/chromium-${old}/chrome-linux" "${browsers}/chromium-${rev}/chrome-linux64"
  ln -sfn "${browsers}/chromium_headless_shell-${old}/chrome-linux/headless_shell" \
    "${browsers}/chromium_headless_shell-${rev}/chrome-headless-shell-linux64/chrome-headless-shell"
  touch "${browsers}/chromium-${rev}/INSTALLATION_COMPLETE" \
    "${browsers}/chromium_headless_shell-${rev}/INSTALLATION_COMPLETE"
}

# The VM's PID 1 never reaps orphans, so killed grandchildren stay zombies and
# process-group liveness checks (tests/unit/test_durable_job_lease.py) see them as
# alive. Run pytest and the gate under `tini -s --`, which reaps them.
install_tini() {
  command -v tini >/dev/null && return 0
  apt-get install -y -q tini || { apt-get update -q && apt-get install -y -q tini; }
}

step "tini (orphan reaper)" install_tini
step "uv sync (workspace)" workspace_sync
step "uv sync (workers/qlib)" uv sync --locked --directory "${root}/workers/qlib"
step "uv sync (workers/literature)" uv sync --locked --directory "${root}/workers/literature"
step "npm ci (frontend)" frontend_install
step "playwright chromium" playwright_chromium

if [ "${#failed[@]}" -gt 0 ]; then
  echo "== cloud-setup: FAILED: ${failed[*]}"
  echo "failed: ${failed[*]}" >"${status_file}"
  exit 1
fi
echo "== cloud-setup: all steps OK"
echo ok >"${status_file}"
