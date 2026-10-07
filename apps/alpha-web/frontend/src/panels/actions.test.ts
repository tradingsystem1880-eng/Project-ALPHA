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
  openProviderCenter,
  openResearchData,
  openResearchSources,
  openStrategyLab,
  openStoredMarket,
  registerNavigator,
  takeLabPrefill,
} from './actions'
import { DEFAULT_LINKED, getLinked, restoreLinked } from '../context/linked'

function stub() {
  const navigator = {
    showChart: vi.fn(),
    showRun: vi.fn(),
    showStrategyLab: vi.fn(),
    showProjects: vi.fn(),
    showResearchSources: vi.fn(),
    showResearchData: vi.fn(),
    showDataSymbol: vi.fn(),
    showCompare: vi.fn(),
    showProviders: vi.fn(),
    showIndicators: vi.fn(),
  }
  registerNavigator(navigator)
  return navigator
}

beforeEach(() => {
  takeLabPrefill()
  restoreLinked(DEFAULT_LINKED)
})

describe('navigation intents', () => {
  it('routes each intent to the registered shell', () => {
    const navigator = stub()
    openStrategyLab({ command: 'validate', args: 'SPY' })
    openDevelopmentCenter()
    openResearchSources()
    openResearchData()
    openProviderCenter()
    expect(navigator.showStrategyLab).toHaveBeenCalledTimes(1)
    expect(navigator.showProjects).toHaveBeenCalledTimes(1)
    expect(navigator.showResearchSources).toHaveBeenCalledTimes(1)
    expect(navigator.showResearchData).toHaveBeenCalledTimes(1)
    expect(navigator.showProviders).toHaveBeenCalledTimes(1)
  })

  it('opens the stored market chart and clears unrelated window and run context', () => {
    const navigator = stub()
    restoreLinked({
      ...DEFAULT_LINKED,
      symbol: 'SPY',
      start: '2020-01-01',
      end: '2020-12-31',
      snapshotId: 'snapshot-1',
      runId: '0123456789abcdef',
    })

    openStoredMarket('XRP/USD')

    expect(getLinked()).toMatchObject({
      symbol: 'XRP/USD',
      start: null,
      end: null,
      snapshotId: null,
      runId: null,
    })
    expect(navigator.showChart).toHaveBeenCalledOnce()
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
