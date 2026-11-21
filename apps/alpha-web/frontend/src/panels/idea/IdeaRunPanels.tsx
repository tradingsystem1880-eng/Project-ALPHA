// Sections 6 and 7 of the idea page: the charts and the checks of the ONE selected run. The charts
// are the real server-rendered figures (`FigureCard`), one per row, full width. The checks reuse the
// run report's reading block and Gates cards. Nothing is redrawn here.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { FigureCatalogue, IdeaTest, RunDetail } from '../../api/types'
import { FigureCard } from '../../components/FigureCard'
import { ReadingBlock } from '../../components/ReadingBlock'
import type { ValidateManifest } from '../../explain/types'
import { Gates } from '../rundetail/Gates'
import { parseReading } from '../readingModel'

type Load<T> = { runId: string; value: T } | { runId: string; error: string }
const words = (cause: unknown): string => (cause instanceof Error ? cause.message : String(cause))
const GATE_KEYS = ['dsr', 'cpcv', 'cis', 'nulls', 'verdict'] as const

function useLoaded<T>(runId: string, read: (id: string) => Promise<T>): Load<T> | null {
  const [state, setState] = useState<Load<T> | null>(null)
  useEffect(() => {
    let live = true
    read(runId).then(
      value => { if (live) setState({ runId, value }) },
      (cause: unknown) => { if (live) setState({ runId, error: words(cause) }) },
    )
    return () => { live = false }
  }, [runId, read])
  return state && state.runId === runId ? state : null
}

export function RunCharts({ run }: { run: IdeaTest }) {
  const state = useLoaded<FigureCatalogue>(run.id, api.figures)
  const wanted = useMemo(() => new Set(run.figures_available), [run.figures_available])
  if (!wanted.size) return <p className="idea-empty">This run has no figure that can be drawn. Nothing is shown in its place.</p>
  if (!state) return <p className="muted" role="status">Loading the figures of run {run.id.slice(0, 8)}…</p>
  if ('error' in state) return <p role="alert" className="idea-error">{state.error}</p>
  const items = state.value.items.filter(item => item.available && wanted.has(item.figure_id))
  if (!items.length) return <p className="idea-empty">The figure catalogue lists none of this run’s figures as drawable.</p>
  return (
    <div className="idea-figures">
      <p className="muted">Each chart is drawn from the stored run, full width. “Expand” opens it full screen.</p>
      {items.map(item => (
        <section key={item.figure_id} className="idea-figure" aria-label={item.title}>
          <h4>{item.title}</h4>
          <p className="idea-figure-says">{item.summary}</p>
          <FigureCard runId={run.id} runName={`Run ${run.id.slice(0, 8)}`} item={item} />
        </section>
      ))}
    </div>
  )
}

export function RunChecks({ run }: { run: IdeaTest }) {
  const detail = useLoaded<RunDetail>(run.id, api.run)
  const reading = useMemo(() => parseReading(run.reading), [run.reading])
  const manifest = detail && 'value' in detail ? (detail.value.manifest as ValidateManifest) : null
  const hasGates = manifest !== null && GATE_KEYS.some(key => (manifest as Record<string, unknown>)[key] !== undefined)
  return (
    <div className="idea-checks">
      <ReadingBlock reading={reading} labels={run.labels} />
      {!detail ? <p className="muted" role="status">Loading the check cards…</p> : null}
      {detail && 'error' in detail ? <p role="alert" className="idea-error">{detail.error}</p> : null}
      {manifest && hasGates ? <Gates manifest={manifest} runId={run.id} /> : null}
      {manifest && !hasGates ? <p className="idea-empty">This run stored no gate blocks, so there are no check cards to draw.</p> : null}
    </div>
  )
}
