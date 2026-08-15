import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type {
  CryptoAcquisitionRequest,
  CryptoAssetIdentity,
  CryptoAssetMaster,
  CryptoAssetMasters,
  CryptoCatalog,
  CryptoCapabilities,
  CryptoCoverage,
  CryptoCoverageBatch,
  CryptoCoverageBatches,
  CryptoCoverageCadence,
  CryptoCoverageItem,
  CryptoCoverageProfilePage,
  CryptoCoverageProfiles,
  CryptoCoverageTask,
  CryptoEstimate,
  CryptoFamily,
  CryptoFeature,
  CryptoFeatureName,
  CryptoFeatures,
  CryptoLiquidityMembership,
  CryptoOneMinuteSelection,
  CryptoQuality,
  CryptoSnapshotCreate,
  CryptoSnapshotRegister,
  CryptoSnapshotVerify,
  CryptoStorage,
  CryptoStorageInventory,
  CryptoStorageVerify,
  CryptoCacheClean,
} from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { shortId } from '../util/format'
import { CryptoAssetsView } from './CryptoAssetsView'
import { CryptoCoverageView } from './CryptoCoverageView'
import { CryptoQualityView } from './CryptoQualityView'
import {
  cryptoCanonicalAction,
  cryptoCoverageStateClass,
  cryptoFeatureInputSelection,
  cryptoMarketChoicesForFamily,
  cryptoSectionForFamily,
  latestCryptoManifestIds,
  type CryptoDataSection,
} from './researchDataModel'

const SECTIONS: { id: CryptoDataSection; label: string }[] = [
  { id: 'assets', label: 'Assets & Contracts' },
  { id: 'cex', label: 'CEX History' },
  { id: 'derivatives', label: 'Derivatives & Funding' },
  { id: 'options', label: 'Options & Volatility' },
  { id: 'onchain', label: 'On-chain Metrics' },
  { id: 'dex', label: 'DEX Pools & Liquidity' },
  { id: 'quality', label: 'Coverage & Quality' },
  { id: 'storage', label: 'Storage & Jobs' },
]

const PROVIDERS = new Set(['binance', 'bybit', 'coingecko', 'geckoterminal', 'coinmetrics', 'ccxt:coinbase'])
const BYBIT_RANGED_FAMILIES = new Set<CryptoFamily>([
  'funding',
  'open_interest',
  'long_short_ratio',
  'derivative_bars',
  'mark_bars',
  'index_bars',
  'premium_bars',
  'historical_volatility',
])

const PROFILE_CADENCES: { id: CryptoCoverageCadence; label: string }[] = [
  { id: 'daily', label: 'Daily coverage' },
  { id: 'hourly', label: 'Hourly coverage' },
  { id: 'funding_interval', label: 'Native funding intervals' },
  { id: 'five_minute', label: 'Five-minute option tier' },
]

function previousUtcSession(): string {
  const value = new Date()
  value.setUTCDate(value.getUTCDate() - 1)
  return value.toISOString().slice(0, 10)
}

function acquisitionProvider(value: string): CryptoAcquisitionRequest['provider'] | null {
  if (PROVIDERS.has(value)) return value as CryptoAcquisitionRequest['provider']
  return null
}

function defaultInstrument(family: CryptoFamily): string {
  if (family === 'comparison_bars') return 'BTC/USD'
  if (family === 'instrument_catalog') return 'linear'
  if (family === 'asset_metadata') return 'all'
  if (family === 'market_reference') return 'bitcoin'
  if (family === 'onchain_catalog') return 'community'
  if (family === 'onchain_metrics') return 'btc'
  if (family.startsWith('option_') || family === 'historical_volatility') return 'BTC'
  return 'BTCUSDT'
}

function bytesLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unit = 0
  while (size >= 1000 && unit < units.length - 1) {
    size /= 1000
    unit += 1
  }
  return `${size.toFixed(unit < 2 ? 0 : 1)} ${units[unit]}`
}

