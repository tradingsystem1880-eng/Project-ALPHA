/**
 * Navigation intents.
 *
 * These shipped broken once: the shell never registered, so every "Run again", "Rerun for
 * causal trace" and next-step suggestion silently did nothing. Nothing failed — the intents
 * were absorbed by the no-op default. That is exactly the failure a test catches and a type
 * checker cannot, so the registration contract is asserted here.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  onLabPrefill,
  openDevelopmentCenter,
  openStrategyLab,
  registerNavigator,
  takeLabPrefill,
} from './actions'

function stub() {
  const navigator = {
    showRun: vi.fn(),
    showStrategyLab: vi.fn(),
    showProjects: vi.fn(),
  }
  registerNavigator(navigator)
  return navigator
}

beforeEach(() => {
  takeLabPrefill()
})

describe('navigation intents', () => {
  it('routes each intent to the registered shell', () => {
    const navigator = stub()
    openStrategyLab({ command: 'validate', args: 'SPY' })
    openDevelopmentCenter()
    expect(navigator.showStrategyLab).toHaveBeenCalledTimes(1)
    expect(navigator.showProjects).toHaveBeenCalledTimes(1)
  })

  it('holds a prefill for a lab that has not mounted yet', () => {
    stub()
    openStrategyLab({ command: 'optim grid', args: 'SPY --strategy breakout' })
    expect(takeLabPrefill()).toEqual({ command: 'optim grid', args: 'SPY --strategy breakout' })
  })

  it('delivers a prefill exactly once, however the lab is listening', () => {
    stub()
    const consumed: unknown[] = []
    const stop = onLabPrefill(() => consumed.push(takeLabPrefill()))

    openStrategyLab({ command: 'validate', args: 'AAPL' })
    expect(consumed).toEqual([{ command: 'validate', args: 'AAPL' }])
    // A mounted lab already took it, so a later mount must not apply it a second time.
    expect(takeLabPrefill()).toBeNull()

    stop()
    openStrategyLab({ command: 'validate', args: 'MSFT' })
    expect(consumed).toHaveLength(1)
    expect(takeLabPrefill()).toEqual({ command: 'validate', args: 'MSFT' })
  })

  it('does not queue or announce a prefill when the lab is opened empty', () => {
    stub()
    const seen = vi.fn()
    const stop = onLabPrefill(seen)
    openStrategyLab()
    expect(seen).not.toHaveBeenCalled()
    expect(takeLabPrefill()).toBeNull()
    stop()
  })
})
