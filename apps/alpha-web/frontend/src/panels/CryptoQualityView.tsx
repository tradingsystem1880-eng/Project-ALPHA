import type {
  CryptoFeature,
  CryptoFeatureName,
  CryptoFeatures,
  CryptoQuality,
} from '../api/types'
import { shortId } from '../util/format'
import {
  cryptoCoverageStateClass,
  type CryptoFeatureInputSelection,
} from './researchDataModel'

const FEATURE_CHOICES: { id: CryptoFeatureName; label: string; description: string }[] = [
  {
    id: 'funding',
    label: 'Funding rate',
    description: 'Provider-native funding rate with exact availability time.',
  },
  {
    id: 'open_interest_change',
    label: 'Open-interest change',
    description: 'Causal change in provider-native open interest.',
  },
  {
    id: 'basis',
    label: 'Basis',
    description: 'Aligned mark, index, and premium observations for one instrument.',
  },
  {
    id: 'volatility_surface',
    label: 'Volatility surface',
    description: 'Option quotes joined to the exact instrument catalog.',
  },
  {
    id: 'liquidity',
    label: 'DEX liquidity',
    description: 'Pool liquidity retained in its native reported units.',
  },
  {
    id: 'onchain_change',
    label: 'On-chain change',
    description: 'Causal changes in the selected network metrics.',
  },
]

export function CryptoQualityView({
  quality,
  showFeatures,
  features,
  featureName,
  featureInputSelection,
  createdFeature,
  busyAction,
  onFeatureNameChange,
  onDeriveFeature,
}: {
  quality: CryptoQuality | null
  showFeatures: boolean
  features: CryptoFeatures | null
  featureName: CryptoFeatureName
  featureInputSelection: CryptoFeatureInputSelection
  createdFeature: CryptoFeature | null
  busyAction: string | null
  onFeatureNameChange: (name: CryptoFeatureName) => void
  onDeriveFeature: () => void
}) {
  return (
    <>
      {quality ? (
        <section className="provider-card" aria-label="Selected quality report">
          <div className="rd-head">
            Mechanical quality · {quality.dataset.instrument} ·{' '}
            {quality.dataset.family.replaceAll('_', ' ')}
          </div>
          <div className="crypto-detail">
            <span className={cryptoCoverageStateClass(quality.quality.state)}>
              {quality.quality.state.toUpperCase()}
            </span>
            <span>
              {quality.quality.row_count.toLocaleString()} rows ·{' '}
              {quality.quality.observed_start ?? 'no start'} →{' '}
              {quality.quality.observed_end ?? 'no end'}
            </span>
            <span>{quality.next_action}</span>
            {quality.quality.failures.length ? (
              <strong>Failures: {quality.quality.failures.join(', ')}</strong>
            ) : null}
            {quality.quality.warnings.length ? (
              <span>Warnings: {quality.quality.warnings.join(', ')}</span>
            ) : null}
            <span className="mono muted advanced-only">
              {quality.quality.dataset_sha256} · {quality.quality.method_version}
            </span>
          </div>
        </section>
      ) : null}

      {showFeatures ? (
        <section className="provider-card" aria-label="Derived research features">
          <div className="provider-card-head">
            <div className="rd-head">Derived features</div>
            <span className="chip kind">{features?.count ?? 0} frozen</span>
          </div>
          <p className="muted">
            Derivations use only the exact qualified datasets selected above. They preserve native
            provider lineage and grant no research or execution authority.
          </p>
          <div className="crypto-form-grid">
            <label>
              <span className="eyebrow">Feature</span>
              <select
                className="field"
                value={featureName}
                onChange={(event) => onFeatureNameChange(event.target.value as CryptoFeatureName)}
              >
                {FEATURE_CHOICES.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </label>
            <div className="crypto-detail">
              <span>{FEATURE_CHOICES.find((item) => item.id === featureName)?.description}</span>
              <span className={featureInputSelection.blocker ? 'muted' : 'chip pass'}>
                {featureInputSelection.blocker ?? 'EXACT INPUTS READY'}
              </span>
            </div>
            <button
              className="btn primary"
              type="button"
              disabled={busyAction !== null || featureInputSelection.blocker !== null}
              onClick={onDeriveFeature}
            >
              {busyAction === 'feature' ? 'Deriving…' : 'Freeze selected feature'}
            </button>
          </div>
          <p className="mono muted advanced-only">
            alpha crypto-data feature-create {featureName}
            {Object.entries(featureInputSelection.inputs)
              .map(([name, id]) => ` --input ${name}=${id}`)
              .join('')}
          </p>
          {createdFeature ? (
            <div className="workbench-notice" role="status">
              <strong>FROZEN AND VERIFIED · {createdFeature.feature_name.replaceAll('_', ' ')}</strong>
              <span>
                {createdFeature.row_count.toLocaleString()} rows · {createdFeature.input_count} exact
                input{createdFeature.input_count === 1 ? '' : 's'} · available{' '}
                {new Date(createdFeature.available_at).toLocaleString()}
              </span>
              <span className="mono muted advanced-only">
                feature {createdFeature.feature_id} · artifact {createdFeature.artifact_sha256}
              </span>
            </div>
          ) : null}
          <div className="crypto-coverage-list">
            {(features?.items ?? []).map((item) => (
              <article className="crypto-dataset" key={item.manifest_id}>
                <span>
                  <strong>{item.feature_name.replaceAll('_', ' ')}</strong>
                  <span className="muted">
                    {item.row_count.toLocaleString()} rows · {item.input_count} exact
                    input{item.input_count === 1 ? '' : 's'}
                  </span>
                </span>
                <span className="chip pass">{item.state.toUpperCase()}</span>
                <span className="mono muted advanced-only">
                  manifest {shortId(item.manifest_id)} · {item.method_version}
                </span>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </>
  )
}
