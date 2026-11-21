import type { FigureCatalogueItem, RuleTest, RuleTestChecks } from '../../api/types'
import { FigureCard } from '../../components/FigureCard'
import { TearSheetStack } from '../../components/tearsheet/TearSheetStack'
import { ReadingBlock } from '../../components/ReadingBlock'
import { GLOSSARY } from '../../explain/glossary'
import { Timestamp } from '../../util/formatTime'
import { parseReading } from '../readingModel'
import {
  auditRows, checkRows, healthLine, dateRange, labelChips, NOT_RECORDED, pct, quickCaveat, ratio, summaryFigures, summaryHeadline, summaryNumbers,
  standardSetCommand, testedRows, variantRows, type Cell, type RuleManifest,
} from '../ruleTestModel'

/** A stored basis note shown as a sentence: first letter upper-case; the words are unchanged. */
function sentence(text: string | null | undefined): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ''
}

function Num({ cell }: { cell: Cell }) {
  const missing = cell.text === NOT_RECORDED
  return (
    <td className={`num mono${cell.tone ? ` ${cell.tone}` : ''}${missing ? ' muted' : ''}`} title={cell.reason ?? undefined}>
      {cell.text}
      {missing && cell.reason ? <span className="rule-test-reason">{cell.reason}</span> : null}
    </td>
  )
}

const FLAG_LABELS: Record<string, string> = {
  'below-benchmark': 'Holding the market had a higher risk-adjusted score.',
  'drawdown-with-market': 'The market also fell during the rule’s worst drop.',
  'concentrated-profit': 'A few trades accounted for most of the profit.',
  'fragile-to-costs': 'The result was sensitive to trading costs.',
  'fragile-to-parameters': 'Changing the rule settings affected the result.',
  'fragile-to-delay': 'Trading later reduced the risk-adjusted score.',
  'fragile-to-price-noise': 'Small price changes affected the result.',
  'implausibly-good': 'The result looks unusually strong.',
}

interface Props {
  test: RuleTest
  manifest: RuleManifest
  runId: string
  runName?: string
  figures: FigureCatalogueItem[] | null
  watermark?: string | null
  figureError?: string
  /** The stored toolbox checks: `null` while loading, a message when they could not be read, absent to omit the section. */
  checks?: RuleTestChecks | string | null
}

/** The toolbox checks stored for this test, one row each; the page only shows what the CLI stored. */
function ChecksRun({ checks, runId, testLabels }: { checks: RuleTestChecks | string | null; runId: string; testLabels: readonly string[] }) {
  const rows = typeof checks === 'object' && checks ? checkRows(checks, testLabels) : []
  return <section aria-label="Checks run on this test">
    <h3>Checks run on this test</h3>
    {checks === null ? <p role="status">Loading checks…</p>
      : typeof checks === 'string' ? <p role="alert">Could not load the checks. {checks}</p>
      : !rows.length ? <p className="muted">No checks have been run on this test yet. To run the standard set:{' '}
        <code className="mono">{standardSetCommand(runId)}</code></p>
      : <><p className="muted">{typeof checks === 'object' ? checks.counts?.text : null}</p>
        <table className="blotter summary-table rule-test-checks"><tbody>
        {rows.map(row => (
          <tr key={row.key}>
            <td className="k">{row.name}</td>
            <td>{row.failure ?? row.reading}
              <span className="rule-test-chips">
                {row.status && <span className="chip kind rule-test-status-chip" title={row.status.title}>{row.status.text}</span>}
                {row.chips.map(chip => <span key={chip.text} className="chip kind" title={chip.title}>{chip.text}</span>)}
              </span>
              {row.chips.length > 0 && <small className="muted">{row.chips.map(chip => chip.title).join(' ')}</small>}
            </td>
            <td className="muted"><Timestamp value={row.when} /></td>
          </tr>
        ))}
      </tbody></table></>}
  </section>
}

/** The run's reading, relayed with its checks: loading while they load, the old letter when no reading came. */
function Reading({ checks, manifest, labels }: { checks: RuleTestChecks | string | null; manifest: RuleManifest; labels: readonly string[] }) {
  if (checks === null) return <p role="status" className="muted">Loading the reading…</p>
  const reading = typeof checks === 'object' ? parseReading(checks.reading) : null
  const letter = manifest.verdict?.overall
  return <ReadingBlock reading={reading} oldLetter={typeof letter === 'string' ? letter : null} labels={labels} />
}

