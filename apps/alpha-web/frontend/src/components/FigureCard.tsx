/**
 * One server-rendered figure, with the text that makes it readable.
 *
 * The image is an SVG whose text is embedded as glyph outlines, so a screen reader can
 * see nothing inside it. Everything a reader needs therefore lives in real HTML around
 * it: the alt text, the question the figure answers, what this particular run's numbers
 * say, and the uncertainty and caveat that qualify them. That is not decoration bolted
 * on — it is the only accessible copy of the figure's meaning, and it is the difference
 * between a chart you can act on and a chart you have to guess at.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { FigureCatalogueItem, FigureMetadata } from '../api/types'
import { useSettings } from '../state/settings'
import { FigureOverlay } from './FigureOverlay'
import { notesVisible } from './figureExport'

interface Props {
  runId: string
  runName?: string
  item: FigureCatalogueItem
}

/** Why a figure cannot be drawn, in words rather than a code. */
function explainUnavailable(reason: string | null): string {
  if (!reason) return 'This figure is not available for this run.'
  if (reason.startsWith('artifact_missing:'))
    return `This run did not record ${reason.slice('artifact_missing:'.length)}.`
  if (reason.startsWith('artifact_empty:'))
    return `Nothing to draw — ${reason.slice('artifact_empty:'.length)} has no rows. A backtest that never traded writes an empty file.`
  if (reason.startsWith('legacy_contract_v'))
    return `Recorded under artifact contract ${reason.slice('legacy_contract_'.length)}, which predates the sidecars this figure reads. Historical runs are never rewritten.`
  if (reason === 'snapshot_unavailable')
    return 'This run has no frozen snapshot, so its price bars cannot be reproduced exactly.'
  if (reason === 'builder_not_implemented') return 'Not implemented for this run kind yet.'
  return reason
}

export function FigureCard({ runId, runName, item }: Props) {
  const { explain } = useSettings()
  const [meta, setMeta] = useState<FigureMetadata | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showData, setShowData] = useState(false)
  const [maximised, setMaximised] = useState(false)
  const expandButton = useRef<HTMLButtonElement>(null)
  const restore = useCallback(() => {
    setMaximised(false)
    expandButton.current?.focus()
  }, [])

  useEffect(() => {
    if (!item.available) return
    let live = true
    setError(null)
    api
      .figureMetadata(runId, item.figure_id)
      .then((value) => live && setMeta(value))
      .catch((cause: unknown) => live && setError(String(cause)))
    return () => {
      live = false
    }
  }, [runId, item.figure_id, item.available])

  if (!item.available) {
    return (
      <figure className="figure-card figure-card--absent" aria-labelledby={`fig-${item.figure_id}`}>
        <figcaption className="figure-head">
          <h3 id={`fig-${item.figure_id}`}>{item.title}</h3>
          <span className="figure-flag">not available</span>
        </figcaption>
        <p className="figure-absent-reason">{explainUnavailable(item.unavailable_reason)}</p>
      </figure>
    )
  }

  if (error) {
    return (
      <figure className="figure-card figure-card--absent">
        <figcaption className="figure-head">
          <h3>{item.title}</h3>
          <span className="figure-flag figure-flag--bad">failed</span>
        </figcaption>
        <p className="figure-absent-reason">{error}</p>
      </figure>
    )
  }

  if (!meta) {
    return (
      <figure className="figure-card figure-card--loading" aria-busy="true">
        <figcaption className="figure-head">
          <h3>{item.title}</h3>
        </figcaption>
        <div className="figure-skeleton" style={{ aspectRatio: '11 / 5' }} />
        <p className="figure-summary">{item.summary}</p>
      </figure>
    )
  }

  const svg = api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'svg')
  const png = api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'png')

  return (
    <figure className="figure-card" aria-labelledby={`fig-${meta.figure_id}`}>
      {/* The figure draws its own title, subtitle, one-line answer and provenance strip --
          it has to, because an exported PNG travels without this page. Repeating them here
          would say everything twice, so the heading stays for screen readers and the
          section anchor only, and the card adds just what the image cannot carry. */}
      <figcaption className="figure-head">
        <h3 id={`fig-${meta.figure_id}`} className="sr-only">
          {meta.title} — {meta.subtitle}
        </h3>
        <div className="figure-actions">
          <button
            ref={expandButton}
            type="button"
            className="btn ghost"
            aria-haspopup="dialog"
            aria-expanded={maximised}
            onClick={() => setMaximised(true)}
          >
            Expand
          </button>
          <a className="btn ghost" href={svg} download={`${meta.figure_id}.svg`}>
            SVG
          </a>
          <a className="btn ghost" href={png} download={`${meta.figure_id}.png`}>
            PNG
          </a>
          <button
            type="button"
            className="btn ghost"
            aria-expanded={showData}
            onClick={() => setShowData((open) => !open)}
          >
            Details
          </button>
        </div>
      </figcaption>

      {/* Double-click maximises, like a chart window in a terminal; the Expand button is the
          keyboard route. */}
      <img
        className="figure-image"
        src={svg}
        alt={meta.alt_text}
        loading="lazy"
        onDoubleClick={() => setMaximised(true)}
      />

      {/* Question, uncertainty and caveat are the only accessible copy of the figure's meaning,
          so they stay in the DOM in both modes and are merely hidden from sight outside Notes. */}
      <div className={notesVisible(explain) ? 'figure-explain' : 'figure-explain sr-only'}>
        <p className="figure-question">
          <span className="eyebrow">What this answers</span>
          {meta.question}
        </p>
        <p className="figure-caveat">
          <span className="eyebrow">How sure</span>
          {meta.uncertainty}
        </p>
        <p className="figure-caveat">
          <span className="eyebrow">Read with care</span>
          {meta.caveat}
        </p>
      </div>

      {showData ? (
        <div className="figure-details">
          <table className="blotter">
            <caption className="sr-only">Panels drawn in {meta.title}</caption>
            <thead>
              <tr>
                <th scope="col">Panel</th>
                <th scope="col">Axis</th>
                <th scope="col">Unit</th>
                <th scope="col">Series</th>
              </tr>
            </thead>
            <tbody>
              {meta.panels.map((panel) => (
                <tr key={panel.panel_id}>
                  <td>{panel.panel_id}</td>
                  <td>{panel.y_label}</td>
                  <td className="mono">{panel.y_unit}</td>
                  <td>{panel.legend.length ? panel.legend.join(', ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {meta.panels.some((panel) => panel.note) ? (
            <ul className="figure-notes">
              {meta.panels
                .filter((panel) => panel.note)
                .map((panel) => (
                  <li key={panel.panel_id}>{panel.note}</li>
                ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {maximised ? <FigureOverlay runId={runId} runName={runName} meta={meta} onClose={restore} /> : null}
    </figure>
  )
}
