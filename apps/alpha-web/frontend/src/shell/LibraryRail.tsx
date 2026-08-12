/**
 * The Library: everything you own, in one place, always present.
 *
 * Previously a run, a symbol and a project each lived inside a different floating panel
 * you had to find and open. There was no answer to "where are my things" — only "which
 * window did I put them in". The rail is that answer: one tree of Runs, Symbols, Projects
 * and Workspaces, open on every screen, that sets the shared context when you click.
 */

import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem, WorkspaceMeta } from '../api/types'
import { restoreLinked, setLinked, useLinked } from '../context/linked'
import { useActivityField } from '../state/activity'
import { shortId } from '../util/format'

type SectionId = 'runs' | 'symbols' | 'projects' | 'workspaces'
type RunScope = 'project' | 'standalone' | 'historical' | 'all'

const SECTIONS: { id: SectionId; label: string; hint: string }[] = [
  { id: 'runs', label: 'Runs', hint: 'every completed run' },
  { id: 'symbols', label: 'Symbols', hint: 'what has stored bars' },
  { id: 'projects', label: 'Projects', hint: 'governed strategy work' },
  { id: 'workspaces', label: 'Workspaces', hint: 'saved research context' },
]

function verdictClass(item: RunListItem): string {
  if (item.passed === true) return 'ok'
  if (item.passed === false) return 'bad'
  return ''
}