export function RuleTestReport({ test, manifest, runId, runName, figures, figureError, watermark, checks }: Props) {
  const diagnostics = test.diagnostics
  const flags = diagnostics?.flags ?? []
  const audit = auditRows(test)
  const variants = variantRows(test)
  const health = healthLine(manifest.data_health)
  const quick = quickCaveat(test)
  return (
    <section className="rule-test" aria-label="Rule test">
      <h2>{summaryHeadline(test, manifest.spine?.periods?.tradable)}</h2>
      {checks !== undefined && <Reading checks={checks} manifest={manifest} labels={test.labels} />}
      {health && <p>{health}</p>}
      <small>data from {dateRange(test.first_ts, test.last_ts)}</small>
      <TearSheetStack runId={runId} />
      {(['tradable', 'scored'] as const).map(period => {
        const row = manifest.spine?.periods?.[period]
        const charts = summaryFigures(figures ?? [], period)
        const title = period === 'tradable' ? 'Whole period the rule could trade' : 'Scored test periods only'
        return <section key={period} aria-label={title}>
          <h3>{title}</h3>
          <p>{dateRange(row?.first_ts, row?.last_ts)}</p>
          <div className="metric-grid" role="group" aria-label={title + ' results'}>
            {summaryNumbers(test, manifest, watermark, period).map(row => (
              <div className="metric" key={row.label}>
                <span title={row.gloss}>{row.label}</span>
                <strong className="metric-val mono">{row.value.text}</strong>
                {row.value.reason && <small className="muted">{row.value.reason}</small>}
                {row.caveats.map(note => note && <small key={note} className="muted">{note}</small>)}
              </div>
            ))}
          </div>
          <div>
            <p title={GLOSSARY.sharpe.short}><strong>Risk-adjusted score (Sharpe)</strong> · Rule{' '}
              {ratio(row?.strategy?.sharpe, row?.strategy?.reasons?.sharpe).text}
              {' · '}Buy and hold {ratio(row?.benchmark?.sharpe, row?.benchmark?.reasons?.sharpe).text}</p>
          </div>
          {figureError ? <p role="alert">Could not load the chart list. {figureError}</p>
            : figures === null ? <p role="status">Loading charts…</p>
            : charts.length ? <div>
              {charts.map(item => (
                <FigureCard key={item.figure_id} item={item} runId={runId} runName={runName} />
              ))}
            </div> : <p className="muted">Charts: not recorded</p>}
        </section>
      })}
      {quick && <p className="muted">{quick}</p>}
      {checks !== undefined && <ChecksRun checks={checks} runId={runId} testLabels={test.labels} />}
      <table className="blotter summary-table">
        <caption>Worth a look</caption>
        <tbody>
          {flags.map(flag => (
            <tr key={flag.flag}>
              <td title={flag.flag}>{FLAG_LABELS[flag.flag] ?? flag.detail}</td>
              {FLAG_LABELS[flag.flag] && <td>{flag.detail}</td>}
            </tr>
          ))}
          {!flags.length && <tr><td className="muted">{diagnostics ? 'The diagnostic checks flagged nothing.'
            : test.diagnostics_reason ?? 'Diagnostics not recorded.'}</td></tr>}
        </tbody>
      </table>

      <table className="blotter summary-table">
        <caption>If things were slightly different</caption>
        <thead><tr><th>Variant</th><th className="r" title={GLOSSARY.sharpe.short}>Sharpe</th>
          <th className="r" title={GLOSSARY.total_return.short}>Total return</th>
          <th className="r" title="Difference from the risk-adjusted score for the original settings.">Sharpe change</th></tr></thead>
        <tbody>
          {diagnostics ? variants.map(row => (
            <tr key={row.label}><td className="k">{row.label}</td><Num cell={row.sharpe} />
              <Num cell={row.totalReturn} /><Num cell={row.change} /></tr>
          )) : <tr><td colSpan={4}>{NOT_RECORDED}</td></tr>}
        </tbody>
        {diagnostics && <tfoot><tr><td colSpan={4} className="muted">
          {sentence(diagnostics.sensitivity?.basis) || NOT_RECORDED}.{variants.filter(row => row.note).map(row => ` ${row.label}: ${row.note}.`)}
        </td></tr></tfoot>}
      </table>

      {!manifest.spine?.periods && diagnostics && <details>
        <summary>Recorded full history</summary>
        <p>Rule return after costs {pct(diagnostics.full_sample?.total_return).text}
          {' · '}Buy and hold {pct(diagnostics.benchmark?.total_return).text}</p>
        <p>Return per year {pct(diagnostics.full_sample?.cagr).text}
          {' · '}Worst drop {pct(diagnostics.full_sample?.max_drawdown).text}
          {' · '}Closed trades {diagnostics.full_sample?.trades ?? NOT_RECORDED}</p>
      </details>}
      <details><summary>What was tested</summary>
        <table className="blotter summary-table rule-test-tested"><tbody>
          {testedRows(test).map(row => (
            <tr key={row.label}><td className="k">{row.label}</td><td className={row.mono ? 'mono' : undefined}>
              {row.label === 'Idea' && !test.idea?.trim() ? <small>{row.value}</small> : row.value}
            </td></tr>
          ))}
          <tr><td className="k">Labels</td><td><span className="rule-test-chips">
            {labelChips(test.labels).map(chip => <span key={chip.text} className="chip kind" title={chip.title}>{chip.text}</span>)}
          </span></td></tr>
        </tbody></table>
      </details>
      <details><summary>Checks on the test itself</summary>
        {audit.length ? <table className="blotter summary-table"><tbody>
          {audit.map(row => (
            <tr key={row.id}><td className="k">{row.check}</td>
              <td className="rule-test-status"><span className={`chip ${row.chip}`}>{row.status}</span></td>
              <td>{row.detail} <small className="muted mono">{row.id}</small></td></tr>
          ))}
        </tbody></table> : <p>{test.diagnostics_reason ?? 'No checks were recorded.'}</p>}
      </details>
    </section>
  )
}
