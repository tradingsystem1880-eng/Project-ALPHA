// The shared histogram bin model — one binning implementation for every distribution chart
// (null distributions, prop-firm outcomes). Rendering stays per-chart; the math does not.

export interface HistogramModel {
  lo: number
  hi: number
  bins: number[]
  max: number
  n: number
  binWidth: number
}

/** Fixed-bin counts over the finite values; `include` extends the range (e.g. the observed
 *  statistic must be inside the axis), `padFrac` adds symmetric range padding. */
export function binValues(
  values: number[],
  nBins: number,
  { include = [], padFrac = 0 }: { include?: number[]; padFrac?: number } = {},
): HistogramModel | null {
  const finite = values.filter((v) => Number.isFinite(v))
  if (!finite.length) return null
  let lo = Math.min(...finite)
  let hi = Math.max(...finite)
  for (const v of include)
    if (Number.isFinite(v)) {
      lo = Math.min(lo, v)
      hi = Math.max(hi, v)
    }
  const span = hi - lo || 1
  lo -= span * padFrac
  hi += span * padFrac
  const binWidth = (hi - lo) / nBins || 1
  const bins = new Array<number>(nBins).fill(0)
  for (const v of finite) bins[Math.min(nBins - 1, Math.max(0, Math.floor((v - lo) / binWidth)))] += 1
  return { lo, hi, bins, max: Math.max(...bins), n: finite.length, binWidth }
}
