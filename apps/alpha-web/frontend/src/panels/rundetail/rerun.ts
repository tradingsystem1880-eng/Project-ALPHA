// Which CLI command would reproduce this run.
//
// Manifests record the command in snake_case (`backtest_run`), while the Strategy Lab keys
// its form on the CLI's own command ids (`backtest run`). "Run again" used to hardcode
// `validate`, which quietly offered the wrong command for every other run kind. Mapping is
// a lookup with a kind-derived fallback for the legacy manifests that recorded no command
// at all, and an honest `null` for runs no single command reproduces.

/** Manifest `command` -> Strategy Lab command id. */
const BY_COMMAND: Record<string, string> = {
  backtest_run: 'backtest run',
  backtest_oos: 'backtest oos',
  backtest_portfolio: 'backtest portfolio',
  cross_sectional: 'backtest cross-sectional',
  validate: 'validate',
  optim_grid: 'optim grid',
  propfirm: 'propfirm run',
  forecast_run: 'forecast run',
  forecast_eval: 'forecast eval',
}

/** Run kind -> command, for manifests written before `command` was recorded. */
const BY_KIND: Record<string, string> = {
  portfolio: 'backtest portfolio',
  cross_sectional: 'backtest cross-sectional',
  optim: 'optim grid',
  propfirm: 'propfirm run',
  forecast: 'forecast run',
}

/**
 * The command to prefill, or `null` when nothing reproduces this run — an ML replay is
 * driven by the `alpha ml` exchange rather than a single launchable command, and offering
 * a button that runs something else would be worse than offering no button.
 */
export function rerunCommand(
  command: string | null,
  kind: string,
  isValidate: boolean,
): string | null {
  if (command) return BY_COMMAND[command] ?? null
  if (kind === 'runs') return isValidate ? 'validate' : 'backtest run'
  return BY_KIND[kind] ?? null
}
