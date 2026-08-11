import { describe, expect, it } from 'vitest'

import type { ProviderDefinition } from '../api/types'
import {
  buildDataPullArgs,
  historicalProviders,
  livePaperStrategies,
  missingCredentialNames,
  providerOptionDefault,
  providerReadinessLabel,
} from './controlPlane'

const PROVIDERS: ProviderDefinition[] = [
  {
    id: 'finnhub',
    label: 'Finnhub',
    capabilities: ['live_quote', 'news'],
    network_required: true,
    credential_env: [{ name: 'ALPHA_FINNHUB_API_KEY', present: false }],
    options: {},
    limitations: ['API key required'],
    asset_classes: ['stock', 'etf'],
    timeframes: ['quote'],
    research_authority: false,
    paper_execution: false,
    budget_tier: 'free_optional',
    installed: true,
    configured: false,
  },
  {
    id: 'ccxt',
    label: 'CCXT Historical Crypto',
    capabilities: ['historical_bars'],
    network_required: true,
    credential_env: [],
    options: {
      exchange: { label: 'Exchange', choices: ['coinbase', 'binance'], default: 'coinbase' },
    },
    limitations: [],
    asset_classes: ['crypto'],
    timeframes: ['1D'],
    research_authority: true,
    paper_execution: false,
    budget_tier: 'free_public',
    installed: true,
    configured: true,
  },
  {
    id: 'stooq',
    label: 'Stooq',
    capabilities: ['historical_bars'],
    network_required: true,
    credential_env: [],
    options: {},
    limitations: [],
    asset_classes: ['stock', 'etf'],
    timeframes: ['1D'],
    research_authority: false,
    paper_execution: false,
    budget_tier: 'free_audit_only',
    installed: false,
    configured: false,
  },
]

describe('provider-driven Data Explorer', () => {
  it('only offers installed historical providers', () => {
    expect(historicalProviders(PROVIDERS).map((provider) => provider.id)).toEqual(['ccxt'])
  })

  it('uses the registry option default', () => {
    expect(providerOptionDefault(PROVIDERS[1], 'exchange')).toBe('coinbase')
    expect(providerOptionDefault(PROVIDERS[0], 'exchange')).toBeNull()
  })

  it('reports missing credential names without carrying any secret values', () => {
    expect(missingCredentialNames(PROVIDERS[0])).toEqual(['ALPHA_FINNHUB_API_KEY'])
    expect(providerReadinessLabel(PROVIDERS[0])).toBe('NEEDS CONFIG')
    expect(providerReadinessLabel(PROVIDERS[2])).toBe('NOT INSTALLED')
    expect(providerReadinessLabel(PROVIDERS[1])).toBe('READY')
  })

  it('threads the CCXT venue into the CLI and omits it for other sources', () => {
    expect(
      buildDataPullArgs({
        symbol: 'BTC/USDT',
        source: 'ccxt',
        start: '2025-01-01',
        end: '2025-06-01',
        exchange: 'binance',
      }),
    ).toBe('BTC/USDT --source ccxt --exchange binance --start 2025-01-01 --end 2025-06-01')
    expect(
      buildDataPullArgs({
        symbol: 'SPY',
        source: 'yfinance',
        start: '2025-01-01',
        end: '2025-06-01',
        exchange: 'binance',
      }),
    ).toBe('SPY --source yfinance --start 2025-01-01 --end 2025-06-01')
  })

  it('keeps unsupported model strategies out of the live-paper launcher', () => {
    const strategies = [
      { name: 'ts_momentum', supports_live_paper: true },
      { name: 'kronos', supports_live_paper: false },
    ]
    expect(livePaperStrategies(strategies).map((strategy) => strategy.name)).toEqual([
      'ts_momentum',
    ])
  })
})
