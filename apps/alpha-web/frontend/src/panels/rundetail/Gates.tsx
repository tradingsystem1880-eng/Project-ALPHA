// Gates tab: every validation gate as an explained card with its inline visualization —
// percentile gauges for the null tiers, an interval bar for the CI, a fold strip for CPCV.

import { useMemo } from 'react'

import { IntervalBar } from '../../components/charts/IntervalBar'
import { PercentileGauge } from '../../components/charts/PercentileGauge'
import { gateStories } from '../../explain/gates'
import type { ValidateManifest } from '../../explain/types'
import { ExplainCard, Section } from './common'

export function Gates({ manifest }: { manifest: ValidateManifest }) {
  const stories = useMemo(() => gateStories(manifest), [manifest])
  const ci = manifest.cis?.find((c) => c.metric === 'sharpe')
  const t1 = manifest.nulls?.find((n) => n.tier === 'returns_level')
  const t2 = manifest.nulls?.find((n) => n.tier === 'full_engine')

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
                    <PercentileGauge percentile={t1.percentile} threshold={t1.threshold} />
                  </div>
                ) : null}
                {t2 ? (
                  <div className="gate-viz-row">
                    <span className="eyebrow">Tier 2 · full engine</span>
                    <PercentileGauge percentile={t2.percentile} threshold={t2.threshold} />
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
