import { describe, expect, it } from 'vitest'

import { GOVERNANCE_SENTENCES, governancePages, type GovernanceInput } from './governanceModel'

const EMPTY: GovernanceInput = {
  system: null,
  providers: null,
  overrides: null,
  sessions: null,
  storage: null,
  gate: { lock: null, projectId: null, projectName: null },
  watermark: null,
  connection: 'connecting',
}

const SYSTEM = {
  paper_enabled: false,
  ibkr_paper_enabled: false,
  nautilus: { available: true, version: '1.200.0' },
} as unknown as NonNullable<GovernanceInput['system']>

function page(pages: ReturnType<typeof governancePages>, id: string) {
  const found = pages.find((item) => item.id === id)
  if (!found) throw new Error(`no page ${id}`)
  return found
}

describe('governancePages', () => {
  it('has the seven pages in the order the spec names them', () => {
    expect(governancePages(EMPTY).map((item) => item.id)).toEqual([
      'authority',
      'touchid',
      'gates',
      'overrides',
      'providers',
      'storage',
      'glossary',
    ])
  })

  it('lists every relocated hazard sentence verbatim under Authority & status', () => {
    const rows = page(governancePages(EMPTY), 'authority').rows.map((row) => row.value)
    for (const sentence of Object.values(GOVERNANCE_SENTENCES)) expect(rows).toContain(sentence)
  })

  it('reads paper flags and the activity connection from the projections, never inventing them', () => {
    const rows = page(governancePages({ ...EMPTY, system: SYSTEM, connection: 'live' }), 'authority')
      .rows
    expect(rows).toContainEqual({ label: 'Paper sessions', value: 'disabled (ALPHA_PAPER_ENABLED unset)', tone: 'warn' })
    expect(rows).toContainEqual({ label: 'IBKR paper', value: 'disabled', tone: 'warn' })
    expect(rows).toContainEqual({ label: 'Activity stream', value: 'live', tone: 'ok' })
    const unloaded = page(governancePages(EMPTY), 'authority').rows
    expect(unloaded).toContainEqual({ label: 'Paper sessions', value: 'not loaded', tone: 'warn' })
  })

  it('carries the selected run watermark as a row so the pane is the third surface', () => {
    const rows = page(
      governancePages({ ...EMPTY, watermark: 'EXPLORATORY / RESEARCH GATE NOT COMPLETED' }),
      'authority',
    ).rows
    expect(rows).toContainEqual({
      label: 'Selected run',
      value: 'EXPLORATORY / RESEARCH GATE NOT COMPLETED',
      tone: 'bad',
    })
    expect(page(governancePages(EMPTY), 'authority').rows.map((row) => row.label)).not.toContain(
      'Selected run',
    )
  })

  it('relays the linked project gate verbatim and says when nothing is linked', () => {
    const open = page(
      governancePages({
        ...EMPTY,
        gate: { lock: { reason: 'gate reason' }, projectId: 'p1', projectName: 'Momentum' },
      }),
      'gates',
    )
    expect(open.rows).toContainEqual({ label: 'Momentum', value: 'RESEARCH GATE OPEN — gate reason', tone: 'bad' })
    expect(open.caseLink).toEqual({ projectId: 'p1', projectName: 'Momentum' })
    const closed = page(
      governancePages({ ...EMPTY, gate: { lock: null, projectId: 'p1', projectName: 'Momentum' } }),
      'gates',
    )
    expect(closed.rows).toContainEqual({ label: 'Momentum', value: 'no open research gate', tone: 'ok' })
    expect(closed.caseLink).toBeNull()
    expect(page(governancePages(EMPTY), 'gates').empty).toBe('No linked project')
  })

  it('lists overrides verbatim: project, actor, reason, recorded_at', () => {
    const pages = governancePages({
      ...EMPTY,
      overrides: [
        {
          project_id: 'p1',
          project_name: 'SPY exploratory probe',
          actor: 'owner',
          reason: 'Owner accepted exploratory-only engine work before research completes.',
          recorded_at: '2026-08-01T00:00:00Z',
          sequence: 3,
        },
      ],
    })
    expect(page(pages, 'overrides').rows).toEqual([
      {
        label: 'SPY exploratory probe · owner · 2026-08-01T00:00:00Z',
        value: 'Owner accepted exploratory-only engine work before research completes.',
        tone: 'bad',
      },
    ])
    expect(page(governancePages({ ...EMPTY, overrides: [] }), 'overrides').empty).toBe(
      'No active research-gate overrides',
    )
    expect(page(governancePages(EMPTY), 'overrides').empty).toBe('Overrides not loaded')
  })

  it('shows each provider with its configuration state', () => {
    const pages = governancePages({
      ...EMPTY,
      providers: [
        { id: 'ccxt', label: 'CCXT', configuration_state: 'available_without_credentials', configured: true },
        { id: 'tiingo', label: 'Tiingo', configuration_state: 'not_installed', configured: false },
      ] as unknown as NonNullable<GovernanceInput['providers']>,
    })
    expect(page(pages, 'providers').rows).toEqual([
      { label: 'CCXT', value: 'available without credentials', tone: 'ok' },
      { label: 'Tiingo', value: 'not installed', tone: 'warn' },
    ])
  })

  it('reuses the Data Manager storage row', () => {
    const rows = page(
      governancePages({
        ...EMPTY,
        storage: { state: 'blocked', blocker: 'bulk_volume_not_mounted', bulk_root_label: 'Expansion', free_bytes: 0, total_bytes: 0 },
      }),
      'storage',
    ).rows
    expect(rows).toEqual([
      { label: 'Expansion SSD not mounted', value: 'Reconnect the Expansion volume, then refresh.', tone: 'warn' },
    ])
  })
})
