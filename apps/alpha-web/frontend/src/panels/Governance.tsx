/**
 * Governance: one place for what the working screens used to shout on every pane — authority
 * and status, Touch ID, research gates, overrides, providers, storage, glossary. `Governance` is
 * the topbar dialog (Esc closes, focus returns to the opener); `GovernanceDocument` is the same
 * pages as an MDI document (spec 2026-09-01 §4.5). Both render existing client reads only
 * (system, providers, overrides, paper sessions, crypto storage, the linked project's gate and the
 * selected run's watermark) and derive no authority in the browser.
 */

import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type {
  ActiveResearchGateOverride,
  CryptoStorage,
  PaperSession,
  ProviderDefinition,
  SystemStatus,
} from '../api/types'
import type { PanelHandleProps } from '../context/panelHandle'
import { requestResearchCase } from '../context/researchCase'
import { useActivityField } from '../state/activity'
import { Glossary } from './Glossary'
import { governancePages } from './governanceModel'
import { useLinkedProjectGate } from './useLinkedProjectGate'
import { useSelectedRunWatermark } from './useSelectedRunWatermark'

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

/** The page tree and the current page; shared by the dialog and the document. */
function GovernancePages({ beforeCaseLink }: { beforeCaseLink?: () => void }) {
  const gate = useLinkedProjectGate()
  const watermark = useSelectedRunWatermark()
  const connection = useActivityField('connection')
  const system = useRead<SystemStatus>(api.system)
  const providers = useRead<ProviderDefinition[]>(api.providers)
  const overrides = useRead<ActiveResearchGateOverride[]>(api.researchGateOverrides)
  const sessions = useRead<PaperSession[]>(api.paperSessions)
  const storage = useRead<CryptoStorage>(api.cryptoStorage)
  const [pageId, setPageId] = useState('authority')

  const pages = governancePages({
    system,
    providers,
    overrides,
    sessions,
    storage,
    gate,
    watermark,
    connection: String(connection),
  })
  const current = pages.find((item) => item.id === pageId) ?? pages[0]

  return (
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
              beforeCaseLink?.()
              requestResearchCase(current.caseLink!.projectId)
            }}
          >
            Open research case
            {current.caseLink.projectName ? ` · ${current.caseLink.projectName}` : ''}
          </button>
        ) : null}
      </section>
    </div>
  )
}

/** Governance as an MDI document: no modal, no focus trap, the MDI tab closes it. */
export function GovernanceDocument(_props: PanelHandleProps) {
  return (
    <div className="panel governance-document">
      <div className="panel-toolbar">
        <span className="title">Governance</span>
        <span className="muted">authority, gates, providers, storage — relayed, never derived</span>
      </div>
      <GovernancePages />
    </div>
  )
}

export function Governance({ onClose }: Props) {
  const box = useRef<HTMLDivElement>(null)

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
        <GovernancePages beforeCaseLink={onClose} />
      </div>
    </div>
  )
}
