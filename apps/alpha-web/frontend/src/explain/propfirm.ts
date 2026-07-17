// Prop-firm Monte-Carlo stories: would this return stream survive a funded-account ruleset?

import { fmtNum, fmtPct } from '../util/format'
import type { Explained, PropfirmManifest, StatChip, Suggestion } from './types'

export interface PropfirmStory extends Explained {
  title: string
  stats: StatChip[]
}

function money(v: number | null | undefined): string {
  return typeof v === 'number' && Number.isFinite(v)
    ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : '—'
}

export function propfirmStories(m: PropfirmManifest): PropfirmStory[] {
  const met = m.metrics ?? {}
  const rules = m.rules ?? {}
  const pPass = met.pass_probability ?? null
  const pBust = met.bust_probability ?? null
  const pPayout = met.payout_probability ?? null
  const ev = met.expected_payout ?? null
  const days = met.median_days_to_pass ?? null
  const evTone = typeof ev === 'number' ? (ev > 0 ? 'good' : 'bad') : 'info'

  return [
    {
      title: `Evaluation odds — ${m.firm ?? 'custom'} rules`,
      stats: [
        { label: 'P(pass)', value: fmtPct(pPass, 1), term: 'pass_probability' },
        { label: 'P(bust)', value: fmtPct(pBust, 1) },
        { label: 'P(payout)', value: fmtPct(pPayout, 1) },
        { label: 'Median days', value: fmtNum(days, 0) },
      ],
      terse: `pass ${fmtPct(pPass, 0)} · bust ${fmtPct(pBust, 0)} · payout ${fmtPct(pPayout, 0)} · median ${fmtNum(days, 0)}d`,
      narrative:
        `${(m.n_paths ?? 0).toLocaleString()} bootstrap re-orderings of the strategy's daily ` +
        `returns walked through the ${m.firm ?? 'custom'} ruleset (target ` +
        `${money(rules.profit_target as number)}, max drawdown ${money(rules.max_drawdown as number)}` +
        `${rules.trailing ? ' trailing' : ''}${typeof rules.daily_loss_limit === 'number' ? `, daily loss ${money(rules.daily_loss_limit)}` : ''}): ` +
        `${fmtPct(pPass, 1)} clear the evaluation (median ${fmtNum(days, 0)} days), ` +
        `${fmtPct(pBust, 1)} bust somewhere along the way, and ${fmtPct(pPayout, 1)} reach at ` +
        `least one payout. Note pass and bust are not complements — a path can pass the eval ` +
        `and still bust the funded account later.`,
      tone: typeof pPass === 'number' ? (pPass >= 0.5 ? 'good' : pPass >= 0.25 ? 'warn' : 'bad') : 'info',
    },
    {
      title: 'Expected value',
      stats: [
        { label: 'E[payout]', value: money(ev) },
        { label: 'Eval fee', value: money(rules.eval_fee as number) },
        { label: 'Profit split', value: fmtPct(rules.profit_split as number, 0) },
        { label: 'Horizon', value: `${m.horizon_days ?? '—'}d` },
      ],
      terse: `E[net payout] ${money(ev)} over ${m.horizon_days ?? '—'}d`,
      narrative:
        `Averaged over ALL paths — busts, fees, and the ${fmtPct(rules.profit_split as number, 0)} ` +
        `profit split included — the expected net take is ${money(ev)} per attempt. ` +
        (evTone === 'good'
          ? `Positive EV: the strategy's edge survives the firm's rule friction.`
          : `Negative or nil EV: whatever the strategy earns, the ruleset (drawdown clamps, ` +
            `fees, split) takes more. These presets are illustrative — but a strategy that ` +
            `cannot beat them on paper will not beat them live.`),
      tone: evTone,
    },
  ]
}

export function propfirmSuggestions(m: PropfirmManifest): Suggestion[] {
  const out: Suggestion[] = []
  const pBust = m.metrics?.bust_probability ?? null
  const ev = m.metrics?.expected_payout ?? null
  if (typeof pBust === 'number' && pBust > 0.5) {
    out.push({
      title: `Bust probability ${fmtPct(pBust, 0)} — the drawdown rules bind before the edge pays`,
      why:
        `Most paths hit the loss limits before the profit target. The classic fix is cutting ` +
        `position size: halving vol roughly halves drawdown breaches while only halving the ` +
        `speed to target — usually a favorable trade against a hard bust line.`,
    })
  }
  if (typeof ev === 'number' && ev <= 0) {
    out.push({
      title: 'Negative expected payout — do not pay this eval fee yet',
      why:
        `Across all simulated paths the attempt loses money net of fees and splits. Improve the ` +
        `underlying strategy first (the validate gauntlet is the gate that matters); rule ` +
        `presets here are illustrative, not authoritative firm terms.`,
    })
  }
  return out
}
