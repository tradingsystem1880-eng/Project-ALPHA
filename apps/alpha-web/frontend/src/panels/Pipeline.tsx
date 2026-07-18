// Pipeline — the strategy-development loop as a live surface: data → backtest → validate →
// optimize → portfolio → propfirm (forecast as a side lane), with per-stage run counts and,
// for the selected run, the explanation engine's next-step actions prefilled into the Lab.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { useLinked } from '../context/linked'
import { suggestionsFor } from '../explain/dispatch'
import type { Suggestion } from '../explain/types'
import { useActivityField } from '../state/activity'
import { shortId } from '../util/format'
import { openRunDetail, openStrategyLab } from './actions'
import { SuggestionList } from './rundetail/common'

interface Stage {
  key: string
  title: string
  desc: string
  /** Which stored runs belong to this stage (a run-dir kind is too coarse: backtest and
   *  validate both live under runs/ and split on the manifest command). */
  match: (r: RunListItem) => boolean
  launch: { command: string; args: string }
}

const never = () => false

const STAGES: Stage[] = [
  {
    key: 'data',
    title: '1 · Data',
    desc: 'Pull + snapshot point-in-time history',
    match: never,
    launch: { command: 'data pull', args: 'SPY --source yfinance --start 2015-01-01' },
  },
  {
    key: 'backtest',
    title: '2 · Backtest',
    desc: 'One pass, fixed params — behavior, not proof',
    match: (r) => r.kind === 'runs' && r.command === 'backtest_run',
    launch: { command: 'backtest run', args: 'SPY --strategy ts_momentum' },
  },
  {
    key: 'validate',
    title: '3 · Validate',
    desc: 'The gauntlet: 5 gates, A–F verdict',
    // gauntlet manifests carry no command key — the verdict is their signature
    match: (r) => r.kind === 'runs' && r.command !== 'backtest_run',
    launch: { command: 'validate', args: 'SPY --strategy ts_momentum' },
  },
  {
    key: 'optim',
    title: '4 · Optimize',
    desc: 'Sweep params under overfitting controls',
    match: (r) => r.kind === 'optim',
    launch: { command: 'optim grid', args: 'SPY --strategy ts_momentum --grid lookback=126,189,252,315' },
  },
  {
    key: 'portfolio',
    title: '5 · Portfolio',
    desc: 'Diversify the edge across a basket',
    match: (r) => r.kind === 'portfolio' || r.kind === 'cross_sectional',
    launch: { command: 'backtest portfolio', args: 'SPY QQQ TLT GLD --strategy ts_momentum' },
  },
  {
    key: 'propfirm',
    title: '6 · Prop-firm MC',
    desc: 'Would it survive real drawdown rules?',
    match: (r) => r.kind === 'propfirm',
    launch: { command: 'propfirm run', args: '--firm topstep --from-run <run-id>' },
  },
]

export function Pipeline(props: IDockviewPanelProps) {
  const runsVersion = useActivityField('runsVersion')
  const linked = useLinked()
  const [items, setItems] = useState<RunListItem[] | null>(null)
  const [sugg, setSugg] = useState<Suggestion[] | null>(null)

  useEffect(() => {
    let live = true
    // small debounce: bursts of store events collapse into one refetch
    const t = window.setTimeout(() => {
      api.runs('?limit=500').then((r) => live && setItems(r.items)).catch(() => {})
    }, 150)
    return () => {
      live = false
      window.clearTimeout(t)
    }
  }, [runsVersion])

  // suggestions for the linked (selected) run — one shared kind dispatch (explain/dispatch)
  useEffect(() => {
    if (!linked.runId) {
      setSugg(null)
      return
    }
    let live = true
    api
      .run(linked.runId)
      .then((d) => live && setSugg(suggestionsFor(d.kind, d.manifest)))
      .catch(() => live && setSugg(null))
    return () => {
      live = false
    }
  }, [linked.runId])

  const forSymbol = useMemo(() => {
    const all = items ?? []
    return linked.symbol
      ? all.filter((r) => r.symbol === linked.symbol || (r.symbols ?? []).includes(linked.symbol!))
      : all
  }, [items, linked.symbol])

  const latestFor = (stage: Stage): RunListItem | undefined => forSymbol.find(stage.match)

  const prefillArgs = (stage: Stage): string => {
    let args = stage.launch.args
    if (linked.symbol) args = args.replace(/^SPY(?=\s|$)/, linked.symbol)
    if (linked.runId) args = args.replace('<run-id>', linked.runId)
    return args
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Pipeline</span>
        <span className="muted">
          the loop{linked.symbol ? ` · ${linked.symbol}` : ''} — every stage raises the bar before
          capital
        </span>
      </div>
      <div className="panel-body panel-pad">
        <div className="pipeline">
          {STAGES.map((s, i) => {
            const latest = latestFor(s)
            const count = forSymbol.filter(s.match).length
            return (
              <div className="pipe-stage" key={s.key}>
                <div className="pipe-head">
                  <span className="pipe-title">{s.title}</span>
                  {s.match !== never ? <span className="count">{count}</span> : null}
                </div>
                <p className="pipe-desc">{s.desc}</p>
                {latest ? (
                  <button
                    className="pipe-latest mono"
                    onClick={() => openRunDetail(props.containerApi, latest.run_id)}
                  >
                    {shortId(latest.run_id)}
                    {latest.verdict ? (
                      <span className={`verdict g-${latest.verdict}`}>{latest.verdict}</span>
                    ) : latest.passed !== null ? (
                      <span className={`chip ${latest.passed ? 'pass' : 'fail'}`}>
                        {latest.passed ? 'PASS' : 'FAIL'}
                      </span>
                    ) : null}
                  </button>
                ) : null}
                <button
                  className="btn"
                  onClick={() =>
                    openStrategyLab(props.containerApi, {
                      command: s.launch.command,
                      args: prefillArgs(s),
                    })
                  }
                >
                  ▶ prep
                </button>
                {i < STAGES.length - 1 ? <span className="pipe-arrow">→</span> : null}
              </div>
            )
          })}
        </div>

        {sugg && sugg.length ? (
          <div className="pipe-suggestions">
            <div className="rd-head">Next steps for {shortId(linked.runId ?? '')}</div>
            <SuggestionList
              items={sugg}
              onLaunch={(command, args) => openStrategyLab(props.containerApi, { command, args })}
            />
          </div>
        ) : linked.runId ? null : (
          <Placeholder>
            Select a run (Run Browser or Activity) to see rule-based next steps for it here.
          </Placeholder>
        )}
      </div>
    </div>
  )
}
