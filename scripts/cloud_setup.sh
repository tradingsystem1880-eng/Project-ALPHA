#!/usr/bin/env bash
# Synchronous root/frontend provisioning; environment-level settings persist separately.
set -Eeuo pipefail
trap 'status=$?; printf "cloud-setup: FAILED at line %s: %s (exit %s)\n" "$LINENO" "$BASH_COMMAND" "$status" >&2; exit "$status"' ERR

if [ "${ALPHA_CLOUD_RDAGENT:-}" = 1 ] && [ "${ALPHA_CLOUD_FOUNDATION:-}" != 1 ]; then
    echo 'cloud-setup: ALPHA_CLOUD_RDAGENT=1 requires ALPHA_CLOUD_FOUNDATION=1' >&2
    exit 1
fi

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${ALPHA_CLOUD_FOUNDATION:-}" = 1 ]; then
    if [ "${ALPHA_CLOUD_RDAGENT:-}" = 1 ]; then
        runtime="$root/.alpha/state/runtime"
        export ALPHA_RDAGENT_PRISTINE="${ALPHA_RDAGENT_PRISTINE:-$runtime/rdagent-pristine}"
        export ALPHA_RDAGENT_SOURCE="${ALPHA_RDAGENT_SOURCE:-$runtime/rdagent-source}"
    fi
    validate_rdagent_input() {
        pin=484776c211e4fbbeef03e0ec00d6bbee7362a4f4
        derived="${ALPHA_RDAGENT_SOURCE:?ALPHA_RDAGENT_SOURCE must name the derived RD-Agent root}"
        head="$(git -C "$ALPHA_RDAGENT_PRISTINE" rev-parse HEAD)"
        if [ "$head" != "$pin" ] || [ -n "$(git -C "$ALPHA_RDAGENT_PRISTINE" status --porcelain)" ]; then
            echo "cloud-setup: $ALPHA_RDAGENT_PRISTINE is not the unmodified pinned commit ($head)" >&2
            exit 1
        fi
    }
    # Explicit full bootstrap may acquire absent source; supplied inputs fail before provisioning.
    if [ -n "${ALPHA_RDAGENT_PRISTINE:-}" ]; then
        (
            cd "$root"
            if [ "${ALPHA_CLOUD_RDAGENT:-}" != 1 ] || [ -e "$ALPHA_RDAGENT_PRISTINE" ]; then
                validate_rdagent_input
            fi
        )
    fi
fi

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/project-alpha-uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-/tmp/project-alpha-uv-tools}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/tmp/project-alpha-xdg}"
export npm_config_cache="${npm_config_cache:-/tmp/project-alpha-npm-cache}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/tmp/project-alpha-playwright-browsers}"
export SEMGREP_VERSION_CACHE_PATH="${SEMGREP_VERSION_CACHE_PATH:-/tmp/project-alpha-semgrep/semgrep_version}"
mkdir -p "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$XDG_CONFIG_HOME" \
    "$npm_config_cache" "$PLAYWRIGHT_BROWSERS_PATH"
mkdir -p "$(dirname -- "$SEMGREP_VERSION_CACHE_PATH")"

for tool in uv npm npx node timeout; do
    command -v "$tool" >/dev/null
done
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

