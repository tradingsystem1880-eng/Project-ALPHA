import { api } from '../api/client'
import type { FigureMetadata } from '../api/types'
import { type FigureVariant, variantFileName } from './figureVariant'

interface Props {
  runId: string
  meta: FigureMetadata
  variant: FigureVariant
  onExpand: () => void
}

/** One immutable, noninteractive scientific image surface. The chart is always white, on both screen themes. */
export function FigureSurface({ runId, meta, variant, onExpand }: Props) {
  const url = (fmt: 'svg' | 'png') => api.figureImageUrl(runId, meta.figure_id, meta.cache_key, fmt, variant)
  return (
    <div className="figure-surface" data-variant={variant}>
      <div className="figure-surface-title">
        <span>{variant === 'plain' ? 'Plain chart' : 'Annotated chart'} · static</span>
        <a className="btn" href={url('svg')} download={variantFileName(meta.figure_id, variant, 'svg')}>
          SVG
        </a>
        <a className="btn" href={url('png')} download={variantFileName(meta.figure_id, variant, 'png')}>
          PNG
        </a>
      </div>
      <img className="figure-image" src={url('svg')} alt={meta.alt_text} loading="lazy" onDoubleClick={onExpand} />
      <small>stored figure</small>
      {meta.truncation_note ? <p>{meta.truncation_note}</p> : null}
    </div>
  )
}
