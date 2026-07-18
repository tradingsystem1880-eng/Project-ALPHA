// Gate stories: turn each validation gate's numbers into an explanation in both voices.
// Pure functions over the manifest — no fetches, no DOM — so the whole module unit-tests in node.

import { fmtNum, fmtPct, isFiniteNum as finite } from '../util/format'
import type {
  CIRow,
  CPCVBlock,
  DSRBlock,
  FoldRow,
  GateStory,
  NullTierRow,
  Tone,
  ValidateManifest,
} from './types'

function tone(passed: boolean | null, warn = false): Tone {
  if (passed === null) return 'info'
  if (passed) return warn ? 'warn' : 'good'
  return 'bad'
}

// ---- gate: walk_forward_oos ----------------------------------------------------------------

export function walkForwardStory(m: ValidateManifest): GateStory {
  const folds: FoldRow[] = m.folds ?? []
  const sharpe = m.oos_metrics?.sharpe ?? null
  const passed = m.outcomes?.find((o) => o.name === 'walk_forward_oos')?.passed ?? null
  const nOos = folds.reduce((acc, f) => acc + (f.n_test || 0), 0)
  const positive = folds.filter((f) => finite(f.oos_sharpe) && f.oos_sharpe > 0).length
  const graded = folds.filter((f) => finite(f.oos_sharpe)).length
  const years = nOos > 0 ? nOos / 252 : 0

  const narrative =
    `The strategy traded ${folds.length} out-of-sample windows in sequence — a total of ` +
    `${nOos.toLocaleString()} sessions (~${fmtNum(years, 1)} years) it never saw during warmup. ` +
    `Stitched together they earn an annualized Sharpe of ${fmtNum(sharpe)}. ` +
    `${positive} of ${graded} windows were profitable on a risk-adjusted basis` +
    (graded < folds.length ? ` (${folds.length - graded} flat windows carry no Sharpe)` : '') +
    `. Consistency across windows matters more than the average: an edge that only lived in one ` +
    `regime shows up here as a few great folds drowning many flat ones.`

  return {
    gate: 'walk_forward_oos',
    title: 'Walk-forward out-of-sample',
    passed,
    tests:
      'Is there any out-of-sample performance to talk about? The series is split into rolling ' +
      'train/test windows (train = warmup only — nothing refits); the concatenated test windows ' +
      'form the single OOS stream every other gate judges.',
    stats: [
      { label: 'OOS Sharpe', value: fmtNum(sharpe), term: 'sharpe' },
      { label: 'Folds', value: String(folds.length), term: 'walk_forward' },
      { label: 'Profitable folds', value: `${positive}/${graded}` },
      { label: 'OOS sessions', value: nOos.toLocaleString() },
    ],
    terse: `OOS Sharpe ${fmtNum(sharpe)} over ${folds.length} folds (${positive}/${graded} positive), n=${nOos}.`,
    narrative,
    tone: tone(passed),
  }
}

// ---- gate: randomized_price_null -----------------------------------------------------------

