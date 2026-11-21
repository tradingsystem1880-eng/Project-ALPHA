import './ReadingBlock.css'
import { StateIcon } from './StateIcon'
import {
  aimSentence, aimSourceLine, BASIS_HINT, countLines, EVIDENCE_STEPS, evidenceStep, faultText, MEASURE_HINTS, num2, rangePicture, STATE_WORDS,
  type AimRow, type AlphaReading, type ReadingMeasure,
} from '../panels/readingModel'

const FOOTER = 'A reading describes the evidence. It is not advice and not an approval.'
const OLD_LETTER = /^[A-F]$/

/** The four steps of evidence strength as a small picture. The current step is filled, outlined and named. */
export function EvidenceScale({ word }: { word: string | null }) {
  const current = evidenceStep(word)
  return <ol className="reading-scale" aria-label="Evidence strength scale, four steps">
    {EVIDENCE_STEPS.map((step, index) => <li key={step} data-step={index + 1} data-current={index === current ? 'true' : undefined}
      aria-current={index === current ? 'step' : undefined}>
      <span className="reading-step-bar" aria-hidden="true" />
      <span className="reading-step-name">{step}</span>
    </li>)}
  </ol>
}

function Checks({ reading }: { reading: AlphaReading }) {
  return <ul className="reading-checks" aria-label="Fact checks">
    {reading.checks.map(item => <li key={item.name} data-state={item.state} title={item.detail}>
      <StateIcon state={item.state} /><span className="reading-check-name">{item.name.replaceAll('-', ' ')}</span>
      <strong>{STATE_WORDS[item.state]}</strong>
    </li>)}
  </ul>
}

function RangePicture({ row }: { row: AimRow }) {
  const picture = rangePicture(row)
  if (!picture || !row.interval) return null
  const [low, high] = row.interval
  const label = `${row.measure}: 95% range ${num2(low)} to ${num2(high)}; the aim ${num2(row.aim)}; ${row.relation}`
  return <div className="reading-range">
    <div className="reading-range-track" role="img" aria-label={label}>
      <span className="reading-range-bar" style={{ left: `${picture.left}%`, width: `${picture.right - picture.left}%` }} />
      {picture.observed !== null && <span className="reading-range-observed" style={{ left: `${picture.observed}%` }} />}
      <span className="reading-range-tick" style={{ left: `${picture.aim}%` }} />
    </div>
    <small className="muted">Bar: 95% range {num2(low)} to {num2(high)} · Tick: the aim {num2(row.aim)} · Dot: this test {num2(row.observed)}</small>
  </div>
}

function Aim({ reading }: { reading: AlphaReading }) {
  const { source, rows, basis } = reading.aim
  return <section aria-label="Against the aim" className="reading-part">
    <h4>Against the aim</h4>
    {rows.length ? <ul className="reading-aim">{rows.map(row => <li key={row.measure}>
      <p><span>{aimSentence(row, source)}</span> · <strong>{row.relation}</strong></p>
      <RangePicture row={row} />
    </li>)}</ul> : null}
    <p className="muted">{aimSourceLine(source)}</p>
    {basis && <details className="muted"><summary>Exact basis as stored</summary><small>{basis}</small></details>}
  </section>
}

function Measures({ rows }: { rows: ReadingMeasure[] }) {
  const text = (row: ReadingMeasure): string => {
    if (row.value === null) return 'not recorded'
    if (row.name === 'closed trades') return String(row.value)
    return row.name.includes('drawdown') ? `${(row.value * 100).toFixed(1)}%` : num2(row.value)
  }
  return <section aria-label="Measures" className="reading-part">
    <h4>Measures</h4>
    <table className="blotter summary-table reading-measures"><thead><tr>
      <th scope="col">Measure</th><th scope="col" className="r">Value</th><th scope="col">95% range</th><th scope="col">Basis</th>
    </tr></thead><tbody>{rows.map(row => <tr key={row.name}>
      <td className="k" title={MEASURE_HINTS[row.name]}>{row.name}</td><td className="num mono">{text(row)}</td>
      <td className="mono">{row.interval ? `${num2(row.interval[0])} to ${num2(row.interval[1])}` : 'none'}</td>
      <td className="muted">{row.basis ?? 'not recorded'}</td>
    </tr>)}</tbody></table>
    <ul className="reading-legend muted">
      {rows.filter(row => MEASURE_HINTS[row.name]).map(row => <li key={row.name}><strong>{row.name}</strong>: {MEASURE_HINTS[row.name]}.</li>)}
      <li>{BASIS_HINT}</li>
    </ul>
  </section>
}

