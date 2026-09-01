import type { ProviderDefinition } from '../api/types'
import { validateDates } from './dataManagerModel'

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
  if (provider.verification_state === 'verified') return 'VERIFIED'
  if (provider.configuration_state === 'optional_disabled') return 'OPTIONAL DISABLED'
  if (provider.configuration_state === 'needs_process_injection') return 'NEEDS PROCESS INJECTION'
  if (provider.configuration_state === 'not_installed') return 'NOT INSTALLED'
  return provider.verification_state.replaceAll('_', ' ').toUpperCase()
}

interface PullArgs {
  symbol: string
  source: string
  start: string
  end: string
  exchange: string
}

/** The `alpha data pull` argv; throws the date problem the CLI would otherwise reject. */
export function buildDataPullArgs({ symbol, source, start, end, exchange }: PullArgs): string {
  const problem = validateDates(start, end)
  if (problem) throw new Error(problem)
  const venue = source === 'ccxt' ? ` --exchange ${exchange}` : ''
  return `${symbol.trim()} --source ${source}${venue} --start ${start} --end ${end}`
}
