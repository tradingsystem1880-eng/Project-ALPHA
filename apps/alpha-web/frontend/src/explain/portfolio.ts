// Portfolio & cross-sectional run stories: does diversification carry the edge?

import { fmtNum } from '../util/format'
import type { Explained, PortfolioManifest, StatChip, Suggestion } from './types'

export interface PortfolioStory extends Explained {
  title: string
  stats: StatChip[]
}

export function portfolioStories(m: PortfolioManifest): PortfolioStory[] {
  const out: PortfolioStory[] = []
  const isXs = m.command === 'cross_sectional'
  const sharpe = m.metrics?.sharpe ?? null
  const ciLo = m.sharpe_ci?.lower ?? null
  const ciHi = m.sharpe_ci?.upper ?? null
  const legs = m.legs ?? []
  const nSyms = m.symbols?.length ?? legs.length

  const headline: PortfolioStory = {
    title: isXs ? 'Cross-sectional book' : 'Diversified basket',
    stats: [
      { label: 'Sharpe', value: fmtNum(sharpe), term: 'sharpe' },
      { label: 'CI', value: `[${fmtNum(ciLo)}, ${fmtNum(ciHi)}]`, term: 'bca_ci' },
      { label: 'PSR', value: fmtNum(m.psr, 3), term: 'psr' },
      { label: isXs ? 'Names/leg' : 'Legs', value: String(isXs ? (m.n_long ?? '—') : nSyms) },
    ],
    terse: `${isXs ? 'XS book' : `${nSyms}-leg basket`}: Sharpe ${fmtNum(sharpe)} ∈ [${fmtNum(ciLo)}, ${fmtNum(ciHi)}], PSR ${fmtNum(m.psr, 3)}`,
    narrative: isXs
      ? `A relative-strength book over ${nSyms} names: rank the universe, hold the top ` +
        `${m.n_long ?? '—'}${m.long_short ? ' long and bottom short (dollar-neutral)' : ' long-only'}, ` +
        `vol-target the book, and pay fees+slippage on every rebalance's turnover. Sharpe ` +
        `${fmtNum(sharpe)} with the CI ${ciLo !== null && ciLo > 0 ? 'clear of' : 'straddling'} zero. ` +
        `Because the book is cross-sectional, single-name luck matters less — but regime risk ` +
        `(everything correlating in a selloff) matters more.`
      : `${nSyms} per-symbol OOS streams combined under ${m.weighting ?? 'equal'} weights ` +
        `(computed causally — trailing vol only). Portfolio Sharpe ${fmtNum(sharpe)} vs the best ` +
        `single legs below: diversification pays exactly when the combined Sharpe beats the ` +
        `legs it averages. CI [${fmtNum(ciLo)}, ${fmtNum(ciHi)}]` +
        (ciLo !== null && ciLo > 0 ? ' — even the lower bound is positive.' : ' — still straddles zero.'),
    tone: ciLo !== null && ciLo > 0 ? 'good' : sharpe !== null && sharpe > 0 ? 'warn' : 'bad',
  }
  out.push(headline)

  if (legs.length) {
    const bestLeg = legs.reduce((a, b) =>
      (b.oos_sharpe ?? -Infinity) > (a.oos_sharpe ?? -Infinity) ? b : a,
    )
    const beat = typeof sharpe === 'number' && typeof bestLeg.oos_sharpe === 'number' && sharpe > bestLeg.oos_sharpe
    out.push({
      title: 'Diversification check',
      stats: legs.slice(0, 6).map((l) => ({ label: l.symbol, value: fmtNum(l.oos_sharpe) })),
      terse: `portfolio ${fmtNum(sharpe)} vs best leg ${bestLeg.symbol} ${fmtNum(bestLeg.oos_sharpe)} ${beat ? '✓' : '✗'}`,
      narrative: beat
        ? `The portfolio Sharpe ${fmtNum(sharpe)} beats every individual leg (best: ` +
          `${bestLeg.symbol} at ${fmtNum(bestLeg.oos_sharpe)}). That is the free lunch working — ` +
          `imperfectly correlated streams cancelling noise.`
        : `The best single leg (${bestLeg.symbol}, ${fmtNum(bestLeg.oos_sharpe)}) still beats the ` +
          `portfolio (${fmtNum(sharpe)}). The legs are either too correlated or too unequal in ` +
          `edge for the averaging to pay; weights or universe need work.`,
      tone: beat ? 'good' : 'warn',
    })
  }
  return out
}

export function portfolioSuggestions(m: PortfolioManifest): Suggestion[] {
  const out: Suggestion[] = []
  const weakest = (m.legs ?? []).filter((l) => typeof l.oos_sharpe === 'number' && l.oos_sharpe < 0)
  if (weakest.length) {
    out.push({
      title: `${weakest.length} leg(s) drag with negative OOS Sharpe`,
      why:
        `${weakest.map((l) => l.symbol).join(', ')} contribute negative risk-adjusted return. ` +
        `Before dropping them, check correlation — a negative-Sharpe leg can still help if it ` +
        `hedges the rest; if it correlates positively AND loses, it is pure drag.`,
    })
  }
  if ((m.sharpe_ci?.lower ?? null) !== null && (m.sharpe_ci?.lower as number) <= 0) {
    out.push({
      title: 'Portfolio CI still straddles zero — widen the universe',
      why:
        `More uncorrelated legs is the highest-probability fix: each genuinely diversifying ` +
        `symbol raises the combined Sharpe roughly with √N while the CI tightens with sample.`,
    })
  }
  return out
}
