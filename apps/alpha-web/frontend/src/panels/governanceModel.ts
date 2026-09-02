// The Governance dialog's seven pages, composed from existing client reads only. Every value is
// relayed from a projection or is one of the sentences that used to be a hazard stripe on a
// working screen; nothing here derives authority, and nothing is computed the server did not say.

import type {
  ActiveResearchGateOverride,
  CryptoStorage,
  PaperSession,
  ProviderDefinition,
  SystemStatus,
} from '../api/types'
import { storageRow } from './dataManagerModel'
import type { StrategyGateLock } from './researchGateModel'

/** The sentences that were hazard stripes on Research, Build and Operate — verbatim. */
export const GOVERNANCE_SENTENCES = {
  research: 'RESEARCH SANDBOX · SYNTHETIC D0 IS NOT REAL-MARKET EVIDENCE OR A TRADING SIGNAL',
  paper: 'PAPER ONLY · BINANCE LOCAL SANDBOX + IBKR PAPER · LIVE-CAPITAL ROUTING ABSENT',
  standalone: 'STANDALONE_UNQUALIFIED · THESE RUNS CAN NEVER COUNT AS GOVERNED RESEARCH EVIDENCE',
  strategy: 'SANDBOX · PUBLIC BINANCE DATA · REAL EXECUTION IS NOT AVAILABLE',
  touchId: 'TOUCH ID REQUIRED · NO OVERRIDE · NO TRADING',
} as const

export type Tone = 'ok' | 'warn' | 'bad'

export interface GovernanceRow {
  label: string
  value: string
  tone: Tone
}

export interface GovernancePage {
  id: string
  label: string
  rows: GovernanceRow[]
  /** Shown instead of rows when there are none. */
  empty: string | null
  /** The research case holding an open gate, when there is one. */
  caseLink: { projectId: string; projectName: string | null } | null
}

export interface GovernanceInput {
  system: SystemStatus | null
  providers: ProviderDefinition[] | null
  overrides: ActiveResearchGateOverride[] | null
  sessions: PaperSession[] | null
  storage: Pick<CryptoStorage, 'state' | 'blocker' | 'bulk_root_label' | 'free_bytes' | 'total_bytes'> | null
  gate: { lock: StrategyGateLock | null; projectId: string | null; projectName: string | null }
  watermark: string | null
  connection: string
}

const page = (
  id: string,
  label: string,
  rows: GovernanceRow[],
  empty: string | null = null,
  caseLink: GovernancePage['caseLink'] = null,
): GovernancePage => ({ id, label, rows, empty: rows.length ? null : empty, caseLink })

function authority(input: GovernanceInput): GovernanceRow[] {
  const rows: GovernanceRow[] = [
    { label: 'Research', value: GOVERNANCE_SENTENCES.research, tone: 'warn' },
    { label: 'Paper', value: GOVERNANCE_SENTENCES.paper, tone: 'warn' },
    { label: 'Standalone', value: GOVERNANCE_SENTENCES.standalone, tone: 'warn' },
    { label: 'Strategy', value: GOVERNANCE_SENTENCES.strategy, tone: 'warn' },
    { label: 'Owner actions', value: GOVERNANCE_SENTENCES.touchId, tone: 'warn' },
  ]
  if (input.watermark) rows.push({ label: 'Selected run', value: input.watermark, tone: 'bad' })
  const system = input.system
  rows.push(
    system === null
      ? { label: 'Paper sessions', value: 'not loaded', tone: 'warn' }
      : system.paper_enabled
        ? { label: 'Paper sessions', value: 'enabled', tone: 'ok' }
        : { label: 'Paper sessions', value: 'disabled (ALPHA_PAPER_ENABLED unset)', tone: 'warn' },
    system === null
      ? { label: 'IBKR paper', value: 'not loaded', tone: 'warn' }
      : { label: 'IBKR paper', value: system.ibkr_paper_enabled ? 'enabled' : 'disabled', tone: system.ibkr_paper_enabled ? 'ok' : 'warn' },
  )
  if (input.sessions !== null) {
    const live = input.sessions.filter((session) => session.ended_at === null).length
    rows.push({ label: 'Open paper sessions', value: String(live), tone: live ? 'ok' : 'warn' })
  }
  rows.push({
    label: 'Activity stream',
    value: input.connection,
    tone: input.connection === 'live' ? 'ok' : 'warn',
  })
  return rows
}

function gates(input: GovernanceInput): GovernancePage {
  const { lock, projectId, projectName } = input.gate
  if (!projectId) return page('gates', 'Research gates', [], 'No linked project')
  const name = projectName ?? projectId
  if (lock) {
    return page(
      'gates',
      'Research gates',
      [{ label: name, value: `RESEARCH GATE OPEN — ${lock.reason}`, tone: 'bad' }],
      null,
      { projectId, projectName },
    )
  }
  return page('gates', 'Research gates', [{ label: name, value: 'no open research gate', tone: 'ok' }])
}

function overrides(list: ActiveResearchGateOverride[] | null): GovernancePage {
  if (list === null) return page('overrides', 'Overrides', [], 'Overrides not loaded')
  return page(
    'overrides',
    'Overrides',
    list.map((item) => ({
      label: `${item.project_name} · ${item.actor} · ${item.recorded_at}`,
      value: item.reason,
      tone: 'bad' as const,
    })),
    'No active research-gate overrides',
  )
}

function providers(list: ProviderDefinition[] | null): GovernancePage {
  if (list === null) return page('providers', 'Providers', [], 'Providers not loaded')
  return page(
    'providers',
    'Providers',
    list.map((item) => ({
      label: item.label,
      value: item.configuration_state.replaceAll('_', ' '),
      tone: item.configured ? ('ok' as const) : ('warn' as const),
    })),
    'No providers registered',
  )
}

export function governancePages(input: GovernanceInput): GovernancePage[] {
  const ssd = storageRow(input.storage)
  return [
    page('authority', 'Authority & status', authority(input)),
    page('touchid', 'Touch ID', [
      { label: 'Owner actions', value: GOVERNANCE_SENTENCES.touchId, tone: 'warn' },
      {
        label: 'Research decisions',
        value: 'Every research decision, semantic freeze and paper acceptance is a Touch ID owner action recorded with a receipt; the browser never derives or caches presence.',
        tone: 'ok',
      },
    ]),
    gates(input),
    overrides(input.overrides),
    providers(input.providers),
    page('storage', 'Storage', [
      { label: ssd.label, value: ssd.detail, tone: ssd.tone === 'amber' ? 'warn' : 'ok' },
    ]),
    page('glossary', 'Glossary', []),
  ]
}
