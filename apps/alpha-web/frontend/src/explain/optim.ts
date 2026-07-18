// Optimization-run stories: is the sweep's best config a real edge or selection luck?

import { fmtNum, fmtPct } from '../util/format'
import type { Explained, OptimManifest, StatChip, Suggestion } from './types'

export interface OptimStory extends Explained {
  title: string
  passed: boolean | null
  stats: StatChip[]
}

export function optimStories(m: OptimManifest): OptimStory[] {
  const out: OptimStory[] = []
  const n = m.n_configs ?? m.configs?.length ?? 0
  const sharpes = (m.sharpes ?? []).filter((s): s is number => typeof s === 'number')
  const best = m.best_sharpe ?? null
  const median = sharpes.length
    ? [...sharpes].sort((a, b) => a - b)[Math.floor(sharpes.length / 2)]
    : null

  if (m.dsr) {
    const d = m.dsr
    out.push({
      title: 'Deflated Sharpe (best of the sweep)',
      passed: d.passed ?? null,
      stats: [
        { label: 'Best Sharpe', value: fmtNum(best), term: 'sharpe' },
        { label: 'E[max SR] by luck', value: fmtNum(d.expected_max_sharpe), term: 'expected_max_sharpe' },
        { label: 'DSR', value: fmtNum(d.dsr, 3), term: 'dsr' },
        { label: 'Trials', value: String(d.n_trials ?? n) },
      ],
      terse: `best ${fmtNum(best)} vs luck-of-${d.n_trials ?? n} ${fmtNum(d.expected_max_sharpe)} → DSR ${fmtNum(d.dsr, 3)} ${d.passed ? '✓' : '✗'}`,
      narrative:
        `Trying ${n} configurations guarantees the best one looks good — the best of ${n} random ` +
        `strategies would already show a Sharpe of ~${fmtNum(d.expected_max_sharpe)}. Deflating ` +
        `the winner (${fmtNum(best)}) for that selection pressure leaves DSR ${fmtNum(d.dsr, 3)}` +
        `${d.passed ? ' — the winner clears the luck-of-the-sweep bar.' : ' — the winner does NOT clear the bar; it is what the best of noise looks like.'}`,
      tone: d.passed ? 'good' : 'bad',
    })
  }

  if (m.pbo) {
    const p = m.pbo
    out.push({
      title: 'Probability of backtest overfitting',
      passed: p.passed ?? null,
      stats: [
        { label: 'PBO', value: fmtPct(p.pbo, 1), term: 'pbo' },
        { label: 'CSCV splits', value: String(p.n_splits ?? '—') },
        { label: 'Median trial SR', value: fmtNum(median) },
      ],
      terse: `PBO ${fmtPct(p.pbo, 1)} over ${p.n_splits ?? '—'} splits ${p.passed ? '✓' : '✗'}`,
      narrative:
        `Across ${p.n_splits ?? 'many'} in-sample/out-of-sample re-splits of the trial matrix, the ` +
        `in-sample winner fell below the OOS median ${fmtPct(p.pbo, 1)} of the time. ` +
        (p.passed
          ? `Picking the backtest winner genuinely transfers out of sample here.`
          : `That is coin-flip territory: the sweep is choosing noise, not signal. Shrink the ` +
            `grid to fewer, more distinct configurations.`),
      tone: p.passed ? 'good' : 'bad',
    })
  }

  if (m.reality_check || m.spa) {
    const rc = m.reality_check
    const spa = m.spa
    out.push({
      title: 'Data-snooping tests (Reality Check / SPA)',
      passed: spa?.passed ?? rc?.passed ?? null,
      stats: [
        { label: 'RC p', value: fmtNum(rc?.p_value, 4), term: 'reality_check' },
        { label: 'SPA p', value: fmtNum(spa?.p_value, 4), term: 'spa' },
      ],
      terse: `RC p=${fmtNum(rc?.p_value, 3)} · SPA p=${fmtNum(spa?.p_value, 3)} ${spa?.passed ? '✓' : '✗'}`,
      narrative:
        `Bootstrap the whole family of ${n} configs under the no-edge null: the chance the BEST ` +
        `performs this well by snooping alone is p=${fmtNum(rc?.p_value, 4)} (White) / ` +
        `p=${fmtNum(spa?.p_value, 4)} (Hansen SPA, robust to junk configs in the family). ` +
        (spa?.passed ?? rc?.passed
          ? `The family contains something better than noise.`
          : `The family as a whole is not distinguishable from noise.`),
      tone: (spa?.passed ?? rc?.passed) ? 'good' : 'bad',
    })
  }

  return out
}

// RunSpec's first-class CLI flags; every other swept name rides through --param.
const CLI_FLAGS = new Set(['lookback', 'skip', 'vol_window', 'rebalance_every', 'target_vol', 'max_leverage'])

export function optimSuggestions(m: OptimManifest): Suggestion[] {
  const out: Suggestion[] = []
  const symbol = m.symbol ?? ''
  const flags = (m.best_config ?? [])
    .map(([k, v]) => (CLI_FLAGS.has(k) ? `--${k.replaceAll('_', '-')} ${v}` : `--param ${k}=${v}`))
    .join(' ')

  if (m.passed) {
    out.push({
      title: 'Sweep verdict clean — validate the winner as a single run',
      why:
        `DSR, PBO, and SPA all pass, so the best config earned its rank. The full gauntlet on ` +
        `that config (fresh seed, single-trial) is the natural next step before sizing it.`,
      action: symbol ? { command: 'validate', args: `${symbol} ${flags}`.trim() } : undefined,
    })
  } else {
    if (m.pbo && m.pbo.passed === false) {
      out.push({
        title: 'High PBO — shrink and coarsen the grid',
        why:
          `With PBO at ${fmtPct(m.pbo.pbo, 0)}, the sweep mostly ranks noise. Fewer axes, wider ` +
          `spacing, and economically-motivated values beat dense grids: you want a plateau of ` +
          `good configs, not a single spike.`,
      })
    }
    if (m.dsr && m.dsr.passed === false) {
      out.push({
        title: 'Best config fails deflation — the family may be too large for the edge',
        why:
          `The winner's Sharpe does not clear what the best of ${m.dsr.n_trials ?? m.n_configs} ` +
          `random trials would show. Either the underlying edge is too small, or the same search ` +
          `on a longer sample would separate skill from luck.`,
      })
    }
  }
  return out
}
