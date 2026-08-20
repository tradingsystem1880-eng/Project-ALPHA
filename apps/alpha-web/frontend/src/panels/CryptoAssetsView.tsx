import type {
  CryptoAssetIdentity,
  CryptoAssetMaster,
  CryptoAssetMasters,
} from '../api/types'

type CryptoAssetsViewProps = {
  show: boolean
  base: string
  asset: CryptoAssetIdentity | null
  assetMasters: CryptoAssetMasters | null
  assetMaster: CryptoAssetMaster | null
  assetMasterVersion: string
  contractNetwork: string
  contractAddress: string
  busyAction: string | null
  onBaseChange: (value: string) => void
  onInspectAsset: () => void
  onAssetMasterVersionChange: (value: string) => void
  onFreezeAssetMaster: () => void
  onVerifyAssetMaster: () => void
  onContractNetworkChange: (value: string) => void
  onContractAddressChange: (value: string) => void
  onInspectContractAsset: () => void
}

export function CryptoAssetsView({
  show,
  base,
  asset,
  assetMasters,
  assetMaster,
  assetMasterVersion,
  contractNetwork,
  contractAddress,
  busyAction,
  onBaseChange,
  onInspectAsset,
  onAssetMasterVersionChange,
  onFreezeAssetMaster,
  onVerifyAssetMaster,
  onContractNetworkChange,
  onContractAddressChange,
  onInspectContractAsset,
}: CryptoAssetsViewProps) {
  if (!show) return null

  return (
    <div className="crypto-card-grid">
      <section className="provider-card">
        <div className="rd-head">Reviewed native identity</div>
        <div className="crypto-form-grid">
          <label><span className="eyebrow">Asset</span><input className="field mono" value={base} onChange={(event) => onBaseChange(event.target.value.toUpperCase())} /></label>
          <button className="btn" type="button" disabled={busyAction === 'asset'} onClick={onInspectAsset}>{busyAction === 'asset' ? 'Checking…' : 'Inspect lineage'}</button>
        </div>
        {asset ? (
          <div className="crypto-detail">
            <strong>{asset.coingecko_id}</strong>
            <span>{asset.network} · {asset.native_asset ? 'reviewed native asset' : 'contract asset'}</span>
            <span className="mono advanced-only">{asset.provider_symbols.map(([key, value]) => `${key}:${value}`).join(' · ')}</span>
          </div>
        ) : <p className="muted">Ticker-only contract joins are prohibited. Native BTC and ETH use reviewed mappings.</p>}
      </section>
      <section className="provider-card" aria-label="Frozen asset master">
        <div className="rd-head">Exact contract identity map</div>
        <p className="muted">Contract assets are joined only when CoinGecko and GeckoTerminal agree on the exact network and contract address.</p>
        <div className="crypto-form-grid">
          <label>
            <span className="eyebrow">Identity map</span>
            <select
              className="field"
              value={assetMasterVersion}
              onChange={(event) => onAssetMasterVersionChange(event.target.value)}
            >
              {(assetMasters?.items ?? []).map((item) => (
                <option key={item.asset_master_version} value={item.asset_master_version}>
                  {item.builtin
                    ? 'Reviewed native assets (BTC and ETH)'
                    : `${item.contract_identity_count} contract mappings · ${item.identity_count} total assets`}
                </option>
              ))}
            </select>
          </label>
          <button className="btn" type="button" disabled={busyAction !== null} onClick={onFreezeAssetMaster}>
            {busyAction === 'asset-master' ? 'Building…' : 'Build from latest qualified catalogs'}
          </button>
          {assetMasterVersion !== 'reviewed-native-v1' ? (
            <button className="btn" type="button" disabled={busyAction !== null} onClick={onVerifyAssetMaster}>
              {busyAction === 'asset-master-verify' ? 'Verifying…' : 'Verify identity map'}
            </button>
          ) : null}
        </div>
        {assetMaster ? (
          <div className="crypto-detail" role="status">
            <strong>{assetMaster.state.toUpperCase()} · {assetMaster.contract_identity_count} contract mappings</strong>
            <span>Ticker-only joins: prohibited</span>
            <span className="mono muted advanced-only">asset master {assetMaster.asset_master_version}</span>
          </div>
        ) : null}
        <div className="crypto-form-grid">
          <label><span className="eyebrow">Network</span><input className="field mono" value={contractNetwork} onChange={(event) => onContractNetworkChange(event.target.value)} /></label>
          <label><span className="eyebrow">Contract address</span><input className="field mono" value={contractAddress} onChange={(event) => onContractAddressChange(event.target.value)} placeholder="Exact contract address" /></label>
          <button
            className="btn primary"
            type="button"
            disabled={busyAction !== null || !contractAddress || assetMasterVersion === 'reviewed-native-v1'}
            onClick={onInspectContractAsset}
          >
            {busyAction === 'asset-contract' ? 'Resolving…' : 'Resolve exact contract'}
          </button>
        </div>
        {assetMasterVersion === 'reviewed-native-v1' ? <p className="muted">Acquire qualified CoinGecko asset metadata and a GeckoTerminal pool catalog, then build a contract identity map.</p> : null}
      </section>
    </div>
  )
}
