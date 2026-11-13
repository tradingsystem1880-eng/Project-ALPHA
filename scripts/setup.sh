#!/usr/bin/env bash
# One-command setup for Project ALPHA on a fresh Linux checkout. Safe to re-run.
#
# Prepares everything synthetic-data development needs, from the locked dependency files only:
#   1. the root Python environment            (uv sync --locked)
#   2. the web app, built                     (npm ci; npm run build in apps/alpha-web/frontend)
#   3. the web app's test browser             (Playwright's Chromium, in the standard per-user cache)
#   4. the Qlib and literature worker setups  (uv sync --locked in each worker folder)
#   5. the commit-message hook                (scripts/git_guard.py install, when not installed)
#
# Optional, off by default (they download more):
#   --with-rdagent          also run scripts/setup_rdagent.sh (pinned RD-Agent source and runtimes)
#   --with-stock-runtime    also build the RD-Agent stock runtime (implies --with-rdagent)
#   --with-daily-container  also pull the pinned daily-study Docker image (implies --with-rdagent)
#   --data-dir DIR --storage-reserve-gb N
#                           record the owner's free-space reserve for the data folder DIR with
#                           scripts/storage_settings.py (see docs/operations/storage-settings.md).
#                           Only runs when the owner names DIR; setup never picks a data folder.
#   --dry-run               print what would run, change nothing
#   --help                  show this text
#
# Never uses sudo, never reads .env or any credential file, never asks a question, and downloads
# only locked packages and Playwright's Chromium (plus what the --with-* options name).
# Afterwards: `python3 scripts/gate.py doctor` says in plain English what is still missing.
set -Eeuo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
current_step='starting'
trap 'status=$?; printf "\nsetup: STOPPED while %s (exit %s).\nsetup: Fix the problem shown above and run scripts/setup.sh again; finished steps are skipped quickly.\n" "$current_step" "$status" >&2; exit "$status"' ERR

usage() {
    sed -n '2,/^set -Eeuo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'
}

die() {
    printf 'setup: %s\n' "$1" >&2
    printf 'setup: run scripts/setup.sh --help for the options.\n' >&2
    exit 2
}

with_rdagent=0
with_stock=0
with_daily=0
dry_run=0
data_dir=''
reserve_gb=''
reserve_given=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --with-rdagent) with_rdagent=1 ;;
        --with-stock-runtime) with_rdagent=1; with_stock=1 ;;
        --with-daily-container) with_rdagent=1; with_daily=1 ;;
        --dry-run) dry_run=1 ;;
        --data-dir)
            [ "$#" -ge 2 ] || die '--data-dir needs a folder, for example --data-dir /home/you/alpha-data'
            data_dir="$2"; shift ;;
        --data-dir=*) data_dir="${1#--data-dir=}" ;;
        --storage-reserve-gb)
            [ "$#" -ge 2 ] || die '--storage-reserve-gb needs a number of gigabytes, for example 10'
            reserve_gb="$2"; reserve_given=1; shift ;;
        --storage-reserve-gb=*) reserve_gb="${1#--storage-reserve-gb=}"; reserve_given=1 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

if [ "$reserve_given" = 1 ] && [ -z "$data_dir" ]; then
    die '--storage-reserve-gb needs --data-dir DIR: setup never chooses a data folder for you.'
fi
if [ -n "$data_dir" ] && [ "$reserve_given" = 0 ]; then
    die '--data-dir is only used together with --storage-reserve-gb N.'