if [ "${ALPHA_CLOUD_FOUNDATION:-}" = 1 ]; then
    # Foundation alone never fetches; explicit RD-Agent provisioning may acquire its fixed pin.
    cd "$root"
    echo 'cloud-setup: Git guards'
    uv run --locked python -B scripts/git_guard.py install
    exclude="$(git rev-parse --git-path info/exclude)"
    mkdir -p "$(dirname -- "$exclude")"
    touch "$exclude"
    for entry in /workers/rdagent/.venv-rule-qualified/ /workers/rdagent/.venv-economics-qualified/; do
        grep -qxF -- "$entry" "$exclude" || printf '%s\n' "$entry" >>"$exclude"
    done

    if [ "${ALPHA_CLOUD_RDAGENT:-}" = 1 ]; then
        runtime="$root/.alpha/state/runtime"
        mkdir -p "$runtime"
        if [ ! -e "$ALPHA_RDAGENT_PRISTINE" ]; then
            pin=484776c211e4fbbeef03e0ec00d6bbee7362a4f4
            partial="$(mktemp -d "$ALPHA_RDAGENT_PRISTINE.partial.XXXXXX")"
            echo "cloud-setup: acquiring pinned RD-Agent in $partial (retained on failure)"
            git init --quiet "$partial"
            git -C "$partial" remote add origin https://github.com/microsoft/RD-Agent.git
            GIT_TERMINAL_PROMPT=0 git -C "$partial" fetch --depth 1 origin "$pin"
            GIT_LFS_SKIP_SMUDGE=1 git -C "$partial" checkout --detach --quiet FETCH_HEAD
            mv -T "$partial" "$ALPHA_RDAGENT_PRISTINE"
        fi
    fi

    if [ -n "${ALPHA_RDAGENT_PRISTINE:-}" ]; then
        pin=484776c211e4fbbeef03e0ec00d6bbee7362a4f4
        echo "cloud-setup: RD-Agent pristine checkout at $pin"
        validate_rdagent_input
        if [ ! -e "$derived" ]; then
            partial="$(mktemp -d "$derived.partial.XXXXXX")"
            cp -a "$ALPHA_RDAGENT_PRISTINE/rdagent" "$ALPHA_RDAGENT_PRISTINE/LICENSE" \
                "$ALPHA_RDAGENT_PRISTINE/pyproject.toml" "$partial/"
            mv -T "$partial" "$derived"
        fi
        uv run --locked python -B -c 'import sys; from pathlib import Path; sys.path.insert(0, "workers/rdagent"); from source_pin import verify_source; print("cloud-setup: RD-Agent source tree", verify_source(Path(sys.argv[1])))' "$derived"
        if [ "${ALPHA_CLOUD_RDAGENT:-}" = 1 ]; then
            echo 'cloud-setup: locked isolated RD-Agent launcher'
            uv sync --locked --project workers/rdagent
        fi
        runtime="$root/.alpha/state/runtime"
        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        mkdir -p "$runtime"
        measure() {
            uv run --locked python -B -c 'import sys; from alpha_cli._native_rule_environment import measure_rule_environment; print(measure_rule_environment(sys.argv[1] == "economics"))' "$1"
        }
        for profile in rule economics; do
            venv="workers/rdagent/.venv-$profile-qualified"
            marker="$runtime/rdagent-venv-$profile.incomplete"
            if [ -e "$marker" ]; then
                # Only a marker this script wrote identifies an owned, never-validated build.
                if [ "$(wc -l <"$marker")" != 1 ] || ! grep -qxE 'build started [0-9]{8}T[0-9]{6}Z' "$marker"; then
                    echo "cloud-setup: $marker was not written by an interrupted build here; inspect it, nothing moved" >&2
                    exit 1
                fi
                if [ -e "$venv" ] && measure "$profile" >/dev/null 2>&1; then
                    echo "cloud-setup: $venv validates despite an interrupted-build marker; kept in place"
                elif [ "${ALPHA_RDAGENT_RETIRE_INTERRUPTED:-}" != 1 ]; then
                    echo "cloud-setup: $venv setup was interrupted ($(cat "$marker")); partial contents are preserved." >&2
                    echo "cloud-setup: rerun with ALPHA_RDAGENT_RETIRE_INTERRUPTED=1 to move them unchanged to $runtime/interrupted/ and build afresh" >&2
                    exit 1
                else
                    retired="$runtime/interrupted/$profile-$stamp"
                    mkdir -p "$runtime/interrupted"
                    mkdir "$retired"
                    [ ! -e "$venv" ] || mv -T "$venv" "$retired/venv"
                    mv "$marker" "$retired/marker"
                    echo "cloud-setup: interrupted $profile environment retired to $retired (not runnable; its paths name $venv)"
                fi
            fi
            if [ ! -e "$venv" ]; then
                flag=""
                [ "$profile" = economics ] && flag="--economics"
                printf 'build started %s\n' "$stamp" >"$marker"
                uv venv --python 3.12 "$venv"
                uv pip install --python "$venv/bin/python" --require-hashes --no-deps \
                    -r "workers/rdagent/$profile-requirements.lock"
                .venv/bin/python -B workers/rdagent/install_rule_profile.py ${flag:+"$flag"}
            fi
            # Every environment, new or existing, is validated against its recorded rule profile.
            identity="$(measure "$profile")"
            if [ -e "$marker" ]; then
                printf 'validated %s identity %s\n' "$stamp" "$identity" >>"$marker"
                mv "$marker" "$runtime/rdagent-venv-$profile.built-$stamp"
            fi
            echo "cloud-setup: qualified $profile environment $identity"
        done
        if [ "${ALPHA_CLOUD_RDAGENT:-}" = 1 ]; then
            echo 'cloud-setup: RD-Agent launcher and closed profiles provisioned; no execution authority or full-suite acceptance'
            printf 'cloud-setup: for later shells: export ALPHA_RDAGENT_SOURCE=%q\n' "$derived"
        fi
    fi

    if [ -e /etc/fonts/conf.d/56-prefer-inter.conf ]; then
        # Stock recipe from README "Linux cloud development setup", verified 2026-10-27.
        echo 'cloud-setup: task-scoped fontconfig without 56-prefer-inter.conf'
        rules="$(for f in /etc/fonts/conf.d/*; do
            [ "${f##*/}" = 56-prefer-inter.conf ] ||
                printf '%s %s\n' "${f##*/}" "$(sha256sum <"$(readlink -f "$f")" | cut -d' ' -f1)"
        done | sort | sha256sum | cut -d' ' -f1)"
        stock="$(sha256sum </etc/fonts/fonts.conf | cut -d' ' -f1)"
        if [ "$stock" != 93a23ba073996edb8b42d6c89ebc2ec5fd2101ce82cb65ba0db358dabf55ca22 ] ||
            [ "$rules" != 8e3428b1839f280d6e6d73dba5c55fdf22c9ea0ee4039499004a6915053322f9 ]; then
            echo "cloud-setup: system fontconfig differs from the verified recipe ($stock, $rules)" >&2
            exit 1
        fi
        cfg="$root/.alpha/state/runtime/fontconfig"
        derive() {
            sed "s#<include ignore_missing=\"yes\">conf.d</include>#<include ignore_missing=\"yes\">$cfg/conf.d</include>#" \
                /etc/fonts/fonts.conf
        }
        expected="$(for f in /etc/fonts/conf.d/*; do
            [ "${f##*/}" = 56-prefer-inter.conf ] || printf '%s %s\n' "${f##*/}" "$(readlink -f "$f")"
        done)"
        if [ -e "$cfg" ]; then
            actual="$(for f in "$cfg"/conf.d/*; do printf '%s %s\n' "${f##*/}" "$(readlink "$f")"; done)"
            if ! derive | cmp -s - "$cfg/fonts.conf" || [ "$actual" != "$expected" ]; then
                echo "cloud-setup: $cfg differs from the verified recipe; inspect it, nothing replaced" >&2
                exit 1
            fi
        else
            mkdir -p "$root/.alpha/state/runtime"
            partial="$(mktemp -d "$cfg.partial.XXXXXX")"
            mkdir "$partial/conf.d"
            while read -r name target; do
                ln -s "$target" "$partial/conf.d/$name"
            done <<<"$expected"
            derive >"$partial/fonts.conf"
            mv -T "$partial" "$cfg"
        fi
        echo "cloud-setup: for later shells: export FONTCONFIG_FILE=$cfg/fonts.conf"
    else
        echo 'cloud-setup: no 56-prefer-inter.conf image rule; system fontconfig used unchanged'
    fi

    if base="$(git rev-parse --verify --quiet refs/remotes/origin/main)"; then
        echo "cloud-setup: refs/remotes/origin/main resolves to $base"
    else
        echo 'cloud-setup: refs/remotes/origin/main does not resolve; not fetched (gate comparison base unavailable)'
    fi
fi
echo 'cloud-setup: ready (root provisioning and browser-runtime smoke only; frontend E2E and full gate remain separate)'
