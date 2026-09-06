// Strategy Builder document (spec 2026-09-01 §4.2 Phase 5 S4): rows of `left op right` become a
// strict rule spec, checked live by `alpha rules validate`, saved by `alpha rules save`, and tested
// with `alpha backtest run --strategy rules --rules <id>` in the standalone sandbox. The SPA never
// judges a rule: the CLI's validation report is shown verbatim, and a governed run goes through
// the Strategy Lab like any other backtest.

import { useCallback, useEffect, useState } from 'react'

import { api, runContextForProject } from '../api/client'
import type { RuleRecord, RuleSummary, RuleValidation } from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { useLinked } from '../context/linked'
import type { PanelHandleProps } from '../context/panelHandle'
import { useSettings } from '../state/settings'
import { openRunDetail, openStrategyLab } from './actions'
import {
  EMPTY_FORM,
  EMPTY_ROW,
  OPERAND_EXAMPLES,
  OPS,
  formToSpec,
  recordToForm,
  ruleIdError,
  sandboxArgs,
  type BuilderForm,
  type Op,
  type Row,
} from './ruleBuilderModel'

type Side = 'longRows' | 'shortRows'

function RowEditor({
  side,
  rows,
  onChange,
}: {
  side: Side
  rows: Row[]
  onChange: (rows: Row[]) => void
}) {
  const label = side === 'longRows' ? 'Be long while all of these hold' : 'Be short while all of these hold'
  const update = (index: number, patch: Partial<Row>) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  return (
    <fieldset className="builder-side">
      <legend>{label}</legend>
      {rows.map((row, index) => (
        <div className="builder-row" key={index}>
          <input
            className="field mono"
            aria-label={`${side === 'longRows' ? 'long' : 'short'} condition ${index + 1} left`}
            value={row.left}
            placeholder="sma:20"
            spellCheck={false}
            onChange={(event) => update(index, { left: event.target.value })}
          />
          <select
            className="field"
            aria-label={`${side === 'longRows' ? 'long' : 'short'} condition ${index + 1} operator`}
            value={row.op}
            onChange={(event) => update(index, { op: event.target.value as Op })}
          >
            {OPS.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
          <input
            className="field mono"
            aria-label={`${side === 'longRows' ? 'long' : 'short'} condition ${index + 1} right`}
            value={row.right}
            placeholder="sma:50"
            spellCheck={false}
            onChange={(event) => update(index, { right: event.target.value })}
          />
          <button
            type="button"
            className="btn"
            aria-label={`Remove ${side === 'longRows' ? 'long' : 'short'} condition ${index + 1}`}
            onClick={() => onChange(rows.filter((_, i) => i !== index))}
          >
            ×
          </button>
        </div>
      ))}
      <button type="button" className="btn" onClick={() => onChange([...rows, { ...EMPTY_ROW }])}>
        + condition
      </button>
    </fieldset>
  )
}

export function StrategyBuilder(_props: PanelHandleProps) {
  const linked = useLinked()
  const { profile } = useSettings()
  const [form, setForm] = useState<BuilderForm>({ ...EMPTY_FORM, longRows: [{ ...EMPTY_ROW }] })
  const [saved, setSaved] = useState<RuleSummary[]>([])
  const [check, setCheck] = useState<RuleValidation | { valid: false; error: string } | null>(null)
  const [savedRecord, setSavedRecord] = useState<RuleRecord | null>(null)
  const [symbol, setSymbol] = useState(linked.symbol ?? '')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    api
      .rules()
      .then((list) => setSaved(list.rules))
      .catch((cause: unknown) => setError(String(cause)))
  }, [])
  useEffect(refresh, [refresh])
  useEffect(() => {
    if (linked.symbol) setSymbol(linked.symbol)
  }, [linked.symbol])

  // Live validation: the rows are mapped to the spec here (a typo fails locally with its
  // message), then the CLI's strict parser has the final word.
  const hasRows = [...form.longRows, ...form.shortRows].some((row) => row.left.trim() || row.right.trim())
  const formKey = JSON.stringify(form)
  useEffect(() => {
    if (!hasRows) {
      setCheck(null)
      return
    }
    let live = true
    let spec: Record<string, unknown>
    try {
      spec = formToSpec(form)
    } catch (cause) {
      setCheck({ valid: false, error: cause instanceof Error ? cause.message : String(cause) })
      return
    }
    api
      .ruleValidate(spec)
      .then((result) => live && setCheck(result))
      .catch((cause: unknown) => live && setCheck({ valid: false, error: String(cause) }))
    return () => {
      live = false
    }
    // formKey captures every field the spec depends on
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formKey, hasRows])

  const idError = ruleIdError(form.id)
  const canSave = check?.valid === true && idError === null

  const save = () => {
    if (!canSave) return
    setError(null)
    api
      .ruleSave(form.id.trim(), formToSpec(form))
      .then((record) => {
        setSavedRecord(record)
        refresh()
      })
      .catch((cause: unknown) => setError(String(cause)))
  }

  const load = (name: string) => {
    setError(null)
    api
      .rule(name)
      .then((record) => {
        setForm(recordToForm(record))
        setSavedRecord(record)
      })
      .catch((cause: unknown) => setError(String(cause)))
  }

  const remove = (name: string) => {
    setError(null)
    api
      .ruleDelete(name)
      .then(() => {
        if (savedRecord?.name === name) setSavedRecord(null)
        refresh()
      })
      .catch((cause: unknown) => setError(String(cause)))
  }

  const savedIsCurrent = savedRecord !== null && savedRecord.name === form.id.trim()
  const testInSandbox = () => {
    if (!savedIsCurrent || !symbol.trim()) return
    setError(null)
    api
      .launch('backtest run', sandboxArgs(symbol, form.id, profile === 'crypto'), runContextForProject(null))
      .then((result) => setJobId(result.job_id))
      .catch((cause: unknown) => setError(String(cause)))
  }

  return (
    <div className="panel strategy-builder">
      <div className="panel-toolbar">
        <span className="title">Strategy Builder</span>
        <span className="muted">rules are state: be long / short while every row holds</span>
      </div>
      <div className="panel-body panel-pad builder-layout">
        <section className="builder-editor" aria-label="Rule editor">
          <div className="lab-row">
            <label className="field-row">
              <span className="field-label">File name</span>
              <input
                className="field mono"
                value={form.id}
                placeholder="trend-follow"
                spellCheck={false}
                aria-invalid={form.id.trim() !== '' && idError !== null}
                onChange={(event) => setForm({ ...form, id: event.target.value })}
              />
            </label>
            <label className="field-row">
              <span className="field-label">Display name</span>
              <input className="field" value={form.name} placeholder="Trend follower" onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label className="field-row" title="Bars every decision reads; blank = 4 × the longest indicator, at least 60">
              <span className="field-label">History (bars)</span>
              <input className="field mono" value={form.history} placeholder="auto" onChange={(event) => setForm({ ...form, history: event.target.value })} />
            </label>
          </div>
          {form.id.trim() && idError ? <p className="builder-error">{idError}</p> : null}
          <RowEditor side="longRows" rows={form.longRows} onChange={(rows) => setForm({ ...form, longRows: rows })} />
          <RowEditor side="shortRows" rows={form.shortRows} onChange={(rows) => setForm({ ...form, shortRows: rows })} />
          <p className="muted builder-help">
            Each side is <span className="mono">{OPERAND_EXAMPLES.join(' · ')}</span>. Indicators are the ones the chart
            draws; a value still warming up on the decision bar is an error, never a guess.
          </p>
          <div className="builder-check" role="status" aria-live="polite">
            {check === null ? (
              <span className="muted">add a condition to check the rule set</span>
            ) : check.valid ? (
              <span className="chip pass">
                valid · warm-up {'warmup' in check ? check.warmup : '—'} bars · history {'history' in check ? check.history : '—'}
              </span>
            ) : (
              <span className="chip fail">{check.error}</span>
            )}
          </div>
          <div className="builder-actions">
            <button type="button" className="btn primary" disabled={!canSave} onClick={save} title="alpha rules save">
              Save rule set
            </button>
            <label className="field-row builder-symbol">
              <span className="field-label">Test symbol</span>
              <input className="field mono" value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="BTC/USDT" />
            </label>
            <button
              type="button"
              className="btn"
              disabled={!savedIsCurrent || !symbol.trim()}
              title={
                savedIsCurrent
                  ? 'alpha backtest run --strategy rules in the standalone sandbox (permanently unqualified)'
                  : 'Save the rule set first'
              }
              onClick={testInSandbox}
            >
              Test in sandbox
            </button>
            <button
              type="button"
              className="btn"
              disabled={!savedIsCurrent}
              title="Open the Strategy Lab prefilled for a governed run under the linked project"
              onClick={() => openStrategyLab({ command: 'backtest run', args: `${symbol.trim()} --strategy rules --rules ${form.id.trim()}` })}
            >
              Open in Strategy Lab
            </button>
          </div>
          {error ? <p className="builder-error" role="alert">{error}</p> : null}
          {jobId ? <JobConsole jobId={jobId} onRun={openRunDetail} onDone={() => undefined} /> : null}
        </section>
        <aside className="builder-saved" aria-label="Saved rule sets">
          <h3>Saved rule sets</h3>
          {saved.length === 0 ? <p className="muted">none yet — save one to backtest it as strategy “rules”</p> : null}
          <ul className="builder-list">
            {saved.map((row) => (
              <li key={row.name} className={row.name === form.id.trim() ? 'active' : ''}>
                <button type="button" className="watch-select" onClick={() => load(row.name)} disabled={row.error !== null && row.error !== undefined}>
                  <span className="mono">{row.name}</span>
                  <span className="muted">{row.error ?? row.spec_name}</span>
                </button>
                <button type="button" className="btn" aria-label={`Delete rule set ${row.name}`} onClick={() => remove(row.name)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  )
}
