import { describe, expect, it } from 'vitest'

import { rerunCommand } from './rerun'

describe('rerunCommand', () => {
  it('maps every command a manifest can record to a launchable command id', () => {
    // These are the exact `command` values stored in this repo's run manifests.
    expect(rerunCommand('backtest_run', 'runs', false)).toBe('backtest run')
    expect(rerunCommand('backtest_oos', 'runs', false)).toBe('backtest oos')
    expect(rerunCommand('validate', 'runs', true)).toBe('validate')
    expect(rerunCommand('optim_grid', 'optim', false)).toBe('optim grid')
    expect(rerunCommand('backtest_portfolio', 'portfolio', false)).toBe('backtest portfolio')
    expect(rerunCommand('cross_sectional', 'cross_sectional', false)).toBe(
      'backtest cross-sectional',
    )
    expect(rerunCommand('propfirm', 'propfirm', false)).toBe('propfirm run')
    expect(rerunCommand('forecast_run', 'forecast', false)).toBe('forecast run')
    expect(rerunCommand('forecast_eval', 'forecast', false)).toBe('forecast eval')
  })

  it('never offers validate for a plain backtest', () => {
    // The regression this exists to prevent: one hardcoded command for every run kind.
    expect(rerunCommand('backtest_run', 'runs', false)).not.toBe('validate')
    expect(rerunCommand('forecast_run', 'forecast', false)).not.toBe('validate')
  })

  it('falls back to the run kind when a legacy manifest recorded no command', () => {
    expect(rerunCommand(null, 'runs', false)).toBe('backtest run')
    expect(rerunCommand(null, 'runs', true)).toBe('validate')
    expect(rerunCommand(null, 'optim', false)).toBe('optim grid')
    expect(rerunCommand(null, 'forecast', false)).toBe('forecast run')
  })

  it('offers nothing rather than the wrong thing for a run no command reproduces', () => {
    expect(rerunCommand('ml_replay', 'runs', false)).toBeNull()
    expect(rerunCommand(null, 'snapshots', false)).toBeNull()
  })
})
