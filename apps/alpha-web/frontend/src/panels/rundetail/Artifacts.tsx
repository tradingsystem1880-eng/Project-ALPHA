// Artifacts tab: full reproducibility — every knob that produced this run, the exact re-run
// command, and the embedded quantstats tear sheet.

import { api } from '../../api/client'
import type { ValidateManifest } from '../../explain/types'
import { Section } from './common'
import { asStr } from './commonUtils'

function reproCommand(m: ValidateManifest, kind: string, runId: string): string {
  const md = m.metadata ?? {}
  const symbol = asStr(md.symbol)
  const strategy = asStr(md.strategy_name)
  if (kind === 'runs' && symbol) {
    const params = Array.isArray(md.strategy_params)
      ? (md.strategy_params as [string, unknown][]).map(([k, v]) => `--param ${k}=${v}`).join(' ')
      : ''
    return `alpha validate ${symbol}${strategy ? ` --strategy ${strategy}` : ''}${params ? ` ${params}` : ''} --seed ${String(md.seed ?? 7)}`
  }
  return `alpha report ${runId}`
}

export function Artifacts({
  manifest,
  kind,
  runId,
  hasTearsheet,
}: {
  manifest: ValidateManifest
  kind: string
  runId: string
  hasTearsheet: boolean
}) {
  const md = manifest.metadata ?? {}
  const entries = Object.entries(md).filter(([, v]) => v !== null && typeof v !== 'object')

  return (
    <>
      <Section title="Reproduce">
        <div className="repro mono">{reproCommand(manifest, kind, runId)}</div>
        <p className="muted">
          Every stochastic gate derives its seed from the master seed via SeedSequence spawning —
          the same command reproduces this manifest byte-for-byte.
        </p>
      </Section>
      {entries.length ? (
        <Section title="Run metadata">
          <div className="meta-grid">
            {entries.map(([k, v]) => (
              <div className="meta-item" key={k}>
                <span className="eyebrow">{k}</span>
                <span className="mono">{String(v)}</span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}
      {hasTearsheet ? (
        <Section title="Tear sheet" right={<span className="muted">external quantstats report</span>}>
          <iframe className="tearsheet" src={api.tearsheetUrl(runId)} title="Tear sheet" />
        </Section>
      ) : null}
    </>
  )
}