function Fault({ reading, text }: { reading: AlphaReading; text: string }) {
  return <section aria-label="Reading" className="reading-block reading-fault" role="alert">
    <p className="reading-sentence"><strong>Fault: {text}. Fix this first. No reading.</strong></p>
    <Checks reading={reading} />
    <details className="muted"><summary>Show numbers that are not to be read</summary>
      <ul>{reading.measures.map(row => <li key={row.name}>{row.name}: {row.value === null ? 'not recorded' : num2(row.value)}</li>)}</ul>
    </details>
  </section>
}

interface Props {
  /** The stored or derived reading; null when the run has none. */
  reading: AlphaReading | null
  /** The old letter, shown muted only when there is no reading to show. */
  oldLetter?: string | null
  /** The test's own labels; a repeat is named in the counts. */
  labels?: readonly string[]
}

/** One reading in context: fact checks, a headline sentence, evidence strength, the aim, measures and counts. Never a grade. */
export function ReadingBlock({ reading, oldLetter = null, labels = [] }: Props) {
  if (!reading) {
    return <section aria-label="Reading" className="reading-block">
      {oldLetter && OLD_LETTER.test(oldLetter) ? <p className="muted">graded {oldLetter} under the old rules</p>
        : <p className="muted">No reading was recorded for this test.</p>}
      <small className="muted">{FOOTER}</small>
    </section>
  }
  const fault = faultText(reading)
  if (fault !== null) return <Fault reading={reading} text={fault} />
  const counts = countLines(reading.counts, labels)
  return <section aria-label="Reading" className="reading-block">
    <Checks reading={reading} />
    <p className="reading-sentence">{reading.sentence}</p>
    {(reading.costsLine || reading.periodsLine) && <p className="muted reading-costs">{[reading.costsLine, reading.periodsLine].filter(Boolean).join(' ')}</p>}
    <section aria-label="Evidence strength" className="reading-part">
      <h4>Evidence strength: {reading.evidence.word ?? 'not recorded'}</h4>
      <EvidenceScale word={reading.evidence.word} />
      {reading.evidence.because.length > 0 && <ul className="reading-because">{reading.evidence.because.map(item => <li key={item}>{item}</li>)}</ul>}
    </section>
    <Aim reading={reading} />
    {reading.measures.length > 0 && <Measures rows={reading.measures} />}
    {counts.length > 0 && <section aria-label="Counts" className="reading-part"><h4>Counts</h4>
      <ul className="reading-counts">{counts.map(line => <li key={line}>{line}</li>)}</ul></section>}
    <small className="muted">{FOOTER}</small>
  </section>
}

interface SetupProps {
  kind: 'study' | 'trade'
  evidence: string | null
  oldWording: boolean
  sentence: string | null
  /** This run's place among the ledger rows of its kind on the same idea, and their number. */
  position: number | null
  count: number | null
}

/** The Setup Lab reading: the evidence word and scale, the stored sentence and the family line. Never an outcome word. */
export function SetupReadingBlock({ kind, evidence, oldWording, sentence, position, count }: SetupProps) {
  const plural = kind === 'study' ? 'studies' : 'trades'
  const family = count === null ? null
    : position === null ? `Setup ${kind}: not among the ${count} ${count === 1 ? kind : plural} recorded for this idea.`
    : `Setup ${kind} ${position} of ${count} recorded for this idea.`
  return <section aria-label="Reading" className="reading-block">
    {evidence ? <section aria-label="Evidence strength" className="reading-part">
      <h4>Evidence strength: {evidence}{oldWording ? ' (old wording)' : ''}</h4>
      <EvidenceScale word={evidence} />
    </section> : <p className="muted">No evidence word was recorded.</p>}
    {sentence && <p className="reading-sentence">{sentence}</p>}
    {family && <p>{family}</p>}
    {evidence && <p className="muted">The figure adjusted for the number of {plural} is shown by <code className="mono">alpha setup {kind}</code>.</p>}
    <small className="muted">{FOOTER}</small>
  </section>
}

