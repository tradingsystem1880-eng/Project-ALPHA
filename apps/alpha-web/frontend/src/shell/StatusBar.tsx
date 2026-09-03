// Status bar (spec 2026-09-01 §4.2 item 8). Every segment is a relay: providers from the
// registry, the Expansion SSD from the storage projection, the hovered bar from the chart, the
// clock from the browser's UTC time. Nothing here is derived authority.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { CryptoStorage, ProviderDefinition } from '../api/types'
import { useChartHover } from '../context/chartHover'
import { useNow } from '../context/clock'
import { storageRow } from '../panels/dataManagerModel'
import { useSettings } from '../state/settings'
import { statusSegments } from './statusBarModel'

export function StatusBar() {
  const { profile } = useSettings()
  const hover = useChartHover()
  const [providers, setProviders] = useState<ProviderDefinition[]>([])
  const [storage, setStorage] = useState<CryptoStorage | null>(null)
  const now = useNow()

  useEffect(() => {
    let live = true
    api
      .providers()
      .then((list) => live && setProviders(list))
      .catch(() => live && setProviders([]))
    api
      .cryptoStorage()
      .then((status) => live && setStorage(status))
      .catch(() => live && setStorage(null))
    return () => {
      live = false
    }
  }, [])

  const segments = statusSegments({
    profile,
    providers: providers.map((item) => ({ id: item.id, configured: item.configured })),
    storage: storageRow(storage),
    now,
    hovered: hover.bar,
    barsLoaded: hover.barsLoaded,
  })

  return (
    <footer className="statusbar" aria-label="Status bar">
      {segments.map((segment) => (
        <span
          key={segment.id}
          className={`status-segment status-segment--${segment.id} tone-${segment.tone}`}
          title={segment.title}
        >
          {segment.text}
        </span>
      ))}
    </footer>
  )
}
