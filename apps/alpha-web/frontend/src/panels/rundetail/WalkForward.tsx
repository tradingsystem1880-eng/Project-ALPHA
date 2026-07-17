// Walk-forward tab: the fold strip (consistency at a glance) + the per-fold table.

import { useMemo } from 'react'

import { FoldStrip } from '../../components/charts/FoldStrip'
import { walkForwardStory } from '../../explain/gates'
import type { ValidateManifest } from '../../explain/types'
import { fmtNum, fmtPct } from '../../util/format'
import { ExplainCard, Section } from './common'

export function WalkForward({ manifest }: { manifest: ValidateManifest }) {
  const folds = manifest.folds ?? []
  const story = useMemo(() => walkForwardStory(manifest), [manifest])
  if (!folds.length) return <Section title="Walk-forward">no folds recorded</Section>

  return (
    <>
      <Section title="Per-fold OOS Sharpe">
        <div className="fold-strip-wrap">
          <FoldStrip values={folds.map((f) => f.oos_sharpe)} title={(i) => `fold ${folds[i]?.index ?? i}`} />
        </div>
        <ExplainCard story={story} title={story.title} passed={story.passed} stats={story.stats} tests={story.tests} />
      </Section>
      <Section title="Folds">
        <table className="blotter">
          <thead>
            <tr>
              <th>#</th>
              <th className="r">Train window</th>
              <th className="r">Test window</th>
              <th className="r">N</th>
              <th className="r">OOS return</th>
              <th className="r">OOS Sharpe</th>
              <th className="r">OOS CAGR</th>
            </tr>
          </thead>
          <tbody>
            {folds.map((f, i) => (
              <tr key={i}>
                <td className="num">{f.index ?? i}</td>
                <td className="num">{f.train_start}–{f.train_end}</td>
                <td className="num">{f.test_start}–{f.test_end}</td>
                <td className="num">{f.n_test}</td>
                <td className={`num${(f.oos_return ?? 0) < 0 ? ' neg' : ''}`}>{fmtPct(f.oos_return, 2)}</td>
                <td className={`num${(f.oos_sharpe ?? 0) < 0 ? ' neg' : ''}`}>{fmtNum(f.oos_sharpe, 2)}</td>
                <td className="num">{fmtPct(f.oos_cagr, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </>
  )
}
