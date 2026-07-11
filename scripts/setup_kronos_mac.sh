#!/usr/bin/env bash
# One-command Kronos setup for macOS: toolchain -> torch stack -> Kronos-base weights ->
# market data -> first real forecast -> web UI. Run from anywhere inside the repo:
#
#   bash scripts/setup_kronos_mac.sh [SYMBOL]      # default symbol: AAPL
#
# Idempotent: re-running skips finished steps (uv sync is incremental, weights are cached,
# forecasts are content-addressed). Fails loud on any error.
set -euo pipefail

SYMBOL="${1:-AAPL}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

step "1/6 Checking uv (Python toolchain)"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found - installing (https://docs.astral.sh/uv/)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv --version

step "2/6 Installing the workspace + Kronos torch stack (uv sync --group kronos)"
uv sync --group kronos

step "3/6 Downloading Kronos-base weights (102.3M params - the largest open checkpoint)"
# Weights come from Hugging Face (NeoQuasar/Kronos-base + Tokenizer-base) into
# data/models. The pull verifies the snapshot loads offline before reporting success.
uv run alpha forecast pull --model base

step "4/6 Pulling market data for ${SYMBOL} (yfinance)"
START="2023-01-01"
END="$(date +%F)"
uv run alpha data pull "$SYMBOL" --source yfinance --start "$START" --end "$END"

step "5/6 Running your first real Kronos-base forecast (30 bars ahead)"
# Device auto-detects: Apple-silicon GPU (MPS) when available, else CPU.
# NOTE the yellow warning if the context window predates 2025-08: Kronos trained on data
# up to then, so forecasts over that region may be memorized - treat as upper bounds.
uv run alpha forecast run "$SYMBOL" --model base --horizon 30 --context 400

step "6/6 Launching the web UI (http://127.0.0.1:8800)"
echo "The forecast chart is on the run page (solid = history, dashed = Kronos forecast)."
echo "Stop the server with Ctrl+C. Next steps:"
echo "  uv run alpha forecast run TSLA --model base --horizon 30   # forecast anything stored"
echo "  uv run alpha backtest run $SYMBOL --strategy kronos_forecast --param model=2"
echo "  uv run pytest -m network -q                                # live test-suite + timings"
if command -v open >/dev/null 2>&1; then
  (sleep 2 && open "http://127.0.0.1:8800") &
fi
exec uv run alpha-web
