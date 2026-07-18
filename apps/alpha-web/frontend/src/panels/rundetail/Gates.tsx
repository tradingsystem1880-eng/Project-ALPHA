// Gates tab: every validation gate as an explained card with its inline visualization —
// null histograms (when the run persisted its null paths) + percentile gauges for the tiers,
// an interval bar for the CI.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { NullTiers } from '../../api/types'
import { IntervalBar } from '../../components/charts/IntervalBar'
import { NullHistogram } from '../../components/charts/NullHistogram'
import { PercentileGauge } from '../../components/charts/PercentileGauge'
import { gateStories } from '../../explain/gates'
import type { ValidateManifest } from '../../explain/types'
import { ExplainCard, Section } from './common'

export function Gates({
  manifest,
  runId,
  hasNulls = false,
}: {
  manifest: ValidateManifest
  runId: string
  hasNulls?: boolean
}) {
  const stories = useMemo(() => gateStories(manifest), [manifest])
  const ci = manifest.cis?.find((c) => c.metric === 'sharpe')
  const t1 = manifest.nulls?.find((n) => n.tier === 'returns_level')
  const t2 = manifest.nulls?.find((n) => n.tier === 'full_engine')
  const [nullTiers, setNullTiers] = useState<NullTiers | null>(null)

  useEffect(() => {
    if (!hasNulls) return
    let live = true
    api.nulls(runId).then((n) => live && setNullTiers(n)).catch(() => {})
    return () => {
      live = false
    }
  }, [runId, hasNulls])

  const histFor = (tier: string) =>
    nullTiers?.tiers.find((t) => t.tier === tier)?.statistics ?? null

  return (
    <Section title="The gauntlet — five gates, all must pass">
      <div className="gate-cards">
        {stories.map((g) => (
          <div key={g.gate}>
            <ExplainCard story={g} title={g.title} passed={g.passed} stats={g.stats} tests={g.tests} />
            {g.gate === 'randomized_price_null' && (t1 || t2) ? (
              <div className="gate-viz">
                {t1 ? (
                  <div className="gate-viz-row">
                    <span className="eyebrow">Tier 1 · returns-level</span>
                    {histFor('returns_level') ? (
                      <NullHistogram
                        statistics={histFor('returns_level')!}
                        observed={t1.observed}
                        threshold={t1.threshold}
                      />
                    ) : (
                      <PercentileGauge percentile={t1.percentile} threshold={t1.threshold} />
                    )}
                  </div>
                ) : null}
                {t2 ? (
                  <div className="gate-viz-row">
                    <span className="eyebrow">Tier 2 · full engine</span>
                    {histFor('full_engine') ? (
                      <NullHistogram
                        statistics={histFor('full_engine')!}
                        observed={t2.observed}
                        threshold={t2.threshold}
                      />
                    ) : (
                      <PercentileGauge percentile={t2.percentile} threshold={t2.threshold} />
                    )}
                  </div>
                ) : null}
              </div>
            ) : null}
            {g.gate === 'bootstrap_ci' && ci ? (
              <div className="gate-viz">
                <div className="gate-viz-row">
                  <span className="eyebrow">Sharpe CI</span>
                  <IntervalBar lower={ci.lower} point={ci.point} upper={ci.upper} />
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </Section>
  )
}
