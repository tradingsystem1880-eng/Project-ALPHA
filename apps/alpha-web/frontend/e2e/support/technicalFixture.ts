// Deterministic test data for the technical chart: a seeded random-walk OHLCV series and a
// stand-in for `alpha chart overlays` that computes the same studies (SMA, EMA, RSI, MACD) and
// refuses too-short windows with the CLI's exact sentence. Test fixture only — the SPA never
// computes a study value.

import type { components } from '../../src/api/generated'

type Candle = components['schemas']['Candle']
const DAY = 86400

/** `n` observations from `startIso`; weekday-only when `weekdays` (an equities calendar). */
export function walkBars(n: number, startIso = '2025-10-06', weekdays = true, seed = 7, start = 240): Candle[] {
  let state = seed >>> 0
  const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 2 ** 32 }
  const bars: Candle[] = []
  let close = start
  for (let t = Date.parse(`${startIso}T00:00:00Z`) / 1000; bars.length < n; t += DAY) {
    const weekday = new Date(t * 1000).getUTCDay()
    if (weekdays && (weekday === 0 || weekday === 6)) continue
    const drift = 0.0009 + 0.018 * (random() - 0.5) * 2 * (random() < 0.08 ? 2.4 : 1)
    const open = close * (1 + (random() - 0.5) * 0.012)
    close = Math.max(1, open * (1 + drift))
    const high = Math.max(open, close) * (1 + random() * 0.012)
    const low = Math.min(open, close) * (1 - random() * 0.012)
    const round = (v: number) => Math.round(v * 100) / 100
    bars.push({ t, o: round(open), h: round(high), l: round(low), c: round(close), v: Math.round(2.5e7 * (0.5 + random() + (random() < 0.05 ? 3 * random() : 0))) })
  }
  return bars
}

const sma = (x: number[], w: number) => x.map((_, i) => i < w - 1 ? null : x.slice(i - w + 1, i + 1).reduce((a, b) => a + b, 0) / w)
function ema(x: number[], w: number): (number | null)[] {
  const out: (number | null)[] = []; const k = 2 / (w + 1); let prev: number | null = null
  x.forEach((v, i) => { if (i < w - 1) { out.push(null); return } prev = prev === null ? x.slice(0, w).reduce((a, b) => a + b, 0) / w : v * k + prev * (1 - k); out.push(prev) })
  return out
}
function rsi(x: number[], w: number): (number | null)[] {
  let gain = 0, loss = 0
  return x.map((v, i) => {
    if (i === 0) return null
    const d = v - x[i - 1], g = Math.max(d, 0), l = Math.max(-d, 0)
    if (i <= w) { gain += g / w; loss += l / w; return i < w ? null : 100 - 100 / (1 + gain / (loss || 1e-12)) }
    gain = (gain * (w - 1) + g) / w; loss = (loss * (w - 1) + l) / w
    return 100 - 100 / (1 + gain / (loss || 1e-12))
  })
}

/** Bars each spec reads (mirrors `_bars_needed` for the studies this stand-in serves). */
const needed = (name: string, p: number[]) => name === 'macd' ? p[1] + p[2] : p[0]

/** One `alpha chart overlays` series list for a spec, or the CLI's short-window refusal text. */
export function studySeries(spec: string, bars: Candle[]): { series: components['schemas']['OverlaySeries'][] } | { refusal: string } {
  const [name, ...raw] = spec.split(':'), p = raw.map(Number)
  const longest = needed(name, p)
  if (longest >= bars.length) return { refusal: `${spec} needs more than ${longest} bars, the window has ${bars.length}` }
  const close = bars.map(b => b.c)
  const one = (id: string, label: string, pane: string, values: (number | null)[], style: 'line' | 'histogram' = 'line') => ({ id, name: label, pane, style, values, warmup: values.findIndex(v => v !== null) })
  if (name === 'sma') return { series: [one(spec, `SMA ${p[0]}`, 'price', sma(close, p[0]))] }
  if (name === 'ema') return { series: [one(spec, `EMA ${p[0]}`, 'price', ema(close, p[0]))] }
  if (name === 'rsi') return { series: [one(spec, `RSI ${p[0]}`, 'rsi', rsi(close, p[0]))] }
  if (name === 'macd') {
    const fast = ema(close, p[0]), slow = ema(close, p[1])
    const line = close.map((_, i) => fast[i] === null || slow[i] === null ? null : fast[i]! - slow[i]!)
    const start = line.findIndex(v => v !== null)
    const signalTail = ema(line.slice(start) as number[], p[2])
    const signal = [...line.slice(0, start).map(() => null), ...signalTail]
    const hist = line.map((v, i) => v === null || signal[i] === null ? null : v - signal[i]!)
    const tag = `MACD ${p[0]}/${p[1]}/${p[2]}`
    return { series: [one(`${spec}:line`, `${tag} line`, 'macd', line), one(`${spec}:signal`, `${tag} signal`, 'macd', signal), one(`${spec}:hist`, `${tag} histogram`, 'macd', hist, 'histogram')] }
  }
  return { series: [one(spec, spec.toUpperCase().replace(':', ' '), 'price', close)] }
}
