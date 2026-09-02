/**
 * The Governance dialog: one place for what the working screens used to shout on every pane —
 * authority and status, Touch ID, research gates, overrides, providers, storage, glossary.
 * Opened from the topbar; Esc closes and focus returns to the opener. It renders existing client
 * reads only (system, providers, overrides, paper sessions, crypto storage, the linked project's
 * gate and the selected run's watermark) and derives no authority in the browser.
 */

import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type {
  ActiveResearchGateOverride,
  CryptoStorage,
  PaperSession,
  ProviderDefinition,
  RunDetail,
  SystemStatus,
} from '../api/types'
import { useLinked } from '../context/linked'
import { requestResearchCase } from '../context/researchCase'
import { useActivityField } from '../state/activity'
import { Glossary } from './Glossary'
import { governancePages } from './governanceModel'
import { researchGateWatermark } from './researchGateModel'
import { useLinkedProjectGate } from './useLinkedProjectGate'

interface Props {
  onClose: () => void
}

function useRead<T>(read: () => Promise<T>): T | null {
  const [value, setValue] = useState<T | null>(null)
  useEffect(() => {
    let live = true
    read()
      .then((result) => live && setValue(result))
      .catch(() => live && setValue(null))
    return () => {
      live = false
    }
  }, [read])
  return value
}

export function Governance({ onClose }: Props) {
  const linked = useLinked()
  const gate = useLinkedProjectGate()
  const connection = useActivityField('connection')
  const system = useRead<SystemStatus>(api.system)
  const providers = useRead<ProviderDefinition[]>(api.providers)
  const overrides = useRead<ActiveResearchGateOverride[]>(api.researchGateOverrides)
  const sessions = useRead<PaperSession[]>(api.paperSessions)
  const storage = useRead<CryptoStorage>(api.cryptoStorage)
  const [run, setRun] = useState<RunDetail | null>(null)
  const [pageId, setPageId] = useState('authority')
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const runId = linked.runId
    if (!runId) {
      setRun(null)
      return
    }
    let live = true
    api
      .run(runId)
      .then((detail) => live && setRun(detail))
      .catch(() => live && setRun(null))
    return () => {
      live = false
    }
  }, [linked.runId])

  useEffect(() => {
    const root = box.current
    if (!root) return
    const controls = () =>
      [...root.querySelectorAll<HTMLElement>('button:not([disabled]), input, [tabindex="0"]')]
    controls()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const items = controls()
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [onClose])

  const pages = governancePages({
    system,
    providers,
    overrides,
    sessions,
    storage,
    gate,
    watermark: researchGateWatermark(run),
    connection: String(connection),
  })
  const current = pages.find((item) => item.id === pageId) ?? pages[0]

  return (
    <div className="shell-modal" role="presentation" onClick={onClose}>
      <div
        ref={box}
        className="shell-modal-box governance"
        role="dialog"
        aria-modal="true"
        aria-label="Governance"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="shell-modal-head">
          <b>Governance</b>
          <span className="muted">authority, gates, providers, storage — relayed, never derived</span>
          <span className="spacer" />
          <button type="button" className="btn ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="governance-body">
          <nav className="report-tree governance-tree">
            <ul role="tree" aria-label="Governance pages">
              {pages.map((item) => (
                <li key={item.id} role="treeitem" aria-selected={item.id === current.id}>
                  <button
                    type="button"
                    className={`tree-leaf${item.id === current.id ? ' active' : ''}`}
                    onClick={() => setPageId(item.id)}
                  >
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
          <section className="governance-page" aria-label={current.label}>
            <h2>{current.label}</h2>
            {current.id === 'glossary' ? (
              <Glossary />
            ) : current.rows.length ? (
              <table className="blotter governance-table">
                <tbody>
                  {current.rows.map((row) => (
                    <tr key={`${row.label}:${row.value}`} data-tone={row.tone}>
                      <td className="k">{row.label}</td>
                      <td className={`tone-${row.tone}`}>{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">{current.empty}</p>
            )}
            {current.caseLink ? (
              <button
                type="button"
                className="btn"
                onClick={() => {
                  onClose()
                  requestResearchCase(current.caseLink!.projectId)
                }}
              >
                Open research case
                {current.caseLink.projectName ? ` · ${current.caseLink.projectName}` : ''}
              </button>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  )
}
