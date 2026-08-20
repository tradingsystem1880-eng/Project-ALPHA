#!/bin/sh
# Atlas gate: the isolated-project ritual (workers/ pattern).
set -eu
cd "$(dirname "$0")"
uv lock --check
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
uv run python -m alpha_atlas.generate --check