export function nullStory(m: ValidateManifest): GateStory {
  const tiers: NullTierRow[] = m.nulls ?? []
  const t1 = tiers.find((t) => t.tier === 'returns_level') ?? null
  const t2 = tiers.find((t) => t.tier === 'full_engine') ?? null
  const passed = m.outcomes?.find((o) => o.name === 'randomized_price_null')?.passed ?? null
  const flagged = t1?.flagged_low_fidelity ?? false

  const tierLine = (t: NullTierRow | null, label: string): string =>
    t
      ? `${label}: the observed Sharpe ${fmtNum(t.observed)} lands at the ` +
        `${fmtPct(t.percentile, 1)} percentile of ${t.n_paths.toLocaleString()} no-edge paths ` +
        `(p = ${fmtNum(t.p_value, 3)}) — ${t.passed ? 'clears' : 'fails'} the ${fmtPct(t.threshold, 0)} bar. `
      : ''

  let narrative =
    `The luck test. Both tiers ask the same question — would random, edge-free prices have paid ` +
    `this well? — at different fidelity. ` +
    tierLine(t1, 'Tier 1 (fast surrogate, resampled returns)') +
    tierLine(t2, 'Tier 2 (real engine, synthetic OHLCV)')
  if (flagged) {
    narrative +=
      `Tier 1 failed but was demoted to advisory: its close-fill convention diverges from the ` +
      `engine's t+1-open fills by ${fmtNum(t1?.convention_divergence)} Sharpe (tolerance ` +
      `exceeded) while Tier 2 — the honest simulation — passed. Read this as a surrogate ` +
      `fidelity problem, not evidence of luck.`
  } else if (passed === false) {
    narrative +=
      `A fail here is the single most important red flag this platform produces: whatever the ` +
      `equity curve looks like, paths with NO edge performed comparably, so the result is ` +
      `indistinguishable from luck on this symbol and period.`
  } else if (passed) {
    narrative += `Random prices could not match this performance — the edge survives its luck test.`
  }

  const stats: GateStory['stats'] = []
  if (t1) {
    stats.push(
      { label: 'T1 percentile', value: fmtPct(t1.percentile, 1), term: 'null_test' },
      { label: 'T1 p-value', value: fmtNum(t1.p_value, 3), term: 'p_value' },
      { label: 'Divergence', value: fmtNum(t1.convention_divergence, 3), term: 'convention_divergence' },
    )
  }
  if (t2) {
    stats.push(
      { label: 'T2 percentile', value: fmtPct(t2.percentile, 1), term: 'null_test' },
      { label: 'T2 p-value', value: fmtNum(t2.p_value, 3), term: 'p_value' },
      { label: 'T2 paths', value: String(t2.n_paths) },
    )
  }

  const t = flagged && passed ? tone(true, true) : tone(passed)
  return {
    gate: 'randomized_price_null',
    title: 'Randomized-price null (the luck test)',
    passed,
    tests:
      'Could pure luck explain the performance? The strategy must beat the 95th percentile of ' +
      'synthetic no-edge price paths in BOTH tiers: a fast returns-level surrogate (1,000 paths) ' +
      'and the real engine on synthetic OHLCV (64 paths). A Tier-2 fail is never excused.',
    stats,
    terse:
      `T1 ${t1 ? `${fmtPct(t1.percentile, 0)} pct${t1.passed ? '✓' : '✗'}` : '—'} · ` +
      `T2 ${t2 ? `${fmtPct(t2.percentile, 0)} pct${t2.passed ? '✓' : '✗'}` : '—'}` +
      (flagged ? ' · T1 demoted (low fidelity)' : ''),
    narrative,
    tone: t,
  }
}

// ---- gate: bootstrap_ci --------------------------------------------------------------------

export function ciStory(m: ValidateManifest): GateStory {
  const ci: CIRow | null = m.cis?.find((c) => c.metric === 'sharpe') ?? null
  const passed = m.outcomes?.find((o) => o.name === 'bootstrap_ci')?.passed ?? null
  const straddles = ci !== null && finite(ci.lower) && finite(ci.upper) && ci.lower < 0 && ci.upper > 0

  const narrative = ci
    ? `Resampling the OOS returns 2,000 times (block bootstrap, BCa-corrected) puts the Sharpe's ` +
      `${fmtPct(ci.confidence, 0)} confidence interval at [${fmtNum(ci.lower)}, ${fmtNum(ci.upper)}] ` +
      `around a point estimate of ${fmtNum(ci.point)}. ` +
      (passed
        ? `Even the pessimistic lower bound is positive — the edge is not an artifact of one lucky stretch.`
        : straddles
          ? `The interval straddles zero: the data cannot rule out that the true Sharpe is negative. ` +
            `This usually means the sample is too short for the edge's size — more history shrinks ` +
            `the interval; a genuinely stronger edge moves it off zero.`
          : `The lower bound sits at or below zero, so a zero-or-worse true Sharpe remains plausible.`)
    : 'No confidence interval was computed for this run.'

  return {
    gate: 'bootstrap_ci',
    title: 'Bootstrap confidence interval',
    passed,
    tests:
      'How sure are we of the Sharpe itself? A stationary block bootstrap resamples the OOS ' +
      'stream and the gate demands the BCa interval\'s lower bound stay above zero.',
    stats: ci
      ? [
          { label: 'Sharpe', value: fmtNum(ci.point), term: 'sharpe' },
          { label: 'Lower', value: fmtNum(ci.lower), term: 'bca_ci' },
          { label: 'Upper', value: fmtNum(ci.upper), term: 'bca_ci' },
          { label: 'Confidence', value: fmtPct(ci.confidence, 0) },
        ]
      : [],
    terse: ci
      ? `Sharpe ${fmtNum(ci.point)} ∈ [${fmtNum(ci.lower)}, ${fmtNum(ci.upper)}] @ ${fmtPct(ci.confidence, 0)} — lower ${passed ? '> 0 ✓' : '≤ 0 ✗'}`
      : 'no CI',
    narrative,
    tone: tone(passed),
  }
}

