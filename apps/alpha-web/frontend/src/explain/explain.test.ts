// The explanation engine's guardrails.
//
// The drift-guard suite is the load-bearing part: it recomputes every fixture's verdict from raw
// gate quantities using the TS band mirror and asserts equality with the grades the Python side
// persisted. If verdict.py's bands ever change without bands.ts following (or vice versa), this
// fails — the UI must never explain a grade with stale rules.

import { describe, expect, it } from 'vitest'

import {
  DRAWDOWN_BANDS,
  EDGE_BANDS,
  RUIN_BANDS,
  SAMPLE_BANDS,
  bandInterval,
  gradeAtLeast,
  gradeAtMost,
  recomputeVerdict,
} from './bands'
import { forecastStories } from './forecast'
import { gateStories, nullStory, walkForwardStory } from './gates'
import { optimStories, optimSuggestions } from './optim'
import { portfolioStories } from './portfolio'
import { propfirmStories } from './propfirm'
import { suggestions } from './suggestions'
import type { OptimManifest, PortfolioManifest, PropfirmManifest, ValidateManifest } from './types'
import { verdictStories } from './verdictStory'
import optimFixture from './__fixtures__/optim.json'
import portfolioFixture from './__fixtures__/portfolio.json'
import propfirmFixture from './__fixtures__/propfirm.json'
import validateA from './__fixtures__/validate-a.json'
import validateB from './__fixtures__/validate-b.json'
import validateD from './__fixtures__/validate-d-kronos.json'

const VALIDATE_FIXTURES: [string, ValidateManifest][] = [
  ['validate-a', validateA as unknown as ValidateManifest],
  ['validate-b', validateB as unknown as ValidateManifest],
  ['validate-d-kronos', validateD as unknown as ValidateManifest],
]

describe('drift guard: TS bands vs persisted Python verdicts', () => {
  it.each(VALIDATE_FIXTURES)('%s: recomputed grades equal persisted grades', (_name, m) => {
    const v = m.verdict
    expect(v).toBeDefined()
    if (!v) return
    const sharpeCi = m.cis?.find((c) => c.metric === 'sharpe')
    const recomputed = recomputeVerdict({
      oosSharpe: m.oos_metrics?.sharpe ?? null,
      nullTiersPassed: (m.nulls?.length ?? 0) > 0 && (m.nulls ?? []).every((n) => n.passed),
      dsrPassed: m.dsr?.passed ?? false,
      cpcvPassed: m.cpcv?.passed ?? false,
      ciLowerPositive: typeof sharpeCi?.lower === 'number' && sharpeCi.lower > 0,
      maxDrawdown: m.oos_metrics?.max_drawdown ?? null,
      riskOfRuin: m.oos_metrics?.risk_of_ruin ?? null,
      nOos: v.detail.sample_n_oos ?? NaN,
    })
    expect(recomputed.edge).toBe(v.edge)
    expect(recomputed.robustness).toBe(v.robustness)
    expect(recomputed.risk).toBe(v.risk)
    expect(recomputed.sample).toBe(v.sample)
    expect(recomputed.overall).toBe(v.overall)
    expect(recomputed.gpa).toBeCloseTo(v.detail.overall_gpa ?? NaN, 10)
    expect(recomputed.checks).toBe(v.detail.robustness_checks_passed ?? NaN)
  })
})

describe('band boundaries (mirror verdict.py exactly)', () => {
  it('edge bands are inclusive lower bounds', () => {
    expect(gradeAtLeast(1.5, EDGE_BANDS)).toBe('A')
    expect(gradeAtLeast(1.4999, EDGE_BANDS)).toBe('B')
    expect(gradeAtLeast(1.0, EDGE_BANDS)).toBe('B')
    expect(gradeAtLeast(0.5, EDGE_BANDS)).toBe('C')
    expect(gradeAtLeast(0.0, EDGE_BANDS)).toBe('D')
    expect(gradeAtLeast(-0.0001, EDGE_BANDS)).toBe('F')
  })
  it('sample bands', () => {
    expect(gradeAtLeast(1000, SAMPLE_BANDS)).toBe('A')
    expect(gradeAtLeast(999, SAMPLE_BANDS)).toBe('B')
    expect(gradeAtLeast(100, SAMPLE_BANDS)).toBe('D')
    expect(gradeAtLeast(99, SAMPLE_BANDS)).toBe('F')
  })
  it('risk bands are inclusive upper bounds', () => {
    expect(gradeAtMost(0.1, DRAWDOWN_BANDS)).toBe('A')
    expect(gradeAtMost(0.10001, DRAWDOWN_BANDS)).toBe('B')
    expect(gradeAtMost(0.5, DRAWDOWN_BANDS)).toBe('D')
    expect(gradeAtMost(0.51, DRAWDOWN_BANDS)).toBe('F')
    expect(gradeAtMost(0.01, RUIN_BANDS)).toBe('A')
    expect(gradeAtMost(0.3, RUIN_BANDS)).toBe('D')
    expect(gradeAtMost(0.31, RUIN_BANDS)).toBe('F')
  })
  it('null/NaN grade F', () => {
    expect(gradeAtLeast(null, EDGE_BANDS)).toBe('F')
    expect(gradeAtLeast(NaN, EDGE_BANDS)).toBe('F')
    expect(gradeAtMost(null, RUIN_BANDS)).toBe('F')
  })
  it('band intervals render for narratives', () => {
    expect(bandInterval('B', EDGE_BANDS, 'atLeast')).toBe('[1, 1.5)')
    expect(bandInterval('A', EDGE_BANDS, 'atLeast')).toBe('≥ 1.5')
    expect(bandInterval('F', EDGE_BANDS, 'atLeast')).toBe('below 0')
    expect(bandInterval('A', DRAWDOWN_BANDS, 'atMost')).toBe('≤ 0.1')
    expect(bandInterval('B', DRAWDOWN_BANDS, 'atMost')).toBe('(0.1, 0.2]')
  })
})

