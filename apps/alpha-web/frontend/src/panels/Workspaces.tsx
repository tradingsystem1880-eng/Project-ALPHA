// Workspaces — save the current dockable layout (+ linked context) under a name, and restore or
// delete saved ones. Layouts persist server-side under the data dir, so they survive restarts.

import type { IDockviewPanelProps } from 'dockview-react'
import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { WorkspaceMeta } from '../api/types'
import { getLinked, setLinked } from '../context/linked'

export function Workspaces(props: IDockviewPanelProps) {
  const [list, setList] = useState<WorkspaceMeta[]>([])
  const [name, setName] = useState('')

  const load = useCallback(() => {
    api.workspaces().then(setList)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function save(): void {
    const n = name.trim()
    if (!n) return
    api
      .saveWorkspace({ name: n, linked_context: getLinked(), dockview: props.containerApi.toJSON() })
      .then(() => {
        setName('')
        load()
      })
  }

  function open(slug: string): void {
    api.getWorkspace(slug).then((doc) => {
      try {
        // `dockview` is a Dockview SerializedDockview; typed loosely across the wire.
        props.containerApi.fromJSON(doc.dockview as never)
      } catch (e) {
        // fromJSON clears the dock BEFORE validating, so a malformed/incompatible layout would
        // otherwise leave it blank (and get that blank autosaved) — recover with a default panel.
        console.error('workspace restore failed', e)
        if (props.containerApi.panels.length === 0) {
          props.containerApi.addPanel({
            id: 'RunBrowser-0',
            component: 'RunBrowser',
            title: 'Run Browser',
          })
        }
        return
      }
      if (doc.linked_context) setLinked(doc.linked_context)
    })
  }

  function remove(slug: string): void {
    void api.deleteWorkspace(slug).then(load)
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Workspaces</span>
        <span className="count">{list.length}</span>
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
          <button className="btn primary ws-save" onClick={save}>
            Save
          </button>
        </div>
        {list.length === 0 ? (
          <div className="muted">No saved workspaces — arrange panels and save one.</div>
        ) : (
          <div className="ws-list">
            {list.map((w) => (
              <div className="ws-item" key={w.slug}>
                <button className="ws-open" onClick={() => open(w.slug)}>
                  {w.name}
                </button>
                <button className="btn ws-del" title="delete" onClick={() => remove(w.slug)}>
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
