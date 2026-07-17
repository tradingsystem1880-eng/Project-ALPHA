// Forecast-run stories: the outcome cone, its calibration, and the pretraining-leakage caveat.

import { fmtPct } from '../util/format'
import type { Explained, ForecastEvalSummary, ForecastManifest, StatChip, Suggestion } from './types'

export interface ForecastStory extends Explained {
  title: string
  stats: StatChip[]
}

export function forecastStories(m: ForecastManifest): ForecastStory[] {
  const out: ForecastStory[] = []
  const s = m.summary
  if (s) {
    const probUp = s.prob_up ?? null
    const med = s.median_end_return ?? null
    const lo = s.p05_end_return ?? null
    const hi = s.p95_end_return ?? null
    out.push({
      title: 'Outcome cone',
      stats: [
        { label: 'P(up)', value: fmtPct(probUp, 0) },
        { label: 'Median', value: fmtPct(med, 1) },
        { label: 'p05', value: fmtPct(lo, 1) },
        { label: 'p95', value: fmtPct(hi, 1) },
      ],
      terse: `P(up) ${fmtPct(probUp, 0)} · median ${fmtPct(med, 1)} · 90% band [${fmtPct(lo, 1)}, ${fmtPct(hi, 1)}]`,
      narrative:
        `${String(m.params?.samples ?? '—')} sampled paths from the model put ` +
        `${fmtPct(probUp, 0)} of end-states above today's close, with a median end return of ` +
        `${fmtPct(med, 1)} and 90% of paths inside [${fmtPct(lo, 1)}, ${fmtPct(hi, 1)}]. Read ` +
        `the WIDTH before the direction: a cone this ${widthWord(lo, hi)} says the model sees ` +
        `${widthWord(lo, hi) === 'wide' ? 'high' : 'contained'} uncertainty, and any directional ` +
        `bet is only as good as the calibration measured by a forecast eval.`,
      tone: 'info',
    })
  }
  if (m.pretrain?.overlap) {
    out.push({
      title: 'Pretraining overlap — in-sample forecast',
      stats: [{ label: 'Cutoff', value: String(m.pretrain.cutoff ?? '—'), term: 'pretrain_overlap' }],
      terse: 'window predates pretrain cutoff — treat as in-sample',
      narrative:
        `This window overlaps the model's pretraining data (cutoff ${String(m.pretrain.cutoff ?? '—')}): ` +
        `the model may have memorized the answer. Skill measured here is an upper bound, not ` +
        `evidence.`,
      tone: 'warn',
    })
  }
  const pre = m.summary_pre_cutoff
  const post = m.summary_post_cutoff
  if (pre || post) {
    if (post) out.push(evalStory(post, 'Post-cutoff (honest zero-shot)', true))
    if (pre) out.push(evalStory(pre, 'Pre-cutoff (overlaps pretraining)', false))
  }
  return out
}

function widthWord(lo: number | null | undefined, hi: number | null | undefined): string {
  if (typeof lo !== 'number' || typeof hi !== 'number') return 'wide'
  return hi - lo > 0.15 ? 'wide' : 'tight'
}

function evalStory(s: ForecastEvalSummary, title: string, honest: boolean): ForecastStory {
  const skillRw = s.skill_vs_rw ?? null
  const skillBs = s.skill_vs_bootstrap ?? null
  const hasSkill = typeof skillRw === 'number' && skillRw > 0 && typeof skillBs === 'number' && skillBs > 0
  return {
    title,
    stats: [
      { label: 'Origins', value: String(s.n_origins ?? '—') },
      { label: 'Skill vs RW', value: fmtPct(skillRw, 1), term: 'crps' },
      { label: 'Skill vs bootstrap', value: fmtPct(skillBs, 1), term: 'crps' },
      { label: 'Coverage 80', value: fmtPct(s.coverage80, 0), term: 'coverage' },
      { label: 'Hit rate', value: fmtPct(s.hit_rate, 0), term: 'hit_rate' },
    ],
    terse: `skill RW ${fmtPct(skillRw, 0)} / boot ${fmtPct(skillBs, 0)} · cov80 ${fmtPct(s.coverage80, 0)} · hit ${fmtPct(s.hit_rate, 0)}`,
    narrative:
      `Across ${s.n_origins ?? '—'} rolling origins, distributional skill is ` +
      `${fmtPct(skillRw, 1)} vs random-walk-with-drift and ${fmtPct(skillBs, 1)} vs a return ` +
      `bootstrap (positive = better than the baseline). The 80% band covered ` +
      `${fmtPct(s.coverage80, 0)} of realized outcomes (want ≈80%: lower = overconfident, ` +
      `higher = underconfident) and the median called the sign ${fmtPct(s.hit_rate, 0)} of the time. ` +
      (honest
        ? hasSkill
          ? `Genuine zero-shot skill on unseen data.`
          : `No skill above the free baselines on unseen data — the honest number to believe.`
        : `Overlaps pretraining — an upper bound, not evidence.`),
    tone: honest ? (hasSkill ? 'good' : 'bad') : 'warn',
  }
}

export function forecastSuggestions(m: ForecastManifest): Suggestion[] {
  const out: Suggestion[] = []
  const post = m.summary_post_cutoff
  if (m.command === 'forecast_run' && m.symbol) {
    out.push({
      title: 'A cone is a claim — measure its calibration',
      why:
        `One forecast can't be judged; a rolling forecast eval scores CRPS/coverage/hit-rate ` +
        `against free baselines, split pre/post the pretraining cutoff.`,
      action: { command: 'forecast eval', args: `${m.symbol} --horizon ${String(m.params?.horizon ?? 21)}` },
    })
  }
  if (post && typeof post.skill_vs_rw === 'number' && post.skill_vs_rw <= 0) {
    out.push({
      title: 'No post-cutoff skill vs random walk — do not trade this signal',
      why:
        `On data the model has never seen it fails to beat a drift random walk. Kronos zero-shot ` +
        `showed the same on BTC-USD; the honest conclusion is the model adds no tradable edge ` +
        `on this symbol/horizon.`,
    })
  }
  return out
}
