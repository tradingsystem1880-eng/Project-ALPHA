/**
 * Workspaces: saved research context, not saved window positions.
 *
 * A workspace used to be a serialised dock layout — where you had dragged your panels.
 * That is not something worth naming and returning to. What is worth returning to is *what
 * you were working on*: the symbol, the window, the project and version, the data snapshot.
 * Restoring that puts every screen back on the same problem, which is what "resume my work"
 * should have meant all along.
 *
 * Documents written by the old shell still carry their layout blob; it is read and ignored.
 */

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { PanelHandleProps } from '../context/panelHandle'
import type { WorkspaceMeta } from '../api/types'
import { getLinked, restoreLinked, useLinked } from '../context/linked'

function slugify(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

export function Workspaces(_props: PanelHandleProps) {
  const linked = useLinked()
  const [items, setItems] = useState<WorkspaceMeta[]>([])
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(() => {
    api
      .workspaces()
      .then(setItems)
      .catch((cause: unknown) => setError(String(cause)))
  }, [])

  useEffect(refresh, [refresh])

  const save = async () => {
    const slug = slugify(name)
    if (!slug) {
      setError('Give the workspace a name first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const current = getLinked()
      await api.saveWorkspace(slug, {
        name: name.trim(),
        linked_context: current as never,
      })
      setName('')
      refresh()
    } catch (cause) {
      setError(String(cause))
    } finally {
      setBusy(false)
    }
  }

  const load = async (slug: string) => {
    try {
      const doc = await api.getWorkspace(slug)
      if (doc.linked_context) restoreLinked(doc.linked_context)
    } catch (cause) {
      setError(String(cause))
    }
  }

  const remove = async (slug: string) => {
    try {
      await api.deleteWorkspace(slug)
      refresh()
    } catch (cause) {
      setError(String(cause))
    }
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Workspaces</span>
        <span className="muted">saved research context</span>
      </div>
      <div className="panel-body">
        <p className="muted">
          Saves what you are working on — symbol, window, project, version, snapshot — so every
          screen can return to it. It does not save panel positions.
        </p>

        <div className="workspace-save">
          <input
            className="field"
            value={name}
            placeholder="Name this context"
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && void save()}
          />
          <button className="btn primary" disabled={busy} onClick={() => void save()}>
            Save current
          </button>
        </div>

        <p className="workspace-current muted mono">
          {linked.symbol ?? 'no symbol'} · {linked.start ?? 'start'} → {linked.end ?? 'latest'}
          {linked.projectId ? ` · ${linked.projectId}` : ''}
        </p>

        {error ? <p className="workspace-error">{error}</p> : null}

        <ul className="workspace-list">
          {items.map((item) => (
            <li key={item.slug}>
              <button className="btn ghost" onClick={() => void load(item.slug)}>
                {item.name}
              </button>
              <button
                className="btn ghost"
                title={`Delete ${item.name}`}
                onClick={() => void remove(item.slug)}
              >
                ✕
              </button>
            </li>
          ))}
          {!items.length ? <li className="muted">Nothing saved yet.</li> : null}
        </ul>
      </div>
    </div>
  )
}
