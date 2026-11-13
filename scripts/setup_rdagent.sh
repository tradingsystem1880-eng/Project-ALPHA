#!/usr/bin/env bash
# Provision the pinned RD-Agent runtime on a local Linux development checkout, idempotently.
#
# Does the RD-Agent part of `ALPHA_CLOUD_FOUNDATION=1 ALPHA_CLOUD_RDAGENT=1 scripts/cloud_setup.sh`
# without its cloud-only steps (Git hook install, npm ci, Chromium download, fontconfig): fetches
# the single pinned upstream commit when absent, derives the source root, verifies the source-tree
# digest, syncs the locked worker launcher and builds/validates the two closed rule profiles from
# their hash-pinned locks. Nothing is downloaded except that commit and locked packages. It makes
# no model call, reads no .env and grants no execution authority. It prints the exports to use.
#
# Optional, off by default so the default install stays small:
#   --with-daily-container  pull the one Docker base image pinned by digest for the daily study
#                           (python:3.12-slim, ~120 MB) and run qualify_daily_container.py, which
#                           writes .alpha/state/runtime/daily-container.json.
#   --with-stock-runtime    build the closed Python 3.11 stock RDLoop runtime bundle from
#                           workers/rdagent/stock-requirements.lock (60 hash-pinned packages,
#                           ~230 MB) and record it with workers/rdagent/install_stock_profile.py.
set -Eeuo pipefail
trap 'status=$?; printf "setup-rdagent: FAILED at line %s: %s (exit %s)\n" "$LINENO" "$BASH_COMMAND" "$status" >&2; exit "$status"' ERR

pin=484776c211e4fbbeef03e0ec00d6bbee7362a4f4
# Daily study base image: the repository digest and the image ID it must produce (packet3 plan).
daily_digest=sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
daily_image=sha256:ae4e8b7c575fabea88a029b6cae757f342ca2525e07f7c22272d5105c346b35e
with_daily=0
with_stock=0
for argument in "$@"; do
    case "$argument" in
        --with-daily-container) with_daily=1 ;;
        --with-stock-runtime) with_stock=1 ;;
        *) echo "setup-rdagent: unknown option $argument" >&2; exit 2 ;;
    esac
done
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

if [ "$with_daily" = 1 ]; then
    command -v docker >/dev/null
    image_id() { docker image inspect --format '{{.Id}}' "python@$daily_digest" 2>/dev/null; }
    if ! image_id >/dev/null; then
        echo "setup-rdagent: pulling python@$daily_digest (the only image this downloads)"
        docker pull --quiet "python@$daily_digest" >/dev/null
    fi
    if [ "$(image_id)" != "$daily_image" ]; then
        echo "setup-rdagent: python@$daily_digest is not image $daily_image; not qualified" >&2
        exit 1
    fi
    echo "setup-rdagent: qualifying daily container image $daily_image (offline import smoke)"
    uv run --locked python -B workers/rdagent/qualify_daily_container.py --image-id "$daily_image"
fi

stock="${ALPHA_STOCK_PYTHON:-}"
if [ "$with_stock" = 1 ]; then
    bundle="$runtime/rdagent-stock-py311"
    marker="$runtime/rdagent-stock-py311.incomplete"
    if [ -e "$marker" ]; then
        echo "setup-rdagent: $bundle build was interrupted ($marker); remove both to rebuild." >&2
        exit 1
    fi
    if [ ! -e "$bundle" ]; then
        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        printf 'build started %s\n' "$stamp" >"$marker"
        # Python 3.11: upstream RD-Agent declares and tests 3.10/3.11 only. Never download one.
        uv venv --quiet --no-python-downloads --python 3.11 "$bundle/venv"
        uv pip install --quiet --python "$bundle/venv/bin/python" --require-hashes --no-deps \
            -r workers/rdagent/stock-requirements.lock
        identity="$(.venv/bin/python -B workers/rdagent/install_stock_profile.py "$bundle")"
        printf 'validated %s identity %s\n' "$stamp" "$identity" >>"$marker"
        mv "$marker" "$runtime/rdagent-stock-py311.built-$stamp"
    fi
    echo "setup-rdagent: stock runtime $(.venv/bin/python -B workers/rdagent/install_stock_profile.py --verify "$bundle")"
    stock="$bundle/venv/bin/python"
fi

echo 'setup-rdagent: done; provisioning only, no execution authority or research admission'
printf 'export ALPHA_RDAGENT_SOURCE=%q\n' "$derived"
if [ -n "$stock" ] && [ -x "$stock" ]; then
    printf 'export ALPHA_STOCK_PYTHON=%q\n' "$stock"
    # The stock tests write receipts into a fresh existing directory of your choice.
    echo 'export ALPHA_STOCK_RECEIPTS="$(mktemp -d)"'
else
    echo '# ALPHA_STOCK_PYTHON: not provisioned (rerun with --with-stock-runtime)'
fi
