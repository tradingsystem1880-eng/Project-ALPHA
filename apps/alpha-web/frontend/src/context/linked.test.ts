import { beforeEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_LINKED,
  getLinked,
  getLinkedWorkspace,
  applyLinkedPatch,
  migrateLinked,
  migrateLinkedWorkspace,
  restoreLinked,
  setLinked,
} from './linked'

beforeEach(() => restoreLinked(null))

describe('linked context migration', () => {
  it('supplies the v3 defaults for an absent context', () => {
    expect(migrateLinked(null)).toEqual(DEFAULT_LINKED)
  })

  it('preserves every field from a v2 saved workspace', () => {
    expect(
      migrateLinked({
        symbol: 'AAPL',
        start: '2020-01-01',
        end: '2024-12-31',
        runId: '0123456789abcdef',
      }),
    ).toEqual({
      ...DEFAULT_LINKED,
      symbol: 'AAPL',
      start: '2020-01-01',
      end: '2024-12-31',
      runId: '0123456789abcdef',
    })
  })

  it('normalizes persisted aliases and rejects invalid enum values', () => {
    expect(
      migrateLinked({
        link_group: 'C',
        project: 'mean-reversion',
        version: 'v7',
        universe: 'US-LIQUID-50',
        timeframe: 'daily',
        snapshot: 'snap-2026-07',
        run_id: 'fedcba9876543210',
      }),
    ).toEqual({
      ...DEFAULT_LINKED,
      linkGroup: 'C',
      projectId: 'mean-reversion',
      versionId: 'v7',
      universe: 'US-LIQUID-50',
      timeframe: '1D',
      snapshotId: 'snap-2026-07',
      runId: 'fedcba9876543210',
    })

    expect(migrateLinked({ linkGroup: 'Z', timeframe: '5m' })).toMatchObject({
      linkGroup: 'A',
      timeframe: '1D',
    })
  })

  it('keeps A and B independent while retaining the active flat projection', () => {
    setLinked({ symbol: 'AAPL', runId: 'run-a' })
    setLinked({ linkGroup: 'B' })
    setLinked({ symbol: 'MSFT', runId: 'run-b' })

    expect(getLinked()).toMatchObject({ linkGroup: 'B', symbol: 'MSFT', runId: 'run-b' })
    expect(getLinkedWorkspace().groups.A).toMatchObject({ symbol: 'AAPL', runId: 'run-a' })
    expect(getLinkedWorkspace().groups.B).toMatchObject({ symbol: 'MSFT', runId: 'run-b' })

    setLinked({ linkGroup: 'A' })
    expect(getLinked()).toMatchObject({ linkGroup: 'A', symbol: 'AAPL', runId: 'run-a' })
  })

  it('restores grouped schema-v3 state without changing the flat active shape', () => {
    const migrated = migrateLinkedWorkspace({
      schemaVersion: 3,
      linkGroup: 'C',
      symbol: 'flat-fallback',
      groups: {
        A: { symbol: 'AAPL', runId: 'run-a' },
        C: { symbol: 'BTC-USD', snapshotId: 'snap-c' },
      },
    })

    expect(migrated).toMatchObject({ linkGroup: 'C', symbol: 'BTC-USD', snapshotId: 'snap-c' })
    expect(migrated.groups.A).toMatchObject({ symbol: 'AAPL', runId: 'run-a' })
    expect(migrated.groups.C).toMatchObject({ symbol: 'BTC-USD', snapshotId: 'snap-c' })
    expect(migrateLinked(migrated)).toEqual({
      ...DEFAULT_LINKED,
      linkGroup: 'C',
      symbol: 'BTC-USD',
      snapshotId: 'snap-c',
    })
  })

  it('clears project-dependent state before applying a new project context', () => {
    expect(applyLinkedPatch(
      {
        ...DEFAULT_LINKED,
        projectId: 'old-project',
        symbol: 'AAPL',
        versionId: 'old-version',
        snapshotId: 'old-snapshot',
        runId: '0123456789abcdef',
      },
      { projectId: 'new-project' },
    )).toMatchObject({
      projectId: 'new-project',
      symbol: null,
      versionId: null,
      snapshotId: null,
      runId: null,
    })

    setLinked({
      projectId: 'old-project',
      symbol: 'AAPL',
      versionId: 'old-version',
      snapshotId: 'old-snapshot',
      runId: '0123456789abcdef',
    })
    setLinked({ projectId: 'new-project' })
    expect(getLinked()).toMatchObject({
      projectId: 'new-project',
      symbol: null,
      versionId: null,
      snapshotId: null,
      runId: null,
    })
  })

  it('accepts an atomic authoritative replacement without retaining old dependent values', () => {
    const next = applyLinkedPatch(
      {
        ...DEFAULT_LINKED,
        projectId: 'old-project',
        symbol: 'AAPL',
        versionId: 'old-version',
        snapshotId: 'old-snapshot',
        runId: '0123456789abcdef',
      },
      { projectId: 'new-project', versionId: 'new-version', symbol: 'SPY' },
    )
    expect(next).toMatchObject({
      projectId: 'new-project',
      symbol: 'SPY',
      versionId: 'new-version',
      snapshotId: null,
      runId: null,
    })
  })
})