export function CryptoDataCenter({
  projectId,
  caseRevision,
  onRegistered,
}: {
  projectId: string | null
  caseRevision: string | null
  onRegistered?: () => void
}) {
  const [section, setSection] = useState<CryptoDataSection>('derivatives')
  const [catalog, setCatalog] = useState<CryptoCatalog | null>(null)
  const [capabilities, setCapabilities] = useState<CryptoCapabilities | null>(null)
  const [storage, setStorage] = useState<CryptoStorage | null>(null)
  const [coverage, setCoverage] = useState<CryptoCoverage | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [family, setFamily] = useState<CryptoFamily>('funding')
  const [instrument, setInstrument] = useState('BTCUSDT')
  const [base, setBase] = useState('BTC')
  const [quote, setQuote] = useState('USDT')
  const [category, setCategory] = useState<CryptoAcquisitionRequest['category']>('linear')
  const [frequency, setFrequency] = useState<CryptoAcquisitionRequest['frequency']>('1h')
  const [period, setPeriod] = useState('2026-07')
  const [network, setNetwork] = useState('eth')
  const [poolAddress, setPoolAddress] = useState('')
  const [metrics, setMetrics] = useState('AdrActCnt,TxCnt,FeeTotNtv')
  const [eventReason, setEventReason] = useState('Capture this bounded derivative event for the selected research case.')
  const [start, setStart] = useState('2025-01-01T00:00:00Z')
  const [end, setEnd] = useState('2026-01-01T00:00:00Z')
  const [days, setDays] = useState(30)
  const [estimate, setEstimate] = useState<CryptoEstimate | null>(null)
  const [asset, setAsset] = useState<CryptoAssetIdentity | null>(null)
  const [assetMasters, setAssetMasters] = useState<CryptoAssetMasters | null>(null)
  const [assetMaster, setAssetMaster] = useState<CryptoAssetMaster | null>(null)
  const [assetMasterVersion, setAssetMasterVersion] = useState('reviewed-native-v1')
  const [contractNetwork, setContractNetwork] = useState('ethereum')
  const [contractAddress, setContractAddress] = useState('')
  const [quality, setQuality] = useState<CryptoQuality | null>(null)
  const [features, setFeatures] = useState<CryptoFeatures | null>(null)
  const [featureName, setFeatureName] = useState<CryptoFeatureName>('funding')
  const [createdFeature, setCreatedFeature] = useState<CryptoFeature | null>(null)
  const [profiles, setProfiles] = useState<CryptoCoverageProfiles | null>(null)
  const [activeProfileId, setActiveProfileId] = useState<string>('')
  const activeProfileRef = useRef('')
  const [profilePage, setProfilePage] = useState<CryptoCoverageProfilePage | null>(null)
  const [profileCadence, setProfileCadence] = useState<CryptoCoverageCadence>('daily')
  const [profileOffset, setProfileOffset] = useState(0)
  const [batches, setBatches] = useState<CryptoCoverageBatches | null>(null)
  const [oneMinuteTasks, setOneMinuteTasks] = useState<CryptoCoverageTask[]>([])
  const [oneMinuteNextOffset, setOneMinuteNextOffset] = useState<number | null>(null)
  const [oneMinuteMarkets, setOneMinuteMarkets] = useState<Set<string>>(() => new Set())
  const [oneMinuteReason, setOneMinuteReason] = useState('Inspect these bounded one-minute markets for the current research case.')
  const [oneMinuteSelection, setOneMinuteSelection] = useState<CryptoOneMinuteSelection | null>(null)
  const [liquidityCategory, setLiquidityCategory] = useState<'spot' | 'linear' | 'inverse'>('spot')
  const [liquidityQuote, setLiquidityQuote] = useState<'USD' | 'USDT'>('USDT')
  const [liquiditySession, setLiquiditySession] = useState(previousUtcSession)
  const [liquidityMembership, setLiquidityMembership] = useState<CryptoLiquidityMembership | null>(null)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobKind, setJobKind] = useState<'acquisition' | 'profile'>('acquisition')
  const [jobFinished, setJobFinished] = useState(false)
  const [snapshot, setSnapshot] = useState<CryptoSnapshotCreate | null>(null)
  const [verification, setVerification] = useState<CryptoSnapshotVerify | null>(null)
  const [registration, setRegistration] = useState<CryptoSnapshotRegister | null>(null)
  const [storageInventory, setStorageInventory] = useState<CryptoStorageInventory | null>(null)
  const [storageVerification, setStorageVerification] = useState<CryptoStorageVerify | null>(null)
  const [cacheResult, setCacheResult] = useState<CryptoCacheClean | null>(null)
  const [cleanupArmed, setCleanupArmed] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true)
    else setLoading(true)
    try {
      const [nextCatalog, nextCapabilities, nextAssetMasters, nextStorage, nextCoverage, nextFeatures, nextProfiles, nextBatches] = await Promise.all([
        api.cryptoCatalog(),
        api.cryptoCapabilities(),
        api.cryptoAssetMasters(),
        api.cryptoStorage(),
        api.cryptoCoverage(),
        api.cryptoFeatures(),
        api.cryptoProfiles(),
        api.cryptoBatches(),
      ])
      setCatalog(nextCatalog)
      setCapabilities(nextCapabilities)
      setAssetMasters(nextAssetMasters)
      setAssetMasterVersion((current) => {
        if (nextAssetMasters.items.some((item) => item.asset_master_version === current)) {
          return current
        }
        return nextAssetMasters.items.find((item) => item.contract_identity_count > 0)
          ?.asset_master_version ?? 'reviewed-native-v1'
      })
      setStorage(nextStorage)
      setCoverage(nextCoverage)
      setFeatures(nextFeatures)
      setProfiles(nextProfiles)
      setBatches(nextBatches)
      setActiveProfileId((current) => {
        if (nextProfiles.items.some((item) => item.profile_id === current)) return current
        return [...nextProfiles.items].sort((left, right) => right.as_of.localeCompare(left.as_of))[0]
          ?.profile_id ?? ''
      })
      setSelected((current) => {
        const admitted = new Set(
          nextCoverage.items
            .filter((item) => item.state === 'qualified')
            .map((item) => item.manifest_id),
        )
        return new Set([...current].filter((id) => admitted.has(id)))
      })
      setError(null)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    activeProfileRef.current = activeProfileId
  }, [activeProfileId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!activeProfileId) {
      setProfilePage(null)
      setOneMinuteTasks([])
      setOneMinuteNextOffset(null)
      return
    }
    let cancelled = false
    void Promise.all([
      api.cryptoProfile(activeProfileId, {
        cadence: profileCadence,
        offset: profileOffset,
        limit: 25,
      }),
      api.cryptoProfile(activeProfileId, {
        provider: 'binance',
        family: 'market_bars',
        frequency: '1d',
        offset: 0,
        limit: 100,
      }),
    ]).then(([nextPage, markets]) => {
      if (cancelled) return
      setProfilePage(nextPage)
      setOneMinuteTasks(markets.items)
      setOneMinuteNextOffset(markets.next_offset)
      setOneMinuteMarkets(new Set())
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason))
    })
    return () => { cancelled = true }
  }, [activeProfileId, profileCadence, profileOffset])

  const familyRows = useMemo(
    () => (catalog?.families ?? []).filter((row) => {
      const provider = acquisitionProvider(row.provider)
      return provider !== null && cryptoSectionForFamily(row.family) === section
    }),
    [catalog, section],
  )

  useEffect(() => {
    if (familyRows.length === 0 || familyRows.some((row) => row.family === family)) return
    const next = familyRows[0].family
    setFamily(next)
    setInstrument(defaultInstrument(next))
  }, [family, familyRows])

  useEffect(() => {
    setEstimate(null)
    setSnapshot(null)
    setVerification(null)
    setRegistration(null)
  }, [family, instrument, base, quote, category, frequency, days])

  useEffect(() => {
    if (family === 'comparison_bars') {
      if (category !== 'spot') setCategory('spot')
      if (frequency !== '1d') setFrequency('1d')
      if (base !== 'BTC') setBase('BTC')
      if (quote !== 'USD') setQuote('USD')
      if (instrument !== 'BTC/USD') setInstrument('BTC/USD')
      return
    }
    const marketChoices = cryptoMarketChoicesForFamily(family)
    if (!marketChoices.includes(category)) setCategory(marketChoices[0])
    if (
      !['open_interest', 'long_short_ratio'].includes(family)
      && ['15m', '30m', '4h'].includes(frequency)
    ) setFrequency('1h')
  }, [base, category, family, frequency, instrument, quote])

  useEffect(() => {
    if (!BYBIT_RANGED_FAMILIES.has(family)) return
    const recentEnd = new Date(Date.now() - 60 * 60 * 1000)
    recentEnd.setUTCMinutes(0, 0, 0)
    const recentStart = new Date(recentEnd.getTime() - 7 * 24 * 60 * 60 * 1000)
    setStart(recentStart.toISOString())
    setEnd(recentEnd.toISOString())
  }, [family])

  const provider = acquisitionProvider(
    catalog?.families.find((row) => row.family === family)?.provider ?? '',
  )
  const capability = capabilities?.items.find((item) => item.family === family) ?? null
  const categoryChoices: CryptoAcquisitionRequest['category'][] =
    cryptoMarketChoicesForFamily(family)
  const frequencyChoices: CryptoAcquisitionRequest['frequency'][] =
    family === 'open_interest' || family === 'long_short_ratio'
      ? ['5m', '15m', '30m', '1h', '4h', '1d']
      : ['1m', '5m', '1h', '1d']
  const qualifiedCount = coverage?.items.filter((item) => item.state === 'qualified').length ?? 0
  const caseBoundEvent = family === 'derivative_trades' || family === 'derivative_book_snapshots'
  const eventCaptureReady = !caseBoundEvent || Boolean(projectId && caseRevision && eventReason.trim())
  const action = cryptoCanonicalAction({
    loading,
    storageState: storage?.state,
    storageBlocker: storage?.blocker,
    qualifiedCount,
    selectedCount: selected.size,
  })
  const visibleCoverage = (coverage?.items ?? []).filter((item) => {
    if (section === 'quality' || section === 'storage') return true
    return cryptoSectionForFamily(item.family) === section
  })
  const latestManifestIds = latestCryptoManifestIds(visibleCoverage)
  const selectedBaseAssets = new Set(
    (coverage?.items ?? [])
      .filter((item) => selected.has(item.manifest_id) && item.base_asset)
      .map((item) => item.base_asset as string),
  )
  const activeProfile = profiles?.items.find((item) => item.profile_id === activeProfileId) ?? null
  const failedBatches = (batches?.items ?? []).filter((item) => item.state === 'failed')
  const featureInputSelection = useMemo(
    () => cryptoFeatureInputSelection(featureName, coverage?.items ?? [], selected),
    [coverage, featureName, selected],
  )

  async function deriveFeature(): Promise<void> {
    if (featureInputSelection.blocker) return
    setBusyAction('feature')
    setError(null)
    try {
      const created = await api.cryptoFeatureCreate({
        feature_name: featureName,
        inputs: featureInputSelection.inputs,
      })
      setCreatedFeature(created)
      setFeatures(await api.cryptoFeatures())
    } catch (reason: unknown) {
      setCreatedFeature(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function estimateAcquisition(): Promise<void> {
    setBusyAction('estimate')
    setError(null)
    try {
      setEstimate(await api.cryptoEstimate({ family, instruments: 1, days, frequency }))
    } catch (reason: unknown) {
      setEstimate(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectAsset(): Promise<void> {
    setBusyAction('asset')
    setError(null)
    try {
      setAsset(await api.cryptoAsset(base, new Date().toISOString()))
    } catch (reason: unknown) {
      setAsset(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectContractAsset(): Promise<void> {
    if (!contractAddress || assetMasterVersion === 'reviewed-native-v1') return
    setBusyAction('asset-contract')
    setError(null)
    try {
      setAsset(await api.cryptoAssetContract(
        contractNetwork,
        contractAddress,
        assetMasterVersion,
        new Date().toISOString(),
      ))
    } catch (reason: unknown) {
      setAsset(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function freezeAssetMaster(): Promise<void> {
    const latestFor = (target: CryptoFamily): CryptoCoverageItem[] => {
      const candidates = (coverage?.items ?? []).filter(
        (item) => item.family === target
          && item.state === 'qualified'
          && (target !== 'asset_metadata' || item.instrument === 'all'),
      )
      const latest = latestCryptoManifestIds(candidates)
      return candidates.filter((item) => latest.has(item.manifest_id))
    }
    const [coingecko] = latestFor('asset_metadata')
    const geckoterminal = latestFor('dex_pools')
    if (!coingecko || geckoterminal.length === 0) {
      setError('Acquire qualified CoinGecko asset metadata and a GeckoTerminal pool catalog first.')
      return
    }
    setBusyAction('asset-master')
    setError(null)
    try {
      const created = await api.cryptoAssetMasterCreate(
        coingecko.manifest_id,
        geckoterminal.map((item) => item.manifest_id),
      )
      setAssetMaster(created)
      setAssetMasterVersion(created.asset_master_version)
      await load(true)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function verifyAssetMaster(): Promise<void> {
    if (assetMasterVersion === 'reviewed-native-v1') return
    setBusyAction('asset-master-verify')
    setError(null)
    try {
      setAssetMaster(await api.cryptoAssetMasterVerify(assetMasterVersion))
    } catch (reason: unknown) {
      setAssetMaster(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function acquire(): Promise<void> {
    if (!provider) return
    setBusyAction('acquire')
    setError(null)
    try {
      const request: CryptoAcquisitionRequest = {
        provider,
        family,
        instrument,
        base,
        quote,
        category,
        frequency,
        period: provider === 'binance' && family !== 'book_snapshots' ? period : null,
        network: provider === 'geckoterminal' ? network : null,
        pool_address: provider === 'geckoterminal' && poolAddress ? poolAddress : null,
        metrics: provider === 'coinmetrics' && family === 'onchain_metrics'
          ? metrics.split(',').map((item) => item.trim()).filter(Boolean)
          : [],
        start: (provider === 'coinmetrics' && family === 'onchain_metrics') || provider === 'ccxt:coinbase' || (provider === 'bybit' && BYBIT_RANGED_FAMILIES.has(family)) ? start : null,
        end: (provider === 'coinmetrics' && family === 'onchain_metrics') || provider === 'ccxt:coinbase' || (provider === 'bybit' && BYBIT_RANGED_FAMILIES.has(family)) ? end : null,
        case_id: caseBoundEvent ? projectId : null,
        expected_case_revision: caseBoundEvent ? caseRevision : null,
        reason: caseBoundEvent ? eventReason.trim() : null,
      }
      const accepted = await api.cryptoAcquire(request)
      setJobId(accepted.job_id)
      setJobKind('acquisition')
      setJobFinished(false)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function freezeSnapshot(): Promise<void> {
    setBusyAction('snapshot')
    setError(null)
    try {
      const created = await api.cryptoSnapshotCreate([...selected], assetMasterVersion)
      setSnapshot(created)
      setVerification(null)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function verifySnapshot(): Promise<void> {
    if (!snapshot) return
    setBusyAction('verify')
    setError(null)
    try {
      setVerification(await api.cryptoSnapshotVerify(snapshot.snapshot_id, {
        required_families: snapshot.families,
        purpose: 'research',
      }))
    } catch (reason: unknown) {
      setVerification(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function registerSnapshot(): Promise<void> {
    if (!snapshot || !verification?.eligible || selectedBaseAssets.size !== 1) return
    setBusyAction('register')
    setError(null)
    try {
      setRegistration(
        await api.cryptoSnapshotRegister(snapshot.snapshot_id, [...selectedBaseAssets][0]),
      )
      onRegistered?.()
    } catch (reason: unknown) {
      setRegistration(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectQuality(item: CryptoCoverageItem): Promise<void> {
    setBusyAction(`quality:${item.manifest_id}`)
    setError(null)
    try {
      setQuality(await api.cryptoQuality(item.manifest_id))
      setSection('quality')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function createProfile(): Promise<void> {
    setBusyAction('profile-create')
    setError(null)
    try {
      const created = await api.cryptoProfileCreate()
      setActiveProfileId(created.profile_id)
      setProfileOffset(0)
      await load(true)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function runProfileBatch(): Promise<void> {
    if (!activeProfileId || !profilePage || profilePage.items.length === 0) return
    setBusyAction('profile-run')
    setError(null)
    try {
      const accepted = await api.cryptoProfileRun(
        activeProfileId,
        profileCadence,
        profileOffset,
        Math.min(25, profilePage.items.length),
      )
      setJobId(accepted.job_id)
      setJobKind('profile')
      setJobFinished(false)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function resumeProfileBatch(batch: CryptoCoverageBatch): Promise<void> {
    if (batch.state !== 'failed') return
    setBusyAction(`batch:${batch.batch_id}`)
    setError(null)
    try {
      const accepted = await api.cryptoBatchResume(batch.batch_id)
      setJobId(accepted.job_id)
      setJobKind('profile')
      setJobFinished(false)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function freezeLiquidityMembership(): Promise<void> {
    if (!activeProfileId) return
    setBusyAction('liquidity-freeze')
    setError(null)
    try {
      setLiquidityMembership(await api.cryptoLiquidityFreeze(activeProfileId, {
        category: liquidityCategory,
        quote_asset: liquidityQuote,
        session: liquiditySession,
        limit: 250,
      }))
    } catch (reason: unknown) {
      setLiquidityMembership(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function loadMoreOneMinuteMarkets(): Promise<void> {
    if (!activeProfileId || oneMinuteNextOffset === null) return
    setBusyAction('one-minute-more')
    setError(null)
    try {
      const page = await api.cryptoProfile(activeProfileId, {
        provider: 'binance',
        family: 'market_bars',
        frequency: '1d',
        offset: oneMinuteNextOffset,
        limit: 100,
      })
      if (page.profile_id !== activeProfileRef.current) return
      setOneMinuteTasks((current) => [...current, ...page.items])
      setOneMinuteNextOffset(page.next_offset)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  function toggleOneMinuteMarket(task: CryptoCoverageTask): void {
    if (!task.category) return
    const market = `${task.category}:${task.instrument}`
    setOneMinuteMarkets((current) => {
      const next = new Set(current)
      if (next.has(market)) next.delete(market)
      else if (next.size < 50) next.add(market)
      return next
    })
    setOneMinuteSelection(null)
  }

  async function freezeOneMinuteSelection(): Promise<void> {
    if (!activeProfileId || !projectId || !caseRevision || oneMinuteMarkets.size === 0) return
    setBusyAction('one-minute-select')
    setError(null)
    try {
      const created = await api.cryptoOneMinuteSelection(activeProfileId, {
        case_id: projectId,
        expected_case_revision: caseRevision,
        markets: [...oneMinuteMarkets],
        reason: oneMinuteReason.trim(),
      })
      setOneMinuteSelection(created)
      setActiveProfileId(created.profile_id)
      await load(true)
    } catch (reason: unknown) {
      setOneMinuteSelection(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectStorage(): Promise<void> {
    setBusyAction('storage-inventory')
    setError(null)
    try {
      setStorageInventory(await api.cryptoStorageInventory())
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function verifyStorage(): Promise<void> {
    setBusyAction('storage-verify')
    setError(null)
    try {
      setStorageVerification(await api.cryptoStorageVerify())
    } catch (reason: unknown) {
      setStorageVerification(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function cleanCache(): Promise<void> {
    if (!cleanupArmed) {
      setCleanupArmed(true)
      return
    }
    setBusyAction('cache-clean')
    setError(null)
    try {
      setCacheResult(await api.cryptoCacheClean())
      setCleanupArmed(false)
      await load(true)
      await inspectStorage()
    } catch (reason: unknown) {
      setCacheResult(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  function toggleManifest(item: CryptoCoverageItem): void {
    if (item.state !== 'qualified') return
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(item.manifest_id)) next.delete(item.manifest_id)
      else next.add(item.manifest_id)
      return next
    })
    setSnapshot(null)
    setVerification(null)
  }

  return (
    <section className="crypto-center" aria-label="Crypto Data Center">
      <div className="crypto-center-head">
        <div>
          <div className="title">Crypto Data Center</div>
          <p className="muted">Provider-native public data · exact units · no automatic fallback · no execution authority</p>
        </div>
        <button className="btn" type="button" disabled={refreshing} onClick={() => void load(true)}>
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className={`crypto-next ${action.state}`} role="status">
        <span className="eyebrow">Canonical next action</span>
        <strong>{action.label}</strong>
      </div>
      {error ? <div className="workbench-notice" role="alert"><strong>ACTION BLOCKED</strong><span>{error}</span></div> : null}

      <nav className="crypto-tabs" role="tablist" aria-label="Crypto data families">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={section === item.id}
            className={`area-tab${section === item.id ? ' active' : ''}`}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <CryptoAssetsView
        show={section === 'assets'}
        base={base}
        asset={asset}
        assetMasters={assetMasters}
        assetMaster={assetMaster}
        assetMasterVersion={assetMasterVersion}
        contractNetwork={contractNetwork}
        contractAddress={contractAddress}
        busyAction={busyAction}
        onBaseChange={(value) => {
          setBase(value)
          setAsset(null)
        }}
        onInspectAsset={() => void inspectAsset()}
        onAssetMasterVersionChange={(value) => {
          setAssetMasterVersion(value)
          setAsset(null)
          setAssetMaster(null)
          setSnapshot(null)
          setVerification(null)
        }}
        onFreezeAssetMaster={() => void freezeAssetMaster()}
        onVerifyAssetMaster={() => void verifyAssetMaster()}
        onContractNetworkChange={(value) => {
          setContractNetwork(value)
          setAsset(null)
        }}
        onContractAddressChange={(value) => {
          setContractAddress(value)
          setAsset(null)
        }}
        onInspectContractAsset={() => void inspectContractAsset()}
      />

      {familyRows.length > 0 ? (
        <section className="crypto-acquire provider-card" aria-label="Bounded acquisition">
          <div className="provider-card-head">
            <div className="rd-head">Bounded acquisition</div>
            <span className="chip kind">{provider ?? 'NO AUTHORITY'}</span>
          </div>
          {capability ? (
            <div className="crypto-detail" aria-label="Provider dataset capability">
              <span>
                <span className="chip kind">SUPPORTED</span>{' '}
                <span className={capability.verification_state === 'receipt_verified' ? 'chip pass' : 'chip'}>
                  {capability.verification_state === 'receipt_verified' ? 'RECEIPT VERIFIED' : 'NOT VERIFIED'}
                </span>{' '}
                <span className={cryptoCoverageStateClass(capability.qualification_state)}>
                  {capability.qualification_state.toUpperCase()}
                </span>
              </span>
              <span>
                Stored coverage: {capability.earliest ?? 'none'} → {capability.latest ?? 'none'}
              </span>
              <span className="advanced-only">Supported frequencies: {capability.frequencies.join(' · ')}</span>
              <span className="advanced-only">Limits: {capability.limits.join(' · ')}</span>
            </div>
          ) : null}
          <div className="crypto-form-grid">
            <label><span className="eyebrow">Dataset family</span><select className="field" value={family} onChange={(event) => { const next = event.target.value as CryptoFamily; setFamily(next); setInstrument(defaultInstrument(next)) }}>{familyRows.map((row) => <option key={row.family} value={row.family}>{row.family.replaceAll('_', ' ')}</option>)}</select></label>
            <label><span className="eyebrow">Instrument</span><input className="field mono" value={instrument} onChange={(event) => setInstrument(event.target.value)} /></label>
            <label><span className="eyebrow">Base asset</span><input className="field mono" value={base} onChange={(event) => setBase(event.target.value.toUpperCase())} /></label>
            <label><span className="eyebrow">Quote asset</span><input className="field mono" value={quote} onChange={(event) => setQuote(event.target.value.toUpperCase())} /></label>
            <label><span className="eyebrow">Market</span><select className="field" value={category} onChange={(event) => setCategory(event.target.value as CryptoAcquisitionRequest['category'])}>{categoryChoices.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            <label><span className="eyebrow">Frequency</span><select className="field" value={frequency} onChange={(event) => setFrequency(event.target.value as CryptoAcquisitionRequest['frequency'])}>{frequencyChoices.map((item) => <option key={item} value={item}>{item === '1d' ? 'daily' : item === '1h' ? 'hourly' : item}</option>)}</select></label>
            <label><span className="eyebrow">Estimate days</span><input className="field" type="number" min={1} max={3650} value={days} onChange={(event) => setDays(Number(event.target.value))} /></label>
            {provider === 'binance' ? <label><span className="eyebrow">Archive month</span><input className="field mono" type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label> : null}
            {provider === 'geckoterminal' ? <><label><span className="eyebrow">Network</span><input className="field mono" value={network} onChange={(event) => setNetwork(event.target.value)} /></label><label><span className="eyebrow">Pool address</span><input className="field mono" value={poolAddress} onChange={(event) => setPoolAddress(event.target.value)} /></label></> : null}
            {provider === 'coinmetrics' && family === 'onchain_metrics' ? <label><span className="eyebrow">Metrics</span><input className="field mono" value={metrics} onChange={(event) => setMetrics(event.target.value)} /></label> : null}
            {(provider === 'coinmetrics' && family === 'onchain_metrics') || provider === 'ccxt:coinbase' || (provider === 'bybit' && BYBIT_RANGED_FAMILIES.has(family)) ? <><label><span className="eyebrow">Start UTC</span><input className="field mono" value={start} onChange={(event) => setStart(event.target.value)} /></label><label><span className="eyebrow">End UTC</span><input className="field mono" value={end} onChange={(event) => setEnd(event.target.value)} /></label></> : null}
            {caseBoundEvent ? <label><span className="eyebrow">Event-capture reason</span><input className="field" value={eventReason} onChange={(event) => setEventReason(event.target.value)} /></label> : null}
          </div>
          <div className="crypto-actions">
            <button className="btn" type="button" disabled={busyAction !== null} onClick={() => void estimateAcquisition()}>{busyAction === 'estimate' ? 'Estimating…' : 'Estimate storage'}</button>
            <button className="btn primary" type="button" disabled={storage?.state !== 'ready' || !provider || busyAction !== null || !eventCaptureReady} onClick={() => void acquire()}>{busyAction === 'acquire' ? 'Starting…' : 'Acquire & qualify'}</button>
            {estimate ? <span className="muted">{estimate.estimated_rows.toLocaleString()} rows · about {bytesLabel(estimate.estimated_bytes)}</span> : null}
          </div>
          {caseBoundEvent && !eventCaptureReady ? <div className="workbench-notice" role="note"><strong>SELECT A RESEARCH CASE</strong><span>Derivative trades and books must be bound to the current case revision before any provider request.</span></div> : null}
          <p className="mono muted advanced-only">alpha crypto-data acquire {provider} {family} {instrument} --base {base} --quote {quote} …</p>
        </section>
      ) : null}

      {jobId ? <section className="crypto-job"><div className="rd-head">{jobKind === 'profile' ? 'Coverage batch job' : 'Acquisition job'}</div><div className="workbench-notice" role="status"><strong>{jobFinished ? 'FINISHED' : 'RUNNING'}</strong><span>{jobFinished ? 'Coverage refreshed. Review the new mechanical qualification below.' : jobKind === 'profile' ? 'Running at most 25 exact tasks from the frozen profile with an atomic checkpoint after each task.' : 'Fetching one bounded provider response and freezing its exact bytes.'}</span></div><div className="advanced-only"><JobConsole jobId={jobId} onDone={() => { setJobFinished(true); void load(true) }} /></div></section> : null}

      <CryptoCoverageView
        section={section}
        loading={loading}
        items={visibleCoverage}
        latestManifestIds={latestManifestIds}
        selectedManifestIds={selected}
        busyAction={busyAction}
        onToggle={toggleManifest}
        onInspectQuality={(item) => void inspectQuality(item)}
      />

      <CryptoQualityView
        quality={quality}
        showFeatures={section === 'quality'}
        features={features}
        featureName={featureName}
        featureInputSelection={featureInputSelection}
        createdFeature={createdFeature}
        busyAction={busyAction}
        onFeatureNameChange={(name) => {
          setFeatureName(name)
          setCreatedFeature(null)
        }}
        onDeriveFeature={() => void deriveFeature()}
      />

      <section className="crypto-snapshot provider-card" aria-label="Frozen crypto snapshot">
        <div className="provider-card-head"><div className="rd-head">Research snapshot</div><span className="chip kind">{selected.size} selected</span></div>
        <p className="muted">Only mechanically qualified datasets can be selected. Provider, venue, quote, units, timestamps, and hashes remain separate.</p>
        <p className="muted">Identity map: {(assetMasters?.items.find((item) => item.asset_master_version === assetMasterVersion)?.builtin ?? true) ? 'reviewed native assets' : 'exact contract identity map'}<span className="advanced-only mono"> · {assetMasterVersion}</span></p>
        <div className="crypto-actions">
          <button className="btn primary" type="button" disabled={selected.size === 0 || busyAction !== null} onClick={() => void freezeSnapshot()}>{busyAction === 'snapshot' ? 'Freezing…' : 'Freeze selected snapshot'}</button>
          {snapshot ? <button className="btn" type="button" disabled={busyAction !== null} onClick={() => void verifySnapshot()}>{busyAction === 'verify' ? 'Verifying…' : 'Verify for research'}</button> : null}
        </div>
        {snapshot ? <div className="crypto-detail"><strong>Frozen · {snapshot.member_count} members</strong><span>{snapshot.families.map((item) => item.replaceAll('_', ' ')).join(' · ')}</span><span className="mono muted advanced-only">snapshot {snapshot.snapshot_id}</span></div> : null}
        {verification ? <div className={`workbench-notice ${verification.eligible ? '' : 'fail'}`} role="status"><strong>{verification.eligible ? 'ELIGIBLE' : 'BLOCKED'}</strong><span>{verification.eligible ? 'Register this immutable snapshot for compatible research proposals.' : `${verification.next_action}${verification.blockers.length ? ` ${verification.blockers.join('; ')}` : ''}`}</span></div> : null}
        {verification?.eligible ? <div className="crypto-actions"><button className="btn primary" type="button" disabled={busyAction !== null || selectedBaseAssets.size !== 1 || registration !== null} onClick={() => void registerSnapshot()}>{busyAction === 'register' ? 'Registering…' : registration ? 'Registered for research' : 'Register research-only dataset'}</button>{selectedBaseAssets.size !== 1 ? <span className="muted">Select datasets for exactly one base asset before registration.</span> : null}</div> : null}
        {registration ? <div className="workbench-notice" role="status"><strong>REGISTERED · RESEARCH ONLY</strong><span>Available to compatible proposal operators; registration does not make an incompatible case executable.</span><span className="mono muted advanced-only">{registration.ref_id}</span></div> : null}
      </section>

      {section === 'storage' && storage ? (
        <>
        <section className="provider-card" aria-label="Default crypto coverage profile">
          <div className="provider-card-head">
            <div className="rd-head">Default coverage profile</div>
            <span className="chip kind">{activeProfile?.task_count.toLocaleString() ?? 0} tasks</span>
          </div>
          <p className="muted">A profile freezes point-in-time provider catalogs into bounded acquisition tasks. It is scheduling provenance only—never research evidence or execution authority.</p>
          <div className="crypto-form-grid">
            <label>
              <span className="eyebrow">Frozen profile</span>
              <select
                className="field"
                value={activeProfileId}
                onChange={(event) => {
                  setActiveProfileId(event.target.value)
                  setProfileOffset(0)
                  setLiquidityMembership(null)
                  setOneMinuteSelection(null)
                }}
              >
                {(profiles?.items ?? []).map((item) => (
                  <option key={item.profile_id} value={item.profile_id}>
                    {new Date(item.as_of).toLocaleString()} · {item.task_count.toLocaleString()} tasks
                  </option>
                ))}
              </select>
            </label>
            <button className="btn" type="button" disabled={busyAction !== null} onClick={() => void createProfile()}>
              {busyAction === 'profile-create' ? 'Freezing catalogs…' : 'Freeze fresh profile'}
            </button>
          </div>
          {activeProfile ? (
            <div className="crypto-detail">
              <span>{Object.entries(activeProfile.counts_by_provider).map(([name, count]) => `${name} ${count.toLocaleString()}`).join(' · ')}</span>
              <span>{Object.entries(activeProfile.counts_by_cadence).map(([name, count]) => `${name.replaceAll('_', ' ')} ${count.toLocaleString()}`).join(' · ')}</span>
              <span className="mono muted advanced-only">profile {activeProfile.profile_id} · {activeProfile.source_manifest_ids.length} exact catalog inputs</span>
            </div>
          ) : <div className="workbench-notice" role="note"><strong>NO FROZEN PROFILE</strong><span>Acquire and qualify the required Bybit catalogs, option chains, and Binance membership catalogs, then freeze a profile.</span></div>}
          {activeProfile ? (
            <>
              <div className="crypto-form-grid">
                <label><span className="eyebrow">Cadence</span><select className="field" value={profileCadence} onChange={(event) => { setProfileCadence(event.target.value as CryptoCoverageCadence); setProfileOffset(0) }}>{PROFILE_CADENCES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
                <label><span className="eyebrow">Page</span><input className="field" readOnly value={`${profileOffset + 1}–${profileOffset + (profilePage?.items.length ?? 0)} of ${profilePage?.filtered_count.toLocaleString() ?? '…'}`} /></label>
                <button className="btn" type="button" disabled={profileOffset === 0 || busyAction !== null} onClick={() => setProfileOffset(Math.max(0, profileOffset - 25))}>Previous 25</button>
                <button className="btn" type="button" disabled={!profilePage?.has_more || busyAction !== null} onClick={() => setProfileOffset(profilePage?.next_offset ?? profileOffset)}>Next 25</button>
                <button className="btn primary" type="button" disabled={!profilePage?.items.length || busyAction !== null} onClick={() => void runProfileBatch()}>{busyAction === 'profile-run' ? 'Starting…' : `Run these ${profilePage?.items.length ?? 0} tasks`}</button>
              </div>
              <p className="muted">{profilePage?.next_action ?? 'Loading this exact cadence page…'} Provider requests begin only after this explicit click.</p>
              <div className="crypto-coverage-list">
                {(profilePage?.items ?? []).map((task) => (
                  <article className="crypto-dataset" key={task.task_id}>
                    <span><strong>{task.instrument}</strong><span className="muted">{task.family.replaceAll('_', ' ')} · {task.provider} · {task.category ?? 'reference'} · {task.frequency}</span></span>
                    <span className="chip">PLANNED</span>
                    <span className="mono muted advanced-only">task {shortId(task.task_id)}</span>
                  </article>
                ))}
              </div>
            </>
          ) : null}
          {failedBatches.length ? (
            <div className="crypto-detail">
              <strong>{failedBatches.length} failed bounded batch{failedBatches.length === 1 ? '' : 'es'}</strong>
              {failedBatches.map((batch) => <div key={batch.batch_id} className="crypto-detail"><span><strong>{batch.error ?? 'Provider or data blocker'}</strong><span className="muted">{batch.recovery_action ?? 'Resolve the blocker, then resume.'}</span></span><button className="btn" type="button" disabled={busyAction !== null} onClick={() => void resumeProfileBatch(batch)}>{busyAction === `batch:${batch.batch_id}` ? 'Resuming…' : `Resume ${batch.cadence.replaceAll('_', ' ')} batch (${batch.completed_count}/${batch.task_count})`}</button></div>)}
            </div>
          ) : null}
        </section>

        {activeProfile ? (
          <section className="crypto-card-grid" aria-label="Higher-resolution crypto coverage">
            <article className="provider-card">
              <div className="rd-head">Causal hourly liquidity scope</div>
              <p className="muted">After every market in one exact prior-day scope is qualified, freeze the top 250 without mixing quote assets or contract units.</p>
              <div className="crypto-form-grid">
                <label><span className="eyebrow">Market</span><select className="field" value={liquidityCategory} onChange={(event) => { const next = event.target.value as 'spot' | 'linear' | 'inverse'; setLiquidityCategory(next); setLiquidityQuote(next === 'inverse' ? 'USD' : 'USDT'); setLiquidityMembership(null) }}><option value="spot">Spot</option><option value="linear">USD-M perpetual</option><option value="inverse">COIN-M perpetual</option></select></label>
                <label><span className="eyebrow">Quote</span><input className="field mono" readOnly value={liquidityQuote} /></label>
                <label><span className="eyebrow">Complete UTC session</span><input className="field mono" type="date" value={liquiditySession} onChange={(event) => { setLiquiditySession(event.target.value); setLiquidityMembership(null) }} /></label>
                <button className="btn primary" type="button" disabled={busyAction !== null || !liquiditySession} onClick={() => void freezeLiquidityMembership()}>{busyAction === 'liquidity-freeze' ? 'Re-verifying scope…' : 'Freeze top-liquidity membership'}</button>
              </div>
              {liquidityMembership ? <div className="workbench-notice" role="status"><strong>FROZEN · {liquidityMembership.selected_count} OF {liquidityMembership.universe_count}</strong><span>Create a fresh profile to admit this exact hourly membership.</span><span className="mono muted advanced-only">manifest {liquidityMembership.manifest_id}</span></div> : null}
            </article>

            <article className="provider-card">
              <div className="rd-head">Case-bound one-minute markets</div>
              <p className="muted">Select up to 50 markets from the frozen daily membership. This only schedules the previous complete hour and is bound to the current research-case revision.</p>
              <label><span className="eyebrow">Research purpose</span><input className="field" value={oneMinuteReason} onChange={(event) => { setOneMinuteReason(event.target.value); setOneMinuteSelection(null) }} /></label>
              {!projectId || !caseRevision ? <div className="workbench-notice" role="note"><strong>SELECT A RESEARCH CASE</strong><span>A current case and revision are required before one-minute membership can be frozen.</span></div> : null}
              <div className="crypto-market-picker">
                {oneMinuteTasks.map((task) => {
                  const market = `${task.category}:${task.instrument}`
                  return <label key={task.task_id}><input type="checkbox" checked={oneMinuteMarkets.has(market)} disabled={!task.category || (!oneMinuteMarkets.has(market) && oneMinuteMarkets.size >= 50)} onChange={() => toggleOneMinuteMarket(task)} /><span><strong>{task.instrument}</strong><small>{task.category} · {task.base_asset}/{task.quote_asset}</small></span></label>
                })}
              </div>
              <div className="crypto-actions">
                {oneMinuteNextOffset !== null ? <button className="btn" type="button" disabled={busyAction !== null} onClick={() => void loadMoreOneMinuteMarkets()}>{busyAction === 'one-minute-more' ? 'Loading…' : 'Load 100 more markets'}</button> : null}
                <button className="btn primary" type="button" disabled={busyAction !== null || !projectId || !caseRevision || oneMinuteMarkets.size === 0 || !oneMinuteReason.trim()} onClick={() => void freezeOneMinuteSelection()}>{busyAction === 'one-minute-select' ? 'Freezing…' : `Freeze ${oneMinuteMarkets.size} selected market${oneMinuteMarkets.size === 1 ? '' : 's'}`}</button>
              </div>
              {oneMinuteSelection ? <div className="workbench-notice" role="status"><strong>CASE-BOUND · {oneMinuteSelection.selected_count} MARKETS</strong><span>New profile frozen for the previous complete hour; no research or execution authority was granted.</span><span className="mono muted advanced-only">selection {oneMinuteSelection.selection_manifest_id}</span></div> : null}
            </article>
          </section>
        ) : null}

        <section className="provider-card">
          <div className="rd-head">Expansion storage</div>
          <div className="crypto-storage-stats"><span className={storage.state === 'ready' ? 'chip pass' : 'chip fail'}>{storage.state.toUpperCase()}</span><span>{bytesLabel(storage.free_bytes)} free of {bytesLabel(storage.total_bytes)}</span><span>{storage.manifest_count} immutable manifests</span><span>{bytesLabel(storage.cache_bytes)} removable cache</span><span>Reserve {storage.reserve_fraction == null ? '—' : `${Math.round(storage.reserve_fraction * 100)}%`} · minimum {bytesLabel(storage.minimum_free_bytes)}</span></div>
          <p className="muted">The browser receives only the volume label and capacity—not the private absolute path. Missing or substituted media fails closed.</p>
          <div className="crypto-actions"><button className="btn" type="button" disabled={busyAction !== null} onClick={() => void inspectStorage()}>{busyAction === 'storage-inventory' ? 'Inspecting…' : 'Inspect storage inventory'}</button><button className="btn" type="button" disabled={busyAction !== null} onClick={() => void verifyStorage()}>{busyAction === 'storage-verify' ? 'Verifying every artifact…' : 'Verify all immutable data'}</button><button className={cleanupArmed ? 'btn danger' : 'btn'} type="button" disabled={busyAction !== null || storage.cache_bytes === 0} onClick={() => void cleanCache()}>{busyAction === 'cache-clean' ? 'Cleaning cache…' : cleanupArmed ? 'Confirm clean removable cache' : 'Review cache cleanup'}</button></div>
          {cleanupArmed ? <div className="workbench-notice fail" role="alert"><strong>CONFIRM CACHE CLEANUP</strong><span>Only {bytesLabel(storage.cache_bytes)} under the disposable cache tree will be deleted. Raw, normalized, staged, snapshot, and control artifacts are excluded.</span></div> : null}
          {storageInventory ? <div className="crypto-detail"><strong>INVENTORY</strong><span>{storageInventory.manifest_count} manifests · {storageInventory.snapshot_count} snapshots · {storageInventory.staging_count} staged downloads</span><span>{bytesLabel(storageInventory.cache_bytes)} removable cache</span><span className="mono muted advanced-only">{JSON.stringify(storageInventory.counts_by_kind)}</span></div> : null}
          {storageVerification ? <div className="workbench-notice" role="status"><strong>VERIFIED</strong><span>{storageVerification.manifest_count} manifests and {storageVerification.snapshot_count} snapshots re-hashed · {storageVerification.research_eligible_snapshot_count} research eligible</span></div> : null}
          {cacheResult ? <div className="workbench-notice" role="status"><strong>CACHE CLEANED</strong><span>{bytesLabel(cacheResult.removed_bytes)} removed · immutable artifacts removed: 0</span></div> : null}
        </section>
        </>
      ) : null}
    </section>
  )
}
