// Prop-firm layout: the outcome funnel (pass → funded → payout vs bust) + rules + EV story.

import { useMemo } from 'react'

import { api } from '../../api/client'
import { OutcomeBars } from '../../components/charts/OutcomeBars'
import { propfirmStories, propfirmSuggestions } from '../../explain/propfirm'
import type { PropfirmManifest } from '../../explain/types'
import { CHART } from '../../util/chartTheme'
import { fmtPct } from '../../util/format'
import { ExplainCard, Section, SuggestionList } from './common'
import { useProjection } from './commonUtils'

/** The three headline probabilities as horizontal magnitude bars (one hue, labeled ends). */
function ProbBars({ m }: { m: PropfirmManifest }) {
  const rows = [
    { label: 'clears evaluation', v: m.metrics?.pass_probability ?? null, color: CHART.accent },
    { label: 'reaches a payout', v: m.metrics?.payout_probability ?? null, color: CHART.up },
    { label: 'busts (eval or funded)', v: m.metrics?.bust_probability ?? null, color: CHART.down },
  ].filter((r) => typeof r.v === 'number')
  if (!rows.length) return null
  const width = 420
  const barH = 22
  const gap = 10
  const labelW = 150
  return (
    <svg width={width} height={rows.length * (barH + gap)} role="img" aria-label="outcome probabilities">
      {rows.map((r, i) => {
        const y = i * (barH + gap)
        const w = Math.max(2, (r.v as number) * (width - labelW - 60))
        return (
          <g key={r.label}>
            <text x={labelW - 8} y={y + barH / 2 + 4} textAnchor="end" className="svg-num">
              {r.label}
            </text>
            <rect x={labelW} y={y + 2} width={width - labelW - 60} height={barH - 4} rx={3} fill={CHART.grid} />
            <rect x={labelW} y={y + 2} width={w} height={barH - 4} rx={3} fill={r.color} opacity={0.75} />
            <text x={labelW + w + 8} y={y + barH / 2 + 4} className="svg-num" fill={CHART.ink}>
              {fmtPct(r.v, 1)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export function PropfirmDetail({
  manifest,
  runId,
  hasPaths = false,
  onLaunch,
}: {
  manifest: PropfirmManifest
  runId: string
  hasPaths?: boolean
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => propfirmStories(manifest), [manifest])
  const sugg = useMemo(() => propfirmSuggestions(manifest), [manifest])
  const rules = manifest.rules ?? {}
  const paths = useProjection(hasPaths, runId, () => api.propfirmPaths(runId))

  return (
    <>
      <Section title={`Monte-Carlo outcomes · ${(manifest.n_paths ?? 0).toLocaleString()} paths`}>
        <ProbBars m={manifest} />
        {paths ? <OutcomeBars data={paths} /> : null}
      </Section>
      <Section title="The story">
        <div className="gate-cards">
          {stories.map((s) => (
            <ExplainCard key={s.title} story={s} title={s.title} stats={s.stats} />
          ))}
        </div>
      </Section>
      <Section title={`Ruleset · ${manifest.firm ?? 'custom'} (illustrative, not firm terms)`}>
        <div className="meta-grid">
          {Object.entries(rules).map(([k, v]) => (
            <div className="meta-item" key={k}>
              <span className="eyebrow">{k.replace(/_/g, ' ')}</span>
              <span className="mono">{typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v ?? '—')}</span>
            </div>
          ))}
        </div>
      </Section>
      {sugg.length ? (
        <Section title="Next steps">
          <SuggestionList items={sugg} onLaunch={onLaunch} />
        </Section>
      ) : null}
    </>
  )
}