// ---- gate: deflated_sharpe -----------------------------------------------------------------

export function dsrStory(m: ValidateManifest): GateStory {
  const d: DSRBlock | undefined = m.dsr
  const passed = m.outcomes?.find((o) => o.name === 'deflated_sharpe')?.passed ?? d?.passed ?? null
  const single = (d?.n_trials ?? 1) <= 1

  const narrative = d
    ? `The probabilistic Sharpe (PSR) is ${fmtNum(d.psr, 4)} — the probability that the TRUE ` +
      `Sharpe is above zero given this sample's length, skew, and kurtosis. ` +
      (single
        ? `With a single configuration (no parameter sweep) there is nothing to deflate, so DSR ` +
          `equals PSR. `
        : `Deflating for ${d.n_trials} trials (expected best-by-luck Sharpe ` +
          `${fmtNum(d.expected_max_sharpe)}) leaves DSR ${fmtNum(d.dsr, 4)}. `) +
      (passed
        ? `Above the ${fmtNum(d.threshold, 2)} bar: the Sharpe is statistically distinguishable from noise.`
        : `Below the ${fmtNum(d.threshold, 2)} bar: on this sample size, the observed Sharpe is ` +
          `not yet statistically separable from zero.`)
    : 'No DSR block in this manifest.'

  return {
    gate: 'deflated_sharpe',
    title: 'Deflated / probabilistic Sharpe',
    passed,
    tests:
      'Is the Sharpe statistically real, net of sample noise (and of selection when many ' +
      'configurations were tried)? Requires DSR ≥ threshold (default 0.95).',
    stats: d
      ? [
          { label: 'PSR', value: fmtNum(d.psr, 4), term: 'psr' },
          { label: 'DSR', value: fmtNum(d.dsr, 4), term: 'dsr' },
          { label: 'Trials', value: String(d.n_trials) },
          { label: 'Threshold', value: fmtNum(d.threshold, 2) },
        ]
      : [],
    terse: d
      ? `PSR ${fmtNum(d.psr, 3)}${single ? ' (=DSR, single trial)' : ` · DSR ${fmtNum(d.dsr, 3)} @ ${d.n_trials} trials`} ${passed ? '≥' : '<'} ${fmtNum(d.threshold, 2)}`
      : 'no DSR',
    narrative,
    tone: tone(passed),
  }
}

// ---- gate: cpcv_oos ------------------------------------------------------------------------

export function cpcvStory(m: ValidateManifest): GateStory {
  const c: CPCVBlock | undefined = m.cpcv
  const passed = m.outcomes?.find((o) => o.name === 'cpcv_oos')?.passed ?? c?.passed ?? null

  const narrative = c
    ? `Instead of trusting one chronological path, CPCV re-splits the OOS stream into ` +
      `${c.n_folds} purged, embargoed fold combinations and scores each. Mean fold Sharpe ` +
      `${fmtNum(c.mean_sharpe)} (σ ${fmtNum(c.std_sharpe)}), with ${fmtPct(c.frac_positive, 0)} of ` +
      `folds positive. ` +
      (passed
        ? `The edge is not an artifact of one particular ordering of history.`
        : `A negative mean across combinations says the single walk-forward path flattered the ` +
          `strategy — under re-orderings the edge disappears.`)
    : 'No CPCV block in this manifest.'

  return {
    gate: 'cpcv_oos',
    title: 'Combinatorial purged CV',
    passed,
    tests:
      'Does the edge survive re-orderings of history? The OOS stream is recombined into many ' +
      'purged train/test group combinations; the gate wants the mean fold Sharpe > 0.',
    stats: c
      ? [
          { label: 'Folds', value: String(c.n_folds), term: 'cpcv' },
          { label: 'Mean Sharpe', value: fmtNum(c.mean_sharpe), term: 'sharpe' },
          { label: 'Std', value: fmtNum(c.std_sharpe) },
          { label: 'Frac > 0', value: fmtPct(c.frac_positive, 0) },
        ]
      : [],
    terse: c
      ? `${c.n_folds} folds: mean ${fmtNum(c.mean_sharpe)} ± ${fmtNum(c.std_sharpe)}, ${fmtPct(c.frac_positive, 0)} positive`
      : 'no CPCV',
    narrative,
    tone: tone(passed),
  }
}

/** All five gate stories in canonical gate order. */
export function gateStories(m: ValidateManifest): GateStory[] {
  return [walkForwardStory(m), nullStory(m), ciStory(m), dsrStory(m), cpcvStory(m)]
}
