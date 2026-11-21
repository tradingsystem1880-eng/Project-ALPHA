// A stored reading (`AlphaReadingV1`) as the screens use it. The command line states every word and
// number; this module only checks the shape, orders the parts and places the range picture.

export const EVIDENCE_STEPS = ['too little to read', 'not clear of chance', 'some evidence', 'clear of chance'] as const
export type EvidenceWord = (typeof EVIDENCE_STEPS)[number]
export type CheckState = 'sound' | 'fault' | 'not-checked'
/** The word a fact check shows for each state. */
export const STATE_WORDS: Record<CheckState, string> = { sound: 'sound', fault: 'fault', 'not-checked': 'not checked' }
export type Interval = [number, number]

export interface ReadingCheck { name: string; state: CheckState; detail: string }
export interface ReadingMeasure { name: string; value: number | null; interval: Interval | null; basis: string | null; notToBeRead: boolean }
export interface AimRow { measure: string; aim: number; observed: number | null; interval: Interval | null; relation: string }
export interface ReadingCounts {
  trial_n: number | null; family_trials: number | null; variants_tried: number | null; best_of: number | null; family_id: string | null
}
export type AimSource = 'card' | 'default' | 'none'
export interface AlphaReading {
  checks: ReadingCheck[]
  measures: ReadingMeasure[]
  evidence: { word: EvidenceWord | null; because: string[] }
  aim: { source: AimSource; basis: string | null; rows: AimRow[] }
  counts: ReadingCounts
  sentence: string
}

type Obj = Record<string, unknown>
const obj = (value: unknown): Obj | null => (typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Obj) : null)
const num = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null)
const count = (value: unknown): number | null => (typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null)
const str = (value: unknown): string | null => (typeof value === 'string' && value ? value : null)
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : [])

function interval(value: unknown): Interval | null {
  const pair = list(value)
  const [low, high] = [num(pair[0]), num(pair[1])]
  return pair.length === 2 && low !== null && high !== null ? [low, high] : null
}

const STATES: readonly string[] = ['sound', 'fault', 'not-checked']

function check(value: unknown): ReadingCheck | null {
  const row = obj(value)
  const [name, state, detail] = [str(row?.name), str(row?.state), str(row?.detail)]
  return name && detail && state && STATES.includes(state) ? { name, state: state as CheckState, detail } : null
}

function measure(value: unknown): ReadingMeasure | null {
  const row = obj(value)
  const name = str(row?.name)
  return row && name
    ? { name, value: num(row.value), interval: interval(row.interval_95), basis: str(row.basis), notToBeRead: row.not_to_be_read === true }
    : null
}

function aimRow(value: unknown): AimRow | null {
  const row = obj(value)
  const [name, aim, relation] = [str(row?.measure), num(row?.aim), str(row?.relation)]
  return row && name && aim !== null && relation
    ? { measure: name, aim, observed: num(row.observed), interval: interval(row.interval_95), relation }
    : null
}

/** A stored reading, or null when the value is not one (or names an evidence word this screen does not know). */
export function parseReading(value: unknown): AlphaReading | null {
  const root = obj(value)
  const evidence = obj(root?.evidence)
  const aim = obj(root?.aim)
  const sentence = str(root?.sentence)
  if (!root || !evidence || !aim || !sentence || !Array.isArray(root.checks)) return null
  const word = evidence.word === null || evidence.word === undefined ? null : str(evidence.word)
  if (word !== null && !(EVIDENCE_STEPS as readonly string[]).includes(word)) return null
  const counts = obj(root.counts) ?? {}
  const source = str(aim.source)
  return {
    checks: root.checks.map(check).filter((row): row is ReadingCheck => row !== null),
    measures: list(root.measures).map(measure).filter((row): row is ReadingMeasure => row !== null),
    evidence: { word: word as EvidenceWord | null, because: list(evidence.because).filter((item): item is string => typeof item === 'string') },
    aim: {
      source: source === 'card' || source === 'default' ? source : 'none',
      basis: str(aim.basis),
      rows: list(aim.rows).map(aimRow).filter((row): row is AimRow => row !== null),
    },
    counts: {
      trial_n: count(counts.trial_n), family_trials: count(counts.family_trials), variants_tried: count(counts.variants_tried),
      best_of: count(counts.best_of), family_id: str(counts.family_id),
    },
    sentence,
  }
}

/** The first fault the checks found, or null when none. A fault replaces the whole reading. */
export function faultText(reading: AlphaReading): string | null {
  return reading.checks.find(item => item.state === 'fault')?.detail ?? null
}

/** Position (0 to 3) of an evidence word on the four-step scale; -1 for anything else. */
export function evidenceStep(word: string | null | undefined): number {
  return word ? (EVIDENCE_STEPS as readonly string[]).indexOf(word) : -1
}

