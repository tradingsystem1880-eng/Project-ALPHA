import { describe, expect, it } from 'vitest'
import result from '../../public/demos/native-nautilus/result.json'
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
