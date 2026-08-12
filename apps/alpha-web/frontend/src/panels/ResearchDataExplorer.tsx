// Research Data Explorer — "what data do we have, is it trustworthy, can it answer the
// question?" Registered research-only dataset refs with their exact origin bindings and
// latest audit findings, plus the stored-symbol inventory. Registration and audits are
// owner-CLI operations; this panel is a read plane.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ResearchDatasetRefRow } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import type { PanelHandleProps } from '../context/panelHandle'
import { usePanelLinked } from '../context/usePanelLinked'
import { stateChipClass } from './researchChipModel'
import {
  datasetAuditBadge,
  datasetOriginSummary,
  datasetRangeLabel,
} from './researchDataModel'

const BADGE_CHIP: Record<string, string> = {
  unaudited: 'chip',
  clean: 'chip pass',
  limiting: 'chip',
  blocking: 'chip fail',
}

export function ResearchDataExplorer(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const [datasets, setDatasets] = useState<ResearchDatasetRefRow[] | null>(null)
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [boundDatasetRefId, setBoundDatasetRefId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setDatasets(null)
    setSymbols(null)
    setBoundDatasetRefId(null)
    const projectId = panelLink.linked.projectId
    Promise.all([
      api.researchDatasets(),
      api.symbols(),
      projectId ? api.researchCase(projectId) : Promise.resolve(null),
    ])
      .then(([page, stored, researchCase]) => {
        if (!live) return
        setDatasets(page.items)
        setSymbols(stored.symbols)
        const value = researchCase?.active_contract.payload['dataset_ref_id']
        setBoundDatasetRefId(typeof value === 'string' && value ? value : null)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!live) return
        setError(reason instanceof Error ? reason.message : String(reason))
      })
    return () => {
      live = false
    }
  }, [panelLink.linked.projectId])

  const boundDataset = datasets?.find((row) => row.ref_id === boundDatasetRefId) ?? null
  const availableDatasets = (datasets ?? []).filter((row) => row.ref_id !== boundDatasetRefId)

  function DatasetRow({ row }: { row: ResearchDatasetRefRow }) {
    const badge = datasetAuditBadge(row.latest_audit as Record<string, unknown> | null)
    return (
      <div className="hypothesis-card-field">
        <span className="eyebrow">
          {row.instrument} · {row.provider} · {row.dataset_kind.replaceAll('_', ' ')}
        </span>
        <span>
          <span className={BADGE_CHIP[badge.state]}>{badge.label}</span>{' '}
          <span className="chip fail">RESEARCH ONLY</span>
        </span>
        <p className="mono">{datasetRangeLabel(row)}</p>
        <p className="mono muted">{datasetOriginSummary(row)}</p>
        <p className="mono muted advanced-only">{row.ref_id}</p>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Research Data</span>
        <span className="chip kind">READ-ONLY · RESEARCH ONLY</span>
        <span className="muted">registered refs · receipts · audits · inventory</span>
      </div>
      <div className="panel-body panel-pad workbench research-data-explorer" tabIndex={0}>
        {error ? (
          <div className="workbench-notice" role="alert">
            <strong>DATA EXPLORER UNAVAILABLE</strong>
            <span>{error}</span>
          </div>
        ) : null}
        <section aria-label="Dataset bound to current research contract">
          <div className="rd-head">Bound to the current contract</div>
          {!panelLink.linked.projectId ? (
            <Placeholder big="NO CASE SELECTED">Select a research case to see its exact data binding.</Placeholder>
          ) : boundDataset ? (
            <DatasetRow row={boundDataset} />
          ) : datasets !== null ? (
            <Placeholder big="NO DATASET BOUND">
              The current contract does not bind a registered dataset yet. Choose one through the
              proposal's compatible dataset list.
            </Placeholder>
          ) : (
            <Placeholder big="LOADING CONTRACT DATA">Checking the selected case and its exact data binding.</Placeholder>
          )}
        </section>
        <section aria-label="Globally available research datasets">
          <div className="rd-head">Globally available · not automatically bound</div>
          {datasets !== null && datasets.length === 0 ? (
            <Placeholder big="NO REGISTERED DATASETS">
              Register data fail-closed against its exact receipt or provenance bytes:
              alpha research data register SYMBOL --kind snapshot|store-slice|quantpad …
            </Placeholder>
          ) : null}
          {availableDatasets.map((row) => <DatasetRow key={row.ref_id} row={row} />)}
        </section>
        <section aria-label="Stored symbol inventory">
          <div className="rd-head">
            Stored symbols <span className="muted">({symbols?.length ?? 0})</span>
          </div>
          {symbols !== null && symbols.length === 0 ? (
            <p className="muted">The canonical store holds no symbols yet.</p>
          ) : null}
          <div className="scorecard-strip">
            {(symbols ?? []).map((symbol) => (
              <button
                key={symbol}
                type="button"
                className={stateChipClass('')}
                title="Set as the linked symbol"
                onClick={() => panelLink.setLinked({ symbol })}
              >
                {symbol}
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
