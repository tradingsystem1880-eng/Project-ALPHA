import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TradeRow } from '../api/types'
import { setLinked, useLinked } from '../context/linked'
import { Scanner } from './Scanner'
import { TradesTab } from './rundetail/TradesTab'
import { EdgeReview } from './EdgeReview'
import { Navigator } from './Navigator'
import type { ResultTab } from '../shell/edgeWorkspace'
import { PanelHost } from '../shell/PanelHost'

export function DeskResults({ tab }: { tab: ResultTab }) {
  const { runId } = useLinked()
  const [trades, setTrades] = useState<TradeRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true; setTrades(null); setError(null)
    if (runId && tab === 'Trades') api.trades(runId).then(value => { if (live) setTrades(value) }).catch(cause => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [runId, tab])
  if (tab === 'Scan results') return <PanelHost name="Scanner" component={Scanner} />
  if (tab === 'Results') return <EdgeReview />
  if (tab === 'Run library') return <Navigator onOpenRun={id => setLinked({ runId: id })} />
  return <section aria-label="Recorded trades">{!runId ? <p>Choose a recorded run in Run library.</p> : error ? <p role="alert">{error}</p> : trades ? <TradesTab trades={trades} runId={runId} /> : <p role="status">Loading trades…</p>}</section>
}
