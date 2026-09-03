// One section of the figure-driven report: the figures a report-tree leaf points at, each carrying
// the question it answers. The tree that selects the section lives in rundetail/index.tsx.

import { useEffect, useState } from 'react'

import { FigureCard } from '../components/FigureCard'
import { Placeholder } from '../components/Placeholder'
import { api } from '../api/client'
import type { FigureCatalogue, FigureCatalogueItem } from '../api/types'

export function FigureSection({
  runId,
  runName,
  title,
  items,
  reason,
}: {
  runId: string
  /** The run's display name for the maximised header; the id when unknown. */
  runName?: string
  title: string
  items: FigureCatalogueItem[]
  reason: string | null
}) {
  if (!items.length) return <Placeholder big={title}>{reason ?? 'no figures'}</Placeholder>
  return (
    <section className="figure-section" aria-label={title}>
      <h2>{title}</h2>
      {items.map((item) => (
        <FigureCard key={item.figure_id} runId={runId} runName={runName} item={item} />
      ))}
    </section>
  )
}

/** Every drawable figure of one run in catalogue order — the Evidence Hub's exploration view. */
export function RunFigures({ runId }: { runId: string }) {
  const [catalogue, setCatalogue] = useState<FigureCatalogue | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setCatalogue(null)
    setError(null)
    api
      .figures(runId)
      .then((value) => live && setCatalogue(value))
      .catch((cause: unknown) => live && setError(String(cause)))
    return () => {
      live = false
    }
  }, [runId])
  if (error) return <Placeholder big="Figures unavailable">{error}</Placeholder>
  if (!catalogue) return <Placeholder big="Loading figures">run {runId.slice(0, 8)}</Placeholder>
  return (
    <FigureSection
      runId={runId}
      title={`Run ${runId.slice(0, 8)}`}
      items={catalogue.items}
      reason="no figures recorded for this run"
    />
  )
}
