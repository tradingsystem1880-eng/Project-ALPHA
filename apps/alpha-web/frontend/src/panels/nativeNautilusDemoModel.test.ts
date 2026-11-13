import { describe, expect, it } from 'vitest'
import result from '../../public/demos/native-nautilus/result.json'
import pipeline from '../../public/demos/native-qlib-nautilus/result.json'
import { readNativeNautilusDemo } from './nativeNautilusDemoModel'

describe('saved native Nautilus result', () => {
  it('retains every native event, including distinct balances at equal UTC timestamps', () => {
    const data = readNativeNautilusDemo(result)
    expect(data.orders).toHaveLength(30); expect(data.fills).toHaveLength(30); expect(data.positions).toHaveLength(15)
    expect(data.balances).toHaveLength(31)
    expect(data.balances[2].timestamp).toBe(data.balances[3].timestamp)
    expect(data.balances[2].account_balance).toBe(1000014.08)
    expect(data.balances[3].account_balance).toBe(1000013.97)
    expect(data.balances.at(-1)?.account_balance).toBe(1000234.2)
  })
  it('rejects admission and equity relabeling', () => {
    expect(() => readNativeNautilusDemo({ ...result, admission: 'accepted' })).toThrow()
    expect(() => readNativeNautilusDemo({ ...result, synthetic: false })).toThrow()
    expect(() => readNativeNautilusDemo({ ...result, balance_kind: 'equity' })).toThrow()
  })
  it('rejects reordered, collapsed or nonfinite native events', () => {
    const reorder = structuredClone(result); reorder.balances.reverse()
    expect(() => readNativeNautilusDemo(reorder)).toThrow()
    const collapsed = structuredClone(result); collapsed.balances.splice(3, 1)
    expect(() => readNativeNautilusDemo(collapsed)).toThrow()
    const invalid = structuredClone(result); invalid.balances[0].account_balance = NaN
    expect(() => readNativeNautilusDemo(invalid)).toThrow()
  })
})

describe('joined native Qlib to Nautilus recording', () => {
  it('requires the explicit joined mode and preserves native event counts', () => {
    const data = readNativeNautilusDemo(pipeline, true)
    expect(data.fills).toHaveLength(10); expect(data.positions).toHaveLength(5)
    expect(data.balances).toHaveLength(27)
    expect(data.pipeline?.links).toHaveLength(16)
    expect(data.pipeline?.predictions_total).toBe(128)
    expect(() => readNativeNautilusDemo(pipeline)).toThrow()
    expect(() => readNativeNautilusDemo(result, true)).toThrow()
  })
  it('rejects broken score, clock, instrument or source-row links', () => {
    const future = structuredClone(pipeline)
    future.pipeline.links[0].available_at = future.pipeline.links[0].executable_at
    expect(() => readNativeNautilusDemo(future, true)).toThrow()
    const instrument = structuredClone(pipeline); instrument.pipeline.links[0].instrument_id = 'BTCUSD.SIM'
    expect(() => readNativeNautilusDemo(instrument, true)).toThrow()
    const missing = structuredClone(pipeline); missing.pipeline.links.pop()
    expect(() => readNativeNautilusDemo(missing, true)).toThrow()
    const signal = structuredClone(pipeline); signal.pipeline.links[0].signal = 1 - signal.pipeline.links[0].signal
    expect(() => readNativeNautilusDemo(signal, true)).toThrow()
  })
  it('rejects fills before availability or excess position size', () => {
    const early = structuredClone(pipeline); early.fills[0].timestamp = pipeline.pipeline.links[0].available_at
    expect(() => readNativeNautilusDemo(early, true)).toThrow()
    const size = structuredClone(pipeline); size.fills[0].quantity = '2'
    expect(() => readNativeNautilusDemo(size, true)).toThrow()
  })
  it('rejects a consistently shifted but late execution schedule', () => {
    const late = structuredClone(pipeline)
    const shift = (value: string) => new Date(Date.parse(value) + 86_400_000).toISOString()
    late.pipeline.links.forEach(row => { row.executable_at = shift(row.executable_at) })
    late.fills.forEach(row => { row.timestamp = shift(row.timestamp) })
    late.orders.forEach(row => { row.timestamp = shift(row.timestamp) })
    expect(() => readNativeNautilusDemo(late, true)).toThrow()
  })
  it('rejects repeated BUY fills inconsistent with a long-flat target transition', () => {
    const repeat = structuredClone(pipeline)
    const sell = repeat.fills.find(row => row.side === 'SELL')!
    sell.side = 'BUY'
    repeat.orders.find(row => row.id === sell.order_id)!.side = 'BUY'
    expect(() => readNativeNautilusDemo(repeat, true)).toThrow()
  })
})
