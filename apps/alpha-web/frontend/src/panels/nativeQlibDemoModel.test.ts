import { describe, expect, it } from 'vitest'
import result from '../../public/demos/native-qlib/result.json'
import { readNativeQlibDemo } from './nativeQlibDemoModel'

describe('recorded native Qlib display boundary', () => {
  it('reads the actual 128-score native artifact in chronological order', () => {
    const demo = readNativeQlibDemo(result)
    expect(demo.run_id).toBe('7169fb461ef2421690db00d910841f17')
    expect(demo.predictions).toHaveLength(128)
    expect(demo.diagnostics).toHaveLength(16)
    expect(demo.predictions[0].score).toBe(0.02044160203819095)
    expect(demo.predictions[0].session_ts.slice(0, 10)).toBe('2024-04-01')
    expect(demo.predictions.at(-1)?.session_ts.slice(0, 10)).toBe('2024-04-22')
  })
  it('refuses an unlabeled or admitted source', () => {
    expect(() => readNativeQlibDemo({ ...result, synthetic: false })).toThrow(/explicitly synthetic/)
    expect(() => readNativeQlibDemo({ ...result, admission: 'accepted' })).toThrow(/explicitly synthetic/)
  })
  it('refuses invalid, duplicate or disordered score records', () => {
    const invalid = structuredClone(result); invalid.predictions[0].score = NaN
    expect(() => readNativeQlibDemo(invalid)).toThrow()
    const duplicate = structuredClone(result); duplicate.predictions[1] = duplicate.predictions[0]
    expect(() => readNativeQlibDemo(duplicate)).toThrow()
    const reversed = structuredClone(result); reversed.predictions.reverse()
    expect(() => readNativeQlibDemo(reversed)).toThrow()
  })
})