export function LibraryRail({
  onOpenRun,
  collapsed,
  onToggle,
}: {
  onOpenRun: (runId: string) => void
  collapsed: boolean
  onToggle: () => void
}) {
  const linked = useLinked()
  const [section, setSection] = useState<SectionId>('runs')
  const [query, setQuery] = useState('')
  const [runs, setRuns] = useState<RunListItem[]>([])
  const [runScope, setRunScope] = useState<RunScope>(linked.projectId ? 'project' : 'all')
  const [symbols, setSymbols] = useState<string[]>([])
  const [projects, setProjects] = useState<{ project_id: string; name?: string | null }[]>([])
  const [projectHasMore, setProjectHasMore] = useState(false)
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  // The activity stream ticks whenever the store changes, so a run launched from the CLI
  // or an agent appears here without a reload — the rail is a live view, not a snapshot.
  const storeRevision = useActivityField('runsVersion')

  useEffect(() => {
    setRunScope(linked.projectId ? 'project' : 'all')
  }, [linked.projectId])

  useEffect(() => {
    let live = true
    setError(null)
    const load = async () => {
      try {
        if (section === 'runs') {
          const list = await api.runs('?limit=500')
          if (live) setRuns(list.items)
        } else if (section === 'symbols') {
          const list = await api.symbols()
          if (live) setSymbols(list.symbols)
        } else if (section === 'projects') {
          const page = await api.projects(100, 0)
          if (live) {
            setProjects(page.items as { project_id: string; name?: string | null }[])
            setProjectHasMore(page.has_more)
          }
        } else {
          const list = await api.workspaces()
          if (live) setWorkspaces(list)
        }
      } catch (cause) {
        if (live) setError(String(cause))
      }
    }
    void load()
    return () => {
      live = false
    }
  }, [section, storeRevision])

  const needle = query.trim().toLowerCase()
  const visibleRuns = useMemo(
    () =>
      runs.filter(
        (item) =>
          (runScope === 'all'
            || (runScope === 'project'
              && item.run_context_kind === 'governed_project'
              && item.run_context_project_id === linked.projectId)
            || (runScope === 'standalone' && item.run_context_kind === 'standalone_sandbox')
            || (runScope === 'historical' && item.run_context_kind === 'legacy_context_unknown'))
          && (!needle ||
            item.run_id.includes(needle) ||
            (item.label ?? '').toLowerCase().includes(needle) ||
            (item.command ?? '').toLowerCase().includes(needle)),
      ),
    [linked.projectId, needle, runScope, runs],
  )
  const visibleSymbols = useMemo(
    () => symbols.filter((symbol) => !needle || symbol.toLowerCase().includes(needle)),
    [symbols, needle],
  )
  const visibleProjects = useMemo(
    () => projects.filter((project) =>
      !needle
      || project.project_id.toLowerCase().includes(needle)
      || (project.name ?? '').toLowerCase().includes(needle)),
    [projects, needle],
  )

  async function loadMoreProjects(): Promise<void> {
    if (projectsLoading || !projectHasMore) return
    setProjectsLoading(true)
    setError(null)
    try {
      const page = await api.projects(100, projects.length)
      setProjects((current) => [
        ...current,
        ...(page.items as { project_id: string; name?: string | null }[]),
      ])
      setProjectHasMore(page.has_more)
    } catch (cause) {
      setError(String(cause))
    } finally {
      setProjectsLoading(false)
    }
  }

  if (collapsed) {
    return (
      <nav className="library library--collapsed" aria-label="Library">
        <button className="library-toggle" onClick={onToggle} title="Show the library">
          ›
        </button>
      </nav>
    )
  }

  return (
    <nav className="library" aria-label="Library">
      <div className="library-head">
        <span className="eyebrow">Library</span>
        <button className="library-toggle" onClick={onToggle} title="Hide the library">
          ‹
        </button>
      </div>

      <div className="library-sections" role="tablist" aria-label="Library sections">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            role="tab"
            aria-selected={section === item.id}
            className={`library-section${section === item.id ? ' active' : ''}`}
            title={item.hint}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <input
        className="library-search field"
        value={query}
        placeholder="Filter…"
        spellCheck={false}
        onChange={(event) => setQuery(event.target.value)}
        aria-label={`Filter ${section}`}
      />

      {error ? <p className="library-error">{error}</p> : null}

      {section === 'runs' ? (
        <label className="library-run-scope">
          <span className="eyebrow">Show</span>
          <select
            className="field"
            value={runScope}
            onChange={(event) => setRunScope(event.target.value as RunScope)}
          >
            <option value="project" disabled={!linked.projectId}>Current project</option>
            <option value="standalone">Standalone · non-evidence</option>
            <option value="historical">Historical · context unknown</option>
            <option value="all">All runs</option>
          </select>
        </label>
      ) : null}

      <div className="library-list">
        {section === 'runs'
          ? visibleRuns.map((item) => (
              <button
                key={item.run_id}
                className={`library-row${linked.runId === item.run_id ? ' active' : ''}`}
                onClick={() => onOpenRun(item.run_id)}
                title={`${item.command ?? item.kind} · ${item.run_id}`}
              >
                <span className="library-row-main">
                  <span className="mono">{shortId(item.run_id)}</span>
                  <span className="library-row-sub">{item.label ?? item.command ?? item.kind}</span>
                </span>
                {item.run_context_kind === 'standalone_sandbox' ? (
                  <span className="chip warn">STANDALONE</span>
                ) : item.run_context_kind === 'legacy_context_unknown' ? (
                  <span className="chip">HISTORICAL</span>
                ) : null}
                {item.verdict ? (
                  <span className={`grade ${verdictClass(item)}`}>{item.verdict}</span>
                ) : null}
              </button>
            ))
          : null}

        {section === 'symbols'
          ? visibleSymbols.map((symbol) => (
              <button
                key={symbol}
                className={`library-row${linked.symbol === symbol ? ' active' : ''}`}
                onClick={() => setLinked({ symbol })}
              >
                <span className="library-row-main mono">{symbol}</span>
              </button>
            ))
          : null}

        {section === 'projects'
          ? visibleProjects.map((project) => (
              <button
                key={project.project_id}
                className={`library-row${linked.projectId === project.project_id ? ' active' : ''}`}
                onClick={() => setLinked({ projectId: project.project_id })}
              >
                <span className="library-row-main">
                  <span className="mono">{shortId(project.project_id)}</span>
                  <span className="library-row-sub">{project.name ?? 'project'}</span>
                </span>
              </button>
            ))
          : null}
        {section === 'projects' && projectHasMore && !needle ? (
          <button
            type="button"
            className="btn library-load-more"
            disabled={projectsLoading}
            onClick={() => void loadMoreProjects()}
          >
            {projectsLoading ? 'Loading…' : 'Load more projects'}
          </button>
        ) : null}

        {section === 'workspaces' ? (
          <>
            {/* Saving has to live here. The rail is the only place workspaces appear now,
                so without this the list could only ever be empty. */}
            <form
              className="library-save"
              onSubmit={(event) => {
                event.preventDefault()
                const name = draft.trim()
                if (!name) return
                setError(null)
                void api
                  .saveWorkspace({ name, linked_context: linked })
                  .then(() => {
                    setDraft('')
                    return api.workspaces().then(setWorkspaces)
                  })
                  .catch((cause: unknown) => setError(String(cause)))
              }}
            >
              <input
                className="field"
                value={draft}
                placeholder="Name this context…"
                aria-label="New workspace name"
                onChange={(event) => setDraft(event.target.value)}
              />
              <button className="btn" type="submit" disabled={!draft.trim()}>
                Save
              </button>
            </form>
            {workspaces.map((workspace) => (
              <button
                key={workspace.slug}
                className="library-row"
                onClick={() => {
                  void api.getWorkspace(workspace.slug).then((doc) => {
                    if (doc.linked_context) restoreLinked(doc.linked_context)
                  })
                }}
              >
                <span className="library-row-main">{workspace.name}</span>
              </button>
            ))}
            {!workspaces.length ? (
              <p className="library-empty">
                Nothing saved yet. A workspace stores the symbol, window, project and run above —
                not a window arrangement.
              </p>
            ) : null}
          </>
        ) : null}

        {section === 'runs' && !visibleRuns.length ? (
          <p className="library-empty">No runs match.</p>
        ) : null}
      </div>
    </nav>
  )
}
