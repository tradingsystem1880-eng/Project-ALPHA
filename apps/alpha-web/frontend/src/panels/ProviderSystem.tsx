// Provider and system control plane — local readiness only. The backend projection deliberately
// performs no implicit network probes and exposes credential names/presence, never values.

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ProviderDefinition, SystemStatus } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { missingCredentialNames, providerReadinessLabel } from './controlPlane'

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value < 0) return '—'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let amount = value
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024
    unit += 1
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

function ProviderCard({ provider }: { provider: ProviderDefinition }) {
  const missing = missingCredentialNames(provider)
  return (
    <article className="provider-card">
      <div className="provider-card-head">
        <div>
          <div className="provider-label">{provider.label}</div>
          <div className="mono muted">{provider.id}</div>
        </div>
        <span className={`chip ${provider.configured ? 'pass' : 'fail'}`}>
          {providerReadinessLabel(provider)}
        </span>
      </div>
      <div className="provider-capabilities">
        {provider.capabilities.map((capability) => (
          <span className="chip kind" key={capability}>
            {capability}
          </span>
        ))}
        {provider.network_required ? <span className="chip kind">network</span> : null}
      </div>
      {provider.credential_env.length ? (
        <div className="provider-credentials">
          <span className="eyebrow">Credential environment</span>
          {provider.credential_env.map((credential) => (
            <div className="provider-credential mono" key={credential.name}>
              <span>{credential.name}</span>
              <span className={credential.present ? 'pos' : 'neg'}>
                {credential.present ? 'present' : 'missing'}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {missing.length ? (
        <div className="leak">Missing {missing.join(', ')}</div>
      ) : null}
      {Object.entries(provider.options).map(([name, option]) => (
        <div className="provider-option" key={name}>
          <span className="eyebrow">{option.label}</span>
          <span className="mono">
            {option.choices.join(' · ')} <span className="muted">default {option.default}</span>
          </span>
        </div>
      ))}
      {provider.limitations.length ? (
        <ul className="provider-limitations">
          {provider.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      ) : null}
    </article>
  )
}

export function ProviderSystem() {
  const [providers, setProviders] = useState<ProviderDefinition[] | null>(null)
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    void Promise.all([api.providers(), api.system()])
      .then(([providerCatalog, status]) => {
        setProviders(providerCatalog)
        setSystem(status)
      })
      .catch((reason: unknown) => setError(String(reason)))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Providers · System</span>
        {system ? (
          <span className={`chip ${system.paper_enabled ? 'pass' : 'fail'}`}>
            PAPER {system.paper_enabled ? 'ENABLED' : 'DISABLED'}
          </span>
        ) : null}
        <span className="muted">local readiness · no network probes</span>
        <div className="spacer" />
        <button className="btn" onClick={load}>
          refresh
        </button>
      </div>
      <div className="panel-body panel-pad control-plane">
        {error ? (
          <Placeholder big="control plane unavailable">{error}</Placeholder>
        ) : providers === null || system === null ? (
          <Placeholder>loading local readiness…</Placeholder>
        ) : (
          <>
            <section>
              <div className="rd-head">System readiness</div>
              <div className="metric-grid">
                <div className="metric">
                  <span className="eyebrow">Data directory</span>
                  <span className="metric-val mono">{system.data_dir.path}</span>
                  <span className={system.data_dir.readable && system.data_dir.writable ? 'pos' : 'neg'}>
                    {system.data_dir.readable ? 'readable' : 'not readable'} ·{' '}
                    {system.data_dir.writable ? 'writable' : 'not writable'}
                  </span>
                </div>
                <div className="metric">
                  <span className="eyebrow">Free space</span>
                  <span className="metric-val num">{formatBytes(system.data_dir.free_bytes)}</span>
                  <span className="muted">{system.data_dir.exists ? 'directory exists' : 'created on first write'}</span>
                </div>
                <div className="metric">
                  <span className="eyebrow">Data inventory</span>
                  <span className="metric-val num">{system.counts.symbols} symbols</span>
                  <span className="muted mono">{system.counts.snapshots} snapshots</span>
                </div>
                <div className="metric">
                  <span className="eyebrow">NautilusTrader</span>
                  <span className="metric-val mono">{system.nautilus.installed_version ?? 'not installed'}</span>
                  <span className={system.nautilus.matches_pin ? 'pos' : 'neg'}>
                    pinned {system.nautilus.pinned_version}
                  </span>
                </div>
                <div className="metric">
                  <span className="eyebrow">Kronos cache</span>
                  <span className="metric-val mono">
                    {system.kronos_cache.configured ? 'configured' : 'not configured'}
                  </span>
                  <span className="muted">
                    {system.kronos_cache.local_only ? 'local-only' : 'network loading allowed'} ·{' '}
                    {system.kronos_cache.exists ? 'present' : 'absent'}
                  </span>
                </div>
                <div className="metric">
                  <span className="eyebrow">ALPHA_PAPER_ENABLED</span>
                  <span className={`metric-val mono ${system.paper_enabled ? 'pos' : 'neg'}`}>
                    {String(system.paper_enabled)}
                  </span>
                  <span className="muted">explicit opt-in required</span>
                </div>
              </div>
            </section>
            <section>
              <div className="rd-head">Provider registry</div>
              {providers.length ? (
                <div className="provider-grid">
                  {providers.map((provider) => (
                    <ProviderCard key={provider.id} provider={provider} />
                  ))}
                </div>
              ) : (
                <Placeholder big="no providers">The CLI provider registry returned no entries.</Placeholder>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}
