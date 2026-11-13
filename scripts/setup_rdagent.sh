#!/usr/bin/env bash
# Provision the pinned RD-Agent runtime on a local Linux development checkout, idempotently.
#
# Does the RD-Agent part of `ALPHA_CLOUD_FOUNDATION=1 ALPHA_CLOUD_RDAGENT=1 scripts/cloud_setup.sh`
# without its cloud-only steps (Git hook install, npm ci, Chromium download, fontconfig): fetches
# the single pinned upstream commit when absent, derives the source root, verifies the source-tree
# digest, syncs the locked worker launcher and builds/validates the two closed rule profiles from
# their hash-pinned locks. Nothing is downloaded except that commit and locked packages. It makes
# no model call, reads no .env and grants no execution authority. It prints the exports to use.
set -Eeuo pipefail
trap 'status=$?; printf "setup-rdagent: FAILED at line %s: %s (exit %s)\n" "$LINENO" "$BASH_COMMAND" "$status" >&2; exit "$status"' ERR

pin=484776c211e4fbbeef03e0ec00d6bbee7362a4f4
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runtime="$root/.alpha/state/runtime"
pristine="${ALPHA_RDAGENT_PRISTINE:-$runtime/rdagent-pristine}"
derived="${ALPHA_RDAGENT_SOURCE:-$runtime/rdagent-source}"
cd "$root"

check_pristine() {
    local head
    head="$(git -C "$pristine" rev-parse HEAD)"
    if [ "$head" != "$pin" ] || [ -n "$(git -C "$pristine" status --porcelain)" ]; then
        echo "setup-rdagent: $pristine is not the unmodified pinned commit ($head)" >&2
        exit 1
    fi
}

# Supplied inputs are checked before anything is installed or fetched.
[ ! -e "$pristine" ] || check_pristine
for tool in git uv; do
    command -v "$tool" >/dev/null
done

echo 'setup-rdagent: locked root environment'
uv sync --locked

mkdir -p "$runtime"
if [ ! -e "$pristine" ]; then
    partial="$(mktemp -d "$pristine.partial.XXXXXX")"
    echo "setup-rdagent: fetching RD-Agent $pin into $partial (kept on failure)"
    git init --quiet "$partial"
    git -C "$partial" remote add origin https://github.com/microsoft/RD-Agent.git
    GIT_TERMINAL_PROMPT=0 git -C "$partial" fetch --quiet --depth 1 origin "$pin"
    GIT_LFS_SKIP_SMUDGE=1 git -C "$partial" checkout --detach --quiet FETCH_HEAD
    mv -T "$partial" "$pristine"
fi
check_pristine
echo "setup-rdagent: pristine checkout $pristine at $pin"

if [ ! -e "$derived" ]; then
    partial="$(mktemp -d "$derived.partial.XXXXXX")"
    cp -a "$pristine/rdagent" "$pristine/LICENSE" "$pristine/pyproject.toml" "$partial/"
    mv -T "$partial" "$derived"
fi
# Upstream's top-level test/ package shadows the standard library, so only rdagent/ is derived.
uv run --locked python -B -c 'import sys; from pathlib import Path; sys.path.insert(0, "workers/rdagent"); from source_pin import verify_source; print("setup-rdagent: source tree digest", verify_source(Path(sys.argv[1])))' "$derived"

echo 'setup-rdagent: locked isolated RD-Agent launcher (workers/rdagent/.venv)'
uv sync --locked --project workers/rdagent

measure() {
    uv run --locked python -B -c 'import sys; from alpha_cli._native_rule_environment import measure_rule_environment; print(measure_rule_environment(sys.argv[1] == "economics"))' "$1"
}
for profile in rule economics; do
    venv="workers/rdagent/.venv-$profile-qualified"
    marker="$runtime/rdagent-venv-$profile.incomplete"
    if [ -e "$marker" ]; then
        echo "setup-rdagent: $venv build was interrupted ($marker); nothing moved." >&2
        echo "setup-rdagent: recover it with scripts/cloud_setup.sh's ALPHA_RDAGENT_RETIRE_INTERRUPTED=1 rule" >&2
        exit 1
    fi
    if [ ! -e "$venv" ]; then
        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        printf 'build started %s\n' "$stamp" >"$marker"
        uv venv --quiet --python 3.12 "$venv"
        uv pip install --quiet --python "$venv/bin/python" --require-hashes --no-deps \
            -r "workers/rdagent/$profile-requirements.lock"
        if [ "$profile" = economics ]; then
            .venv/bin/python -B workers/rdagent/install_rule_profile.py --economics
        else
            .venv/bin/python -B workers/rdagent/install_rule_profile.py
        fi
        identity="$(measure "$profile")"
        printf 'validated %s identity %s\n' "$stamp" "$identity" >>"$marker"
        mv "$marker" "$runtime/rdagent-venv-$profile.built-$stamp"
    fi
    echo "setup-rdagent: qualified $profile environment $(measure "$profile")"
done

stock="${ALPHA_STOCK_PYTHON:-}"
echo 'setup-rdagent: done; provisioning only, no execution authority or research admission'
printf 'export ALPHA_RDAGENT_SOURCE=%q\n' "$derived"
if [ -n "$stock" ] && [ -x "$stock" ]; then
    printf 'export ALPHA_STOCK_PYTHON=%q\n' "$stock"
else
    # Stock RDLoop needs upstream's full dependency set (docker, litellm, openai, tiktoken, ...);
    # the repository has no lock for it, so it is not installed here.
    echo '# ALPHA_STOCK_PYTHON: not provisioned (no committed lock for the stock runtime bundle)'
fi
