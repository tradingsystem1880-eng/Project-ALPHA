#!/usr/bin/env bash
# Synchronous root/frontend provisioning; environment-level settings persist separately.
set -Eeuo pipefail
trap 'status=$?; printf "cloud-setup: FAILED at line %s: %s (exit %s)\n" "$LINENO" "$BASH_COMMAND" "$status" >&2; exit "$status"' ERR

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/project-alpha-uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-/tmp/project-alpha-uv-tools}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/tmp/project-alpha-xdg}"
export npm_config_cache="${npm_config_cache:-/tmp/project-alpha-npm-cache}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/tmp/project-alpha-playwright-browsers}"
mkdir -p "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$XDG_CONFIG_HOME" \
    "$npm_config_cache" "$PLAYWRIGHT_BROWSERS_PATH"

for tool in uv npm npx node timeout; do
    command -v "$tool" >/dev/null
done
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
echo 'cloud-setup: locked Python workspace'
uv sync --locked

cd "$root/apps/alpha-web/frontend"
echo 'cloud-setup: locked frontend and pinned Chromium'
npm ci
npx --no-install playwright install chromium

cd "$root"
echo 'cloud-setup: CLI smoke'
timeout 30s uv run --locked alpha info
cd "$root/apps/alpha-web/frontend"
echo 'cloud-setup: Chromium browser-runtime smoke'
timeout 35s node --input-type=module <<'JS'
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
console.log('pinned executable:', chromium.executablePath());
const browser = await chromium.launch({ headless: true, timeout: 15000 });
try {
    const page = await browser.newPage();
    await page.setContent('<title>ALPHA cloud smoke</title><button>Ready</button>');
    await page.getByRole('button', { name: 'Ready' }).click({ timeout: 5000 });
    assert.equal(await page.title(), 'ALPHA cloud smoke');
    console.log('pinned Chromium:', browser.version());
} finally {
    await browser.close();
}
JS
echo 'cloud-setup: ready (root provisioning and browser-runtime smoke only; frontend E2E and full gate remain separate)'