describe('gate stories', () => {
  const m = validateB as unknown as ValidateManifest

  it('produces all five gates in canonical order', () => {
    expect(gateStories(m).map((g) => g.gate)).toEqual([
      'walk_forward_oos',
      'randomized_price_null',
      'bootstrap_ci',
      'deflated_sharpe',
      'cpcv_oos',
    ])
  })

  it('every story carries both voices and teaching text', () => {
    for (const g of gateStories(m)) {
      expect(g.narrative.length).toBeGreaterThan(80)
      expect(g.terse.length).toBeGreaterThan(5)
      expect(g.tests.length).toBeGreaterThan(40)
    }
  })

  it('walk-forward counts folds and flat windows', () => {
    const g = walkForwardStory(m)
    expect(g.passed).toBe(true)
    expect(g.terse).toContain('31 folds')
    // fold 24 is flat (null sharpe) → 30 graded
    expect(g.terse).toContain('/30')
  })

  it('failed null gate reads as the luck flag', () => {
    const g = nullStory(m)
    expect(g.passed).toBe(false)
    expect(g.tone).toBe('bad')
    expect(g.narrative).toContain('indistinguishable from luck')
  })
})

describe('verdict stories', () => {
  it('explains each dimension against its band (fixture B: C/C/B/A → B overall)', () => {
    const stories = verdictStories(validateB as unknown as ValidateManifest)
    const byDim = Object.fromEntries(stories.map((s) => [s.dimension, s]))
    expect(byDim.edge.grade).toBe('C')
    expect(byDim.edge.narrative).toContain('[0.5, 1)')
    expect(byDim.robustness.grade).toBe('C')
    expect(byDim.robustness.narrative).toContain('2 of the 4')
    expect(byDim.risk.grade).toBe('B')
    expect(byDim.sample.grade).toBe('A')
    expect(byDim.overall.grade).toBe('B')
    // hard gates failed → overall story must say so, loudly
    expect(byDim.overall.tone).toBe('bad')
    expect(byDim.overall.narrative).toContain('FAILED')
  })
})

describe('suggestions', () => {
  it('failed-null run leads with the luck suggestion', () => {
    const s = suggestions(validateB as unknown as ValidateManifest)
    expect(s.length).toBeGreaterThan(0)
    expect(s[0].title).toContain('luck')
  })
  it('CI straddling zero yields the statistical-power suggestion', () => {
    const s = suggestions(validateB as unknown as ValidateManifest)
    expect(s.some((x) => x.title.includes('straddles zero'))).toBe(true)
  })
})

describe('kind modules', () => {
  it('optim: all three control stories, passing sweep suggests validate', () => {
    const m = optimFixture as unknown as OptimManifest
    const stories = optimStories(m)
    expect(stories.map((s) => s.title)).toEqual([
      'Deflated Sharpe (best of the sweep)',
      'Probability of backtest overfitting',
      'Data-snooping tests (Reality Check / SPA)',
    ])
    const sugg = optimSuggestions(m)
    expect(sugg[0].action?.command).toBe('validate')
  })

  it('propfirm: odds + EV stories with money formatting', () => {
    const stories = propfirmStories(propfirmFixture as unknown as PropfirmManifest)
    expect(stories).toHaveLength(2)
    expect(stories[0].terse).toMatch(/pass \d+%/)
    expect(stories[1].stats[0].value).toMatch(/^[$—-]/)
  })

  it('portfolio: headline + diversification check', () => {
    const stories = portfolioStories(portfolioFixture as unknown as PortfolioManifest)
    expect(stories.length).toBeGreaterThanOrEqual(2)
    expect(stories[1].title).toBe('Diversification check')
  })

  it('forecast: eval summaries split honest vs overlapping', () => {
    const stories = forecastStories({
      command: 'forecast_eval',
      summary_post_cutoff: { n_origins: 10, skill_vs_rw: -0.05, skill_vs_bootstrap: -0.1, coverage80: 0.9, hit_rate: 0.4 },
      summary_pre_cutoff: { n_origins: 20, skill_vs_rw: 0.2, skill_vs_bootstrap: 0.1, coverage80: 0.8, hit_rate: 0.6 },
    })
    const post = stories.find((s) => s.title.includes('Post-cutoff'))
    expect(post?.tone).toBe('bad')
    const pre = stories.find((s) => s.title.includes('Pre-cutoff'))
    expect(pre?.tone).toBe('warn')
  })
})
