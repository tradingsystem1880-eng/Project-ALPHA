// Pipeline — the strategy-development loop as a live surface: data → backtest → validate →
// optimize → portfolio → propfirm (forecast as a side lane), with per-stage run counts and,
// for the selected run, the explanation engine's next-step actions prefilled into the Lab.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { useLinked } from '../context/linked'
import { suggestions } from '../explain/suggestions'
import { optimSuggestions } from '../explain/optim'
import { portfolioSuggestions } from '../explain/portfolio'
import { propfirmSuggestions } from '../explain/propfirm'
import type {
  OptimManifest,
  PortfolioManifest,
  PropfirmManifest,
  Suggestion,
  ValidateManifest,
} from '../explain/types'
import { useActivity } from '../state/activity'
import { shortId } from '../util/format'
import { openRunDetail, openStrategyLab } from './actions'
import { SuggestionList } from './rundetail/common'

interface Stage {
  key: string
  title: string
  desc: string
  kinds: string[]
  launch: { command: string; args: string }
}

const STAGES: Stage[] = [
  {
    key: 'data',
    title: '1 · Data',
    desc: 'Pull + snapshot point-in-time history',
    kinds: [],
    launch: { command: 'data pull', args: 'SPY --source yfinance --start 2015-01-01' },
  },
  {
    key: 'backtest',
    title: '2 · Backtest',
    desc: 'One pass, fixed params — behavior, not proof',
    kinds: ['runs'],
    launch: { command: 'backtest run', args: 'SPY --strategy ts_momentum' },
  },
  {
    key: 'validate',
    title: '3 · Validate',
    desc: 'The gauntlet: 5 gates, A–F verdict',
    kinds: ['runs'],
    launch: { command: 'validate', args: 'SPY --strategy ts_momentum' },
  },
  {
    key: 'optim',
    title: '4 · Optimize',
    desc: 'Sweep params under overfitting controls',
    kinds: ['optim'],
    launch: { command: 'optim grid', args: 'SPY --strategy ts_momentum --grid lookback=126,189,252,315' },
  },
  {
    key: 'portfolio',
    title: '5 · Portfolio',
    desc: 'Diversify the edge across a basket',
    kinds: ['portfolio', 'cross_sectional'],
    launch: { command: 'backtest portfolio', args: 'SPY QQQ TLT GLD --strategy ts_momentum' },
  },
  {
    key: 'propfirm',
    title: '6 · Prop-firm MC',
    desc: 'Would it survive real drawdown rules?',
    kinds: ['propfirm'],
    launch: { command: 'propfirm run', args: '--firm topstep --from-run <run-id>' },
  },
]

export function Pipeline(props: IDockviewPanelProps) {
  const { runsVersion } = useActivity()
  const linked = useLinked()
  const [items, setItems] = useState<RunListItem[] | null>(null)
  const [sugg, setSugg] = useState<Suggestion[] | null>(null)

  useEffect(() => {
    let live = true
    api.runs('?limit=500').then((r) => live && setItems(r.items)).catch(() => {})
    return () => {
      live = false
    }
  }, [runsVersion])

  // suggestions for the linked (selected) run — the engine picks by kind
  useEffect(() => {
    if (!linked.runId) {
      setSugg(null)
      return
    }
    let live = true
    api
      .run(linked.runId)
      .then((d) => {
        if (!live) return
        const m = d.manifest
        if (d.kind === 'optim') setSugg(optimSuggestions(m as OptimManifest))
        else if (d.kind === 'portfolio' || d.kind === 'cross_sectional')
          setSugg(portfolioSuggestions(m as PortfolioManifest))
        else if (d.kind === 'propfirm') setSugg(propfirmSuggestions(m as PropfirmManifest))
        else setSugg(suggestions(m as ValidateManifest))
      })
      .catch(() => live && setSugg(null))
    return () => {
      live = false
    }
  }, [linked.runId])

  const counts = useMemo(() => {
    const all = items ?? []
    const bySym = linked.symbol
      ? all.filter((r) => r.symbol === linked.symbol || (r.symbols ?? []).includes(linked.symbol!))
      : all
    return { validate: 0, backtest: 0, ...Object.fromEntries(
      STAGES.map((s) => [s.key, bySym.filter((r) => s.kinds.includes(r.kind)).length]),
    ) }
  }, [items, linked.symbol])

  const latestFor = (stage: Stage): RunListItem | undefined =>
    (items ?? []).find(
      (r) =>
        stage.kinds.includes(r.kind) &&
        (!linked.symbol || r.symbol === linked.symbol || (r.symbols ?? []).includes(linked.symbol)),
    )

  const prefillArgs = (stage: Stage): string => {
    let args = stage.launch.args
    if (linked.symbol) args = args.replace(/^SPY(?=\s|$)/, linked.symbol).replace(/^SPY /, `${linked.symbol} `)
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
            return (
              <div className="pipe-stage" key={s.key}>
                <div className="pipe-head">
                  <span className="pipe-title">{s.title}</span>
                  {s.kinds.length ? (
                    <span className="count">{counts[s.key as keyof typeof counts] ?? 0}</span>
                  ) : null}
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
