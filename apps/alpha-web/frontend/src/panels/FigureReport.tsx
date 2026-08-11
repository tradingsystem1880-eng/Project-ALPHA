/**
 * The figure-driven run report.
 *
 * A scrolling report with a sticky section rail rather than tabs. Tabs hid most of a run
 * behind a click and, worse, only ever appeared for `validate` runs — a plain backtest
 * fell through to one flat unstructured page. Sections come from the figure catalogue, so
 * every run kind gets the same readable spine and a new figure needs no wiring here.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { FigureCard } from '../components/FigureCard'
import { Placeholder } from '../components/Placeholder'
import { api } from '../api/client'
import type { FigureCatalogue, FigureCatalogueItem } from '../api/types'

/** Reading order: what happened, how it traded, what it risked, whether to believe it. */
const SECTION_ORDER = [
  'performance',
  'signals',
  'trades',
  'risk',
  'robustness',
  'optimisation',
  'portfolio',
  'propfirm',
  'forecast',
] as const

const SECTION_TITLES: Record<string, string> = {
  performance: 'Performance',
  signals: 'Signals',
  trades: 'Trades',
  risk: 'Risk',
  robustness: 'Can we believe it',
  optimisation: 'Parameter search',
  portfolio: 'Portfolio',
  propfirm: 'Prop firm',
  forecast: 'Forecast',
}

function grouped(items: FigureCatalogueItem[]): [string, FigureCatalogueItem[]][] {
  const buckets = new Map<string, FigureCatalogueItem[]>()
  for (const item of items) {
    const bucket = buckets.get(item.section) ?? []
    bucket.push(item)
    buckets.set(item.section, bucket)
  }
  const ordered = [...buckets.keys()].sort((a, b) => {
    const ai = SECTION_ORDER.indexOf(a as (typeof SECTION_ORDER)[number])
    const bi = SECTION_ORDER.indexOf(b as (typeof SECTION_ORDER)[number])
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi)
  })
  return ordered.map((section) => [section, buckets.get(section) ?? []])
}

export function FigureReport({ runId }: { runId: string }) {
  const [catalogue, setCatalogue] = useState<FigureCatalogue | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState<string>('')
  const container = useRef<HTMLDivElement>(null)

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

  const sections = useMemo(() => grouped(catalogue?.items ?? []), [catalogue])

  useEffect(() => {
    if (!sections.length) return
    setActive((current) => current || sections[0][0])
  }, [sections])

  // Highlight the section the reader is actually looking at, so the rail is a position
  // indicator rather than just a menu.
  useEffect(() => {
    const root = container.current
    if (!root || !sections.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
        if (visible?.target.id) setActive(visible.target.id.replace('section-', ''))
      },
      { root, rootMargin: '-10% 0px -70% 0px', threshold: 0 },
    )
    for (const [section] of sections) {
      const node = root.querySelector(`#section-${section}`)
      if (node) observer.observe(node)
    }
    return () => observer.disconnect()
  }, [sections])

  if (error) return <Placeholder big="Could not load figures">{error}</Placeholder>
  if (!catalogue) return <Placeholder big="Reading the figure catalogue…" />
  if (!sections.length)
    return <Placeholder big="No figures for this run kind yet" />

  const drawable = catalogue.items.filter((item) => item.available).length

  return (
    <div className="figure-report">
      <nav className="figure-rail" aria-label="Report sections">
        <p className="eyebrow">Report</p>
        <ul>
          {sections.map(([section, items]) => (
            <li key={section}>
              <a
                href={`#section-${section}`}
                className={section === active ? 'active' : undefined}
                aria-current={section === active ? 'true' : undefined}
              >
                {SECTION_TITLES[section] ?? section}
                <span className="figure-rail-count">
                  {items.filter((item) => item.available).length}
                </span>
              </a>
            </li>
          ))}
        </ul>
        <p className="figure-rail-foot muted">
          {drawable} of {catalogue.items.length} figures available
        </p>
      </nav>

      <div className="figure-scroll" ref={container}>
        {sections.map(([section, items]) => (
          <section key={section} id={`section-${section}`} className="figure-section">
            <h2>{SECTION_TITLES[section] ?? section}</h2>
            {items.map((item) => (
              <FigureCard key={item.figure_id} runId={runId} item={item} />
            ))}
          </section>
        ))}
      </div>
    </div>
  )
}
