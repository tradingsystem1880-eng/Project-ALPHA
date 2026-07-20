// Workspaces — save the current dockable layout (+ linked context) under a name, and restore or
// delete saved ones. Layouts persist server-side under the data dir, so they survive restarts.

import type { IDockviewPanelProps } from 'dockview-react'
import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { WorkspaceMeta } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { getLinkedWorkspace, restoreLinked } from '../context/linked'
import { buildDeskLayout } from '../layouts/presets'
import {
  requireSuccessfulWorkspaceResponse,
  workspaceMutation,
  workspaceViewState,
} from './workspaceModel'

export function Workspaces(props: IDockviewPanelProps) {
  const [list, setList] = useState<WorkspaceMeta[] | null>(null)
  const [name, setName] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [mutationError, setMutationError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'save' | 'open' | 'delete' | null>(null)

  const load = useCallback(async () => {
    setList(null)
    setLoadError(null)
    try {
      setList(await api.workspaces())
    } catch (reason) {
      setLoadError(String(reason))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function perform(
    action: 'save' | 'open' | 'delete',
    operation: 'SAVE' | 'OPEN' | 'DELETE',
    task: () => Promise<void>,
  ): Promise<void> {
    setBusy(action)
    setMutationError(null)
    setMutationError(await workspaceMutation(operation, task))
    setBusy(null)
  }

  function save(): void {
    const n = name.trim()
    if (!n || busy !== null) return
    void perform('save', 'SAVE', async () => {
      await api.saveWorkspace({
        name: n,
        linked_context: getLinkedWorkspace(),
        dockview: props.containerApi.toJSON(),
      })
      setName('')
      await load()
    })
  }

  function open(slug: string): void {
    void perform('open', 'OPEN', async () => {
      const doc = await api.getWorkspace(slug)
      try {
        // `dockview` is a Dockview SerializedDockview; typed loosely across the wire.
        props.containerApi.fromJSON(doc.dockview as never)
      } catch (reason) {
        // fromJSON clears the dock BEFORE validating, so recover the curated default and surface
        // the invalid saved layout instead of silently swallowing it.
        console.error('workspace restore failed', reason)
        if (props.containerApi.panels.length === 0) buildDeskLayout(props.containerApi)
        throw new Error(`layout restore failed: ${String(reason)}`)
      }
      if (doc.linked_context) restoreLinked(doc.linked_context)
    })
  }

  function remove(slug: string): void {
    void perform('delete', 'DELETE', async () => {
      const response = await api.deleteWorkspace(slug)
      requireSuccessfulWorkspaceResponse(response)
      setList((current) => current?.filter((workspace) => workspace.slug !== slug) ?? [])
    })
  }

  const viewState = workspaceViewState(list, loadError)

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Workspaces</span>
        <span className="count">{list?.length ?? '—'}</span>
      </div>
      <div className="panel-body panel-pad de">
        <div className="lab-row">
          <label className="field-row">
            <span className="field-label">Save current layout as</span>
            <input
              className="field"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && save()}
              placeholder="Research Desk"
            />
          </label>
          <button
            className="btn primary ws-save"
            disabled={busy !== null || !name.trim()}
            onClick={save}
          >
            {busy === 'save' ? 'Saving…' : 'Save'}
          </button>
        </div>
        {mutationError ? <div className="leak" role="alert">{mutationError}</div> : null}
        {viewState === 'loading' ? (
          <Placeholder>loading saved workspaces…</Placeholder>
        ) : viewState === 'error' ? (
          <Placeholder big="workspace load failed">
            <span>{loadError}</span>
            <button className="btn" onClick={() => void load()}>retry</button>
          </Placeholder>
        ) : viewState === 'empty' ? (
          <div className="muted">No saved workspaces — arrange panels and save one.</div>
        ) : (
          <div className="ws-list">
            {(list ?? []).map((workspace) => (
              <div className="ws-item" key={workspace.slug}>
                <button
                  className="ws-open"
                  disabled={busy !== null}
                  onClick={() => open(workspace.slug)}
                >
                  {workspace.name}
                </button>
                <button
                  className="btn ws-del"
                  aria-label={`Delete ${workspace.name}`}
                  disabled={busy !== null}
                  onClick={() => remove(workspace.slug)}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
