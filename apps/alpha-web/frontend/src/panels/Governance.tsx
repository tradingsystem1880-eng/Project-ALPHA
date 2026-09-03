/**
 * Governance: one place for what the working screens used to shout on every pane — authority
 * and status, Touch ID, research gates, overrides, providers, storage, glossary. It is an MDI
 * document (spec 2026-09-01 §4.5) opened from the toolbar, the status chip and the View menu; the
 * MDI tab closes it. It renders existing client reads only (system, providers, overrides, paper
 * sessions, crypto storage, the linked project's gate and the selected run's watermark) and
 * derives no authority in the browser.
 */

import { useEffect, useState } from 'react'

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

/** The page tree and the current page. */
function GovernancePages() {
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
      <nav className="report-tree governance-tree" tabIndex={0}>
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
      <section className="governance-page" aria-label={current.label} tabIndex={0}>
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

/** Governance as an MDI document; the MDI tab closes it. */
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
