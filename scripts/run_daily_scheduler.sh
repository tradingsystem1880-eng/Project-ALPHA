#!/bin/sh
set -eu
set +x

if [ "$#" -ne 1 ]; then
  echo "usage: run_daily_scheduler.sh /absolute/private/daily-paper.json" >&2
  exit 64
fi

ALPHA_TIINGO_API_KEY="$(/usr/bin/security find-generic-password -w -s project-alpha-tiingo)"
if [ -z "$ALPHA_TIINGO_API_KEY" ]; then
  echo "missing project-alpha-tiingo keychain secret" >&2
  exit 78
fi
export ALPHA_TIINGO_API_KEY

exec .venv/bin/alpha paper scheduler-tick --config "$1"