export const num2 = (value: number | null): string => (value === null ? 'not recorded' : value.toFixed(2))
export const num3 = (value: number | null): string => (value === null ? 'not recorded' : value.toFixed(3))

export interface RangePicture {
  /** Percent from the left edge of the picture: the bar's ends, the aim tick and the observed mark. */
  left: number
  right: number
  aim: number
  observed: number | null
}

/** Where the strategy's 95% range, the aim and the observed value sit on one line; null without a usable range. */
export function rangePicture(row: AimRow): RangePicture | null {
  if (!row.interval || row.interval[0] > row.interval[1]) return null
  const [low, high] = row.interval
  const points = [low, high, row.aim, ...(row.observed === null ? [] : [row.observed])]
  const lo = Math.min(...points)
  const hi = Math.max(...points)
  const pad = (hi - lo || 1) * 0.1
  const place = (value: number): number => ((value - (lo - pad)) / (hi - lo + 2 * pad)) * 100
  return {
    left: place(low), right: place(high), aim: place(row.aim),
    observed: row.observed === null ? null : place(row.observed),
  }
}

const capital = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1)

/** "Out-of-sample Sharpe 0.75 against buy-and-hold 0.78": what was compared. */
export function aimSentence(row: AimRow, source: AimSource): string {
  const target = source === 'default' ? 'buy-and-hold' : 'the aim'
  return `${capital(row.measure)} ${num2(row.observed)} against ${target} ${num2(row.aim)}`
}

export function aimSourceLine(source: AimSource): string {
  return source === 'default'
    ? 'Default aim: beat buy-and-hold over the same days, with no costs. The aim’s own uncertainty is not included.'
    : source === 'card' ? 'Aim from the idea card' : 'No aim was recorded for this reading.'
}

/** The counts in plain words; a repeat is labelled, never hidden. */
export function countLines(counts: ReadingCounts, labels: readonly string[]): string[] {
  return [
    counts.trial_n ? `Ledger entry ${counts.trial_n}` : '',
    counts.family_trials ? `Family counted as ${counts.family_trials} tries` : '',
    counts.best_of ? `Best of ${counts.best_of} variants` : '',
    labels.includes('repeat') ? 'A repeat of an earlier test; it still counts as another try' : '',
  ].filter(Boolean)
}

/** One plain-words hint per measure the command line names. Words only; no number is read from here. */
export const MEASURE_HINTS: Record<string, string> = {
  'out-of-sample Sharpe': 'Return for each unit of risk, on days the rule was not tuned on',
  'deflated Sharpe': 'Sharpe after allowing for the number of ideas tried',
  'Sharpe before counting trials': 'Sharpe without allowing for the number of ideas tried',
  'cross-validated mean Sharpe': 'Average over many re-splits of the test period',
  'maximum drawdown': 'The largest fall from a peak',
  'closed trades': 'Trades that were opened and later closed',
}
/** What the stored basis words mean, shown once under the table. */
export const BASIS_HINT = '“Walk-forward out-of-sample, after costs” means: tested on later days than the rule learned from, with trading costs taken off.'

/** What a run list or summary row says for a run: its stored evidence word, else its old grade (a letter or an old word), muted by the caller. */
export function runWord(evidence: string | null | undefined, letter: unknown): { text: string; old: boolean } | null {
  if (evidence) return { text: evidence, old: false }
  return typeof letter === 'string' && letter.trim() ? { text: `graded ${letter} under the old rules`, old: true } : null
}

interface RunWords { evidence?: string | null; verdict?: string | null }

/** The evidence word of a stored manifest: its stored reading, else its old letter (muted by the caller). */
export function manifestWord(manifest: Obj): { text: string; old: boolean } | null {
  // A run made under the current contract (it records `labels`) never reads as an old grade.
  const verdict = 'labels' in manifest ? null : (obj(manifest.verdict)?.overall ?? manifest.verdict)
  return runWord(str(obj(obj(manifest.reading)?.evidence)?.word), verdict)
}

/** What a toast says after the run's label: the evidence word, or nothing. Never a gate result. */
export function toastDetail(run: RunWords & { label?: string | null }): string {
  const word = runWord(run.evidence, run.verdict)
  return `${run.label ?? ''}${word ? ` — ${word.text}` : ''}`
}

/** The hint after a run in the command palette: kind, label and the evidence word. */
export function paletteHint(run: RunWords & { kind: string; label?: string | null }): string {
  const word = runWord(run.evidence, run.verdict)
  return `${run.kind} · ${run.label ?? '—'}${word ? ` · ${word.text}` : ''}`
}
