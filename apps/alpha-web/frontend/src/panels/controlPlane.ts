import type { ProviderDefinition } from '../api/types'

export function livePaperStrategies<T extends { supports_live_paper?: boolean }>(
  strategies: T[],
): T[] {
  return strategies.filter((strategy) => strategy.supports_live_paper === true)
}

export function historicalProviders(providers: ProviderDefinition[]): ProviderDefinition[] {
  return providers.filter(
    (provider) => provider.installed && provider.capabilities.includes('historical_bars'),
  )
}

export function providerOptionDefault(
  provider: ProviderDefinition | undefined,
  option: string,
): string | null {
  return provider?.options[option]?.default ?? null
}

export function missingCredentialNames(provider: ProviderDefinition): string[] {
  return provider.credential_env
    .filter((credential) => !credential.present)
    .map((credential) => credential.name)
}

export function providerReadinessLabel(provider: ProviderDefinition): string {
  if (provider.configured) return 'READY'
  return provider.installed ? 'NEEDS CONFIG' : 'NOT INSTALLED'
}

interface PullArgs {
  symbol: string
  source: string
  start: string
  end: string
  exchange: string
}

export function buildDataPullArgs({ symbol, source, start, end, exchange }: PullArgs): string {
  const venue = source === 'ccxt' ? ` --exchange ${exchange}` : ''
  return `${symbol.trim()} --source ${source}${venue} --start ${start} --end ${end}`
}
