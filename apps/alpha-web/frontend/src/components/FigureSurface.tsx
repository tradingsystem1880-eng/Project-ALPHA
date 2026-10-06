import { api } from '../api/client'
import type { FigureMetadata } from '../api/types'
/** One immutable, noninteractive scientific image surface shared by reports and workspaces. */
export function FigureSurface({ runId, meta, onExpand }: { runId: string; meta: FigureMetadata; onExpand: () => void }) {
  return <div className="figure-surface"><div className="figure-surface-title"><span>Static figure · noninteractive</span><a className="btn" href={api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'svg')} download={`${meta.figure_id}.svg`}>SVG</a><a className="btn" href={api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'png')} download={`${meta.figure_id}.png`}>PNG</a></div><img className="figure-image" src={api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'svg')} alt={meta.alt_text} loading="lazy" onDoubleClick={onExpand}/>{meta.truncation_note ? <p>{meta.truncation_note}</p> : null}</div>
}
