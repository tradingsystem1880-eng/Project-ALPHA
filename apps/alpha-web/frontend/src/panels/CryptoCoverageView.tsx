import type { CryptoCoverageItem } from '../api/types'
import { shortId } from '../util/format'
import { cryptoCoverageStateClass, type CryptoDataSection } from './researchDataModel'

export function CryptoCoverageView({
  section,
  loading,
  items,
  latestManifestIds,
  selectedManifestIds,
  busyAction,
  onToggle,
  onInspectQuality,
}: {
  section: CryptoDataSection
  loading: boolean
  items: CryptoCoverageItem[]
  latestManifestIds: Set<string>
  selectedManifestIds: Set<string>
  busyAction: string | null
  onToggle: (item: CryptoCoverageItem) => void
  onInspectQuality: (item: CryptoCoverageItem) => void
}) {
  return (
    <section aria-label="Crypto coverage">
      <div className="rd-head">
        {section === 'quality' ? 'All coverage and quality' : 'Available coverage'} ·{' '}
        {latestManifestIds.size} current{' '}
        <span className="advanced-only">· {items.length} immutable versions</span>
      </div>
      {loading ? <p className="muted">Loading exact manifests and qualification reports…</p> : null}
      {!loading && items.length === 0 ? (
        <p className="muted">
          No dataset in this family has been acquired yet. Estimate one bounded acquisition above.
        </p>
      ) : null}
      <div className="crypto-coverage-list">
        {items.map((item) => (
          <article
            className={`crypto-dataset ${selectedManifestIds.has(item.manifest_id) ? 'selected' : ''}${latestManifestIds.has(item.manifest_id) ? '' : ' advanced-only'}`}
            key={item.manifest_id}
          >
            <label className="crypto-dataset-select">
              <input
                type="checkbox"
                checked={selectedManifestIds.has(item.manifest_id)}
                disabled={item.state !== 'qualified'}
                onChange={() => onToggle(item)}
                aria-label={`Select ${item.state} ${item.family} ${item.instrument} ${item.quote_asset ?? 'no quote asset'}`}
              />
              <span>
                <strong>{item.instrument}</strong>
                <span>{item.family.replaceAll('_', ' ')} · {item.provider}/{item.venue}</span>
              </span>
            </label>
            <span className={cryptoCoverageStateClass(item.state)}>{item.state.toUpperCase()}</span>
            <span className="mono">{item.row_count.toLocaleString()} rows · {item.frequency}</span>
            <span className="muted">
              {item.quote_asset ?? 'no quote'} · {item.units}
              {item.fetched_at
                ? ` · fetched ${new Date(item.fetched_at).toLocaleString()}`
                : ' · legacy receipt time unavailable'}
            </span>
            <button
              className="btn"
              type="button"
              disabled={busyAction === `quality:${item.manifest_id}`}
              onClick={() => onInspectQuality(item)}
            >
              Quality
            </button>
            <span className="mono muted advanced-only">
              manifest {shortId(item.manifest_id)} · artifact {shortId(item.artifact_sha256)} ·{' '}
              {item.method_version}
            </span>
          </article>
        ))}
      </div>
    </section>
  )
}
