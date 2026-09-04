// Research Backlog — the Command Center's case list, served by the ADR-0021 read-only
// GET /api/research/cases route. Buckets, ordering, and progress all come from the
// already-tested researchCockpitModel; selecting a case writes only linked projectId.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { useAreaVersion } from '../state/activity'
import { Placeholder } from '../components/Placeholder'
import type { PanelHandleProps } from '../context/panelHandle'
import { usePanelLinked } from '../context/usePanelLinked'
import { groupResearchBacklog } from './researchBacklogModel'
import {
  researchCaseProgress,
  researchPhaseLabel,
  type ResearchCaseSummary,
} from './researchCockpitModel'

const ACTIVE_POLL_MS = 5_000
const ERROR_POLL_MS = 10_000

function progressLabel(row: ResearchCaseSummary): string {
  const progress = researchCaseProgress(row)
  const milestones = `${row.completed_milestones}/${row.total_milestones} milestones`
  if (progress.budget_fraction === null) return milestones
  return `${milestones} · ${Math.round(progress.budget_fraction * 100)}% of ${row.budget.unit}`
}

export function ResearchBacklog(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const [rows, setRows] = useState<ResearchCaseSummary[] | null>(null)
  const researchVersion = useAreaVersion('research')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    let timer = 0
    const poll = async (): Promise<void> => {
      try {
        const page = await api.researchCases({ limit: 100 })
        if (!live) return
        setRows(page.items)
        setError(null)
        timer = window.setTimeout(() => void poll(), ACTIVE_POLL_MS)
      } catch (reason) {
        if (!live) return
        setError(reason instanceof Error ? reason.message : String(reason))
        timer = window.setTimeout(() => void poll(), ERROR_POLL_MS)
      }
    }
    void poll()
    return () => {
      live = false
      window.clearTimeout(timer)
    }
    // A case the CLI or the AI over MCP touches on disk re-lists here without a click.
  }, [researchVersion])

  const groups = groupResearchBacklog(rows ?? [])
  const selected = panelLink.linked.projectId

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Research Backlog</span>
        <span className="chip kind">READ-ONLY</span>
        <span className="muted">every case · newest research activity first</span>
      </div>
      <div className="panel-body panel-pad research-backlog" tabIndex={0}>
        {error ? (
          <div className="workbench-notice" role="alert">
            <strong>BACKLOG UNAVAILABLE</strong>
            <span>{error}</span>
          </div>
        ) : null}
        {rows !== null && rows.length === 0 ? (
          <Placeholder big="NO RESEARCH CASES YET">
            Use New Idea to capture your first observation — in your exact words, with no
            trading rules asked.
          </Placeholder>
        ) : null}
        {groups.map((group) => (
          <section key={group.bucket} className="backlog-bucket" aria-label={group.label}>
            <div className="rd-head">
              {group.label} <span className="muted">({group.cases.length})</span>
            </div>
            <ul className="backlog-list">
              {group.cases.map((row) => (
                <li key={row.case_id}>
                  <button
                    type="button"
                    className={`backlog-row${selected === row.case_id ? ' selected' : ''}`}
                    onClick={() => panelLink.setLinked({ projectId: row.case_id })}
                    title={row.original_idea}
                  >
                    <span className="backlog-title">{row.title}</span>
                    <span className="backlog-meta mono">
                      {researchPhaseLabel(row.phase).toUpperCase()} · {row.execution_state}
                      {' · '}
                      {row.responsibility === 'owner' ? 'needs you' : 'codex'}
                    </span>
                    <span className="backlog-next">{row.next_action}</span>
                    <span className="backlog-progress muted">{progressLabel(row)}</span>
                    {row.blocker ? (
                      <span className="chip fail" title={row.blocker}>
                        BLOCKED
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