fi
if [ "$reserve_given" = 1 ]; then
    case "$reserve_gb" in
        ''|*[!0-9.]*|.*|*.|*.*.*) die "--storage-reserve-gb must be a plain number of gigabytes, not '$reserve_gb'." ;;
    esac
    case "$data_dir" in
        /*) ;;
        *) die "--data-dir must be an absolute path (starting with /), not '$data_dir'." ;;
    esac
fi

done_steps=()
skipped_steps=()
failed_note=''

# Run a command (or only print it with --dry-run), inside the folder named by $1.
run_in() {
    local folder="$1"
    shift
    printf '  $ (cd %s && %s)\n' "${folder#"$root"/}" "$*"
    if [ "$dry_run" = 0 ]; then
        (cd "$folder" && "$@")
    fi
}

step() {
    current_step="$1"
    printf '\n== %s\n' "$1"
}

check_tools() {
    local missing=0 tool hint
    for tool in git uv node npm npx; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            case "$tool" in
                uv) hint='install uv: https://docs.astral.sh/uv/getting-started/installation/' ;;
                git) hint='install git with your system package manager' ;;
                *) hint='install Node.js 20 or newer (it brings npm and npx)' ;;
            esac
            printf 'setup: missing tool "%s": %s\n' "$tool" "$hint" >&2
            missing=1
        fi
    done
    if [ "$missing" = 1 ]; then
        current_step='checking the tools setup needs'
        return 1
    fi
}

step 'Checking the tools setup needs (uv, git, node, npm, npx)'
check_tools
cd "$root"

if [ "$dry_run" = 1 ]; then
    printf 'setup: dry run: nothing below is executed.\n'
fi

step 'Root Python environment (uv sync --locked)'
run_in "$root" uv sync --locked
done_steps+=('root Python environment')

step 'Web app: locked packages and build'
run_in "$root/apps/alpha-web/frontend" npm ci
run_in "$root/apps/alpha-web/frontend" npm run build
done_steps+=('web app built')

step "Web app test browser (Playwright's Chromium, standard per-user cache)"
if [ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ]; then
    printf 'setup: note: PLAYWRIGHT_BROWSERS_PATH is set (%s); ignoring it so the browser goes to the\n' "$PLAYWRIGHT_BROWSERS_PATH"
    printf '       standard cache (~/.cache/ms-playwright). You can remove that variable from your shell.\n'
fi
run_in "$root/apps/alpha-web/frontend" env -u PLAYWRIGHT_BROWSERS_PATH npx --no-install playwright install chromium
done_steps+=('test browser (Chromium)')

for worker in qlib literature; do
    step "Worker environment: $worker (uv sync --locked)"
    run_in "$root/workers/$worker" uv sync --locked
    done_steps+=("$worker worker environment")
done

step 'Git commit-message hook'
current_hooks="$(git -C "$root" config --get core.hooksPath 2>/dev/null || true)"
if [ "$current_hooks" = '.githooks' ]; then
    printf '  already installed\n'
    skipped_steps+=('git hook: already installed')
else
    run_in "$root" uv run python scripts/git_guard.py install
    done_steps+=('git commit-message hook')
fi

if [ "$with_rdagent" = 1 ]; then
    rdagent_args=()
    [ "$with_daily" = 1 ] && rdagent_args+=(--with-daily-container)
    [ "$with_stock" = 1 ] && rdagent_args+=(--with-stock-runtime)
    step 'RD-Agent (scripts/setup_rdagent.sh): pinned source and runtimes'
    run_in "$root" bash scripts/setup_rdagent.sh ${rdagent_args[@]+"${rdagent_args[@]}"}
    done_steps+=('RD-Agent source and runtimes')
    [ "$with_daily" = 1 ] && done_steps+=('daily-study Docker image')
    [ "$with_stock" = 1 ] && done_steps+=('RD-Agent stock runtime')
else
    skipped_steps+=('RD-Agent: not requested (add --with-rdagent)')
fi

if [ "$reserve_given" = 1 ]; then
    step "Storage reserve for $data_dir"
    settings_file="$data_dir/crypto/storage-config.json"
    if [ -e "$settings_file" ]; then
        printf '  settings already exist; showing them, changing nothing\n'
        run_in "$root" uv run python scripts/storage_settings.py show --data-dir "$data_dir"
        skipped_steps+=("storage reserve: settings already exist in $data_dir (kept)")
    else
        if [ "$dry_run" = 0 ]; then
            mkdir -p "$data_dir/bulk"
        fi
        run_in "$root" uv run python scripts/storage_settings.py write --apply \
            --data-dir "$data_dir" --bulk-root "$data_dir/bulk" \
            --durable-hosting-reference "owner-named data folder $data_dir (set by scripts/setup.sh; durability not assessed)" \
            --reserve-gb "$reserve_gb" \
            --decided-by owner --decided-on "$(date +%F)" \
            --decision-record "ADR-0043; owner passed --storage-reserve-gb $reserve_gb to scripts/setup.sh"
        done_steps+=("storage reserve ${reserve_gb} GB in $data_dir")
    fi
else
    skipped_steps+=('storage reserve: not requested (needs --data-dir DIR --storage-reserve-gb N)')
fi

current_step='printing the summary'
printf '\n================ setup summary ================\n'
if [ "$dry_run" = 1 ]; then
    printf 'Dry run: nothing was changed. A real run would set up:\n'
else
    printf 'Set up:\n'
fi
for item in "${done_steps[@]}"; do
    printf '  + %s\n' "$item"
done
if [ "${#skipped_steps[@]}" -gt 0 ]; then
    printf 'Skipped:\n'
    for item in "${skipped_steps[@]}"; do
        printf '  - %s\n' "$item"
    done
fi
printf 'Total time: %ss\n' "$SECONDS"
printf 'Next: python3 scripts/gate.py doctor   (says in plain English what is still missing)\n'
