// Data Manager, Quality tab under the Equities profile: the stored stock and ETF bars, how many,
// how new, and a plain note on crypto-data storage. A display of stored bars; nothing is fetched.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { CryptoStorage, MarketAsset } from '../api/types'
import { CopyCommand } from '../components/CopyCommand'
import { Placeholder } from '../components/Placeholder'
import { setLinked } from '../context/linked'
import { useAreaVersion } from '../state/activity'
import { storageNote, storedRows } from './dataManagerModel'

export function StorageNote({ storage }: { storage: CryptoStorage | null }) {
  const note = storageNote(storage)
  if (!note) return null
  return (
    <div className={note.tone === 'blocked' ? 'leak' : 'muted storage-note'} role={note.tone === 'blocked' ? 'alert' : 'note'}>
      <p>{note.text}</p>
      {note.command ? <CopyCommand command={note.command} why="Run it from the project folder. Nothing runs from this screen." /> : null}
    </div>
  )
}

export function EquitiesDataView() {
  const version = useAreaVersion('bars')
  const [assets, setAssets] = useState<MarketAsset[] | null>(null)
  const [storage, setStorage] = useState<CryptoStorage | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setError(null)
    api.marketOverview('1D', 30, 30)
      .then((overview) => live && setAssets(overview.assets))
      .catch((cause: unknown) => live && setError(String(cause)))
    api.cryptoStorage().then((value) => live && setStorage(value)).catch(() => live && setStorage(null))
    return () => { live = false }
  }, [version])
  const rows = assets ? storedRows(assets, new Date().toISOString().slice(0, 10)) : null
  return (
    <section className="panel-pad equities-data" aria-label="Stored equity bars">
      <div className="rd-head">Stored stock and ETF bars (daily; first 30 symbols)</div>
      {error ? <div className="leak" role="alert">{error}</div> : null}
      {rows === null && !error ? <Placeholder>Loading stored bars…</Placeholder> : null}
      {rows && rows.length === 0 ? <p className="muted">No daily bars are stored yet. Use the Pull tab to add some.</p> : null}
      {rows && rows.length ? (
        <div className="table-scroll" tabIndex={0}>
          <table className="blotter">
            <caption className="sr-only">Stored daily bars by symbol</caption>
            <thead><tr><th>symbol</th><th className="r">bars</th><th>newest bar</th><th>health</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.symbol}>
                  <td><button className="sym-chip" onClick={() => setLinked({ symbol: row.symbol })}>{row.symbol}</button></td>
                  <td className="r">{row.bars.toLocaleString('en-US')}</td>
                  <td className="mono">{row.newest}</td>
                  <td>{row.health}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <StorageNote storage={storage} />
    </section>
  )
}
