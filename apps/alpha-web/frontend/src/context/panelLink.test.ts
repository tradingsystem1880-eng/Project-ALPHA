import { describe, expect, it } from 'vitest'

import { DEFAULT_LINKED, migrateLinkedWorkspace } from './linked'
import {
  migratePanelBinding,
  patchLocalPanelBinding,
  resolvePanelLinked,
} from './panelLinkModel'

const workspace = migrateLinkedWorkspace({
  schemaVersion: 3,
  linkGroup: 'B',
  groups: {
    A: { symbol: 'AAPL', runId: 'run-a' },
    B: { symbol: 'MSFT', runId: 'run-b' },
  },
})

describe('panel link bindings', () => {
  it('keeps a panel pinned to A when B broadcasts a different context', () => {
    const pinned = migratePanelBinding({ mode: 'pinned-to-group', group: 'A' })
    const before = resolvePanelLinked(workspace, pinned)
    const after = resolvePanelLinked(
      migrateLinkedWorkspace({
        ...workspace,
        symbol: 'NVDA',
        runId: 'run-b-2',
        groups: { ...workspace.groups, B: { ...workspace.groups.B, symbol: 'NVDA', runId: 'run-b-2' } },
      }),
      pinned,
    )

    expect(before).toMatchObject({ linkGroup: 'A', symbol: 'AAPL', runId: 'run-a' })
    expect(after).toEqual(before)
  })

  it('keeps unlinked local state isolated and patches only its local copy', () => {
    const local = migratePanelBinding(
      { mode: 'unlinked-local', group: 'C', local: { symbol: 'ETH-USD', runId: 'local-run' } },
      DEFAULT_LINKED,
    )
    const before = resolvePanelLinked(workspace, local)
    const broadcast = resolvePanelLinked(
      migrateLinkedWorkspace({ ...workspace, linkGroup: 'A', groups: workspace.groups }),
      local,
    )
    const patched = resolvePanelLinked(workspace, patchLocalPanelBinding(local, { runId: 'local-run-2' }))

    expect(before).toMatchObject({ linkGroup: 'C', symbol: 'ETH-USD', runId: 'local-run' })
    expect(broadcast).toEqual(before)
    expect(patched).toMatchObject({ symbol: 'ETH-USD', runId: 'local-run-2' })
    expect(workspace.groups.C.runId).toBeNull()
  })

  it('migrates a legacy explicit panel run to unlinked-local semantics', () => {
    const binding = migratePanelBinding(undefined, { ...DEFAULT_LINKED, linkGroup: 'D' }, 'legacy-run')
    expect(binding).toMatchObject({
      mode: 'unlinked-local',
      group: 'D',
      local: { runId: 'legacy-run' },
    })
  })
})
