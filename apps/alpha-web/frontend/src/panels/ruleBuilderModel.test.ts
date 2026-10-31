import { describe, expect, it } from 'vitest'

import type { RuleRecord } from '../api/types'
import {
  ARITY,
  EMPTY_FORM,
  OPERAND_EXAMPLES,
  draftToForm,
  formToSpec,
  operandText,
  parseOperandText,
  recordToForm,
  ruleIdError,
  sandboxArgs,
} from './ruleBuilderModel'

describe('operand text (the way the chart names things)', () => {
  it('parses sources, numbers and indicator specs with optional fields', () => {
    expect(parseOperandText(' Close ')).toEqual({ source: 'close' })
    expect(parseOperandText('30')).toEqual({ value: 30 })
    expect(parseOperandText('-1.5')).toEqual({ value: -1.5 })
    expect(parseOperandText('sma:20')).toEqual({ indicator: 'sma', params: [20] })
    expect(parseOperandText('bbands:20:2.5:lower')).toEqual({ indicator: 'bbands', params: [20, 2.5], field: 'lower' })
    expect(parseOperandText('macd:12:26:9:histogram')).toEqual({ indicator: 'macd', params: [12, 26, 9], field: 'histogram' })
    expect(parseOperandText('hawkes:0.1:168')).toEqual({ indicator: 'hawkes', params: [0.1, 168] })
    expect(parseOperandText('vg_path:12:inverse')).toEqual({ indicator: 'vg_path', params: [12], field: 'inverse' })
    expect(parseOperandText('perm_entropy:3:28')).toEqual({ indicator: 'perm_entropy', params: [3, 28] })
  })
  it('offers an example for every indicator head and every example parses', () => {
    const heads = OPERAND_EXAMPLES.map((text) => parseOperandText(text)).flatMap((operand) => ('indicator' in operand ? [operand.indicator] : []))
    expect(new Set(heads)).toEqual(new Set(Object.keys(ARITY)))
    for (const text of OPERAND_EXAMPLES) expect(operandText(parseOperandText(text))).toBe(text)
  })
  it('names the defect before anything reaches the CLI', () => {
    expect(() => parseOperandText('')).toThrow(/empty/)
    expect(() => parseOperandText('vwap:20')).toThrow(/"vwap" is not/)
    expect(() => parseOperandText('sma')).toThrow(/sma takes 1 parameter/)
    expect(() => parseOperandText('sma:abc')).toThrow(/must be numbers/)
    expect(() => parseOperandText('bbands:20:2')).toThrow(/needs a field/)
    expect(() => parseOperandText('macd:12:26:9:foo')).toThrow(/field must be one of/)
    expect(() => parseOperandText('vg_path:12')).toThrow(/needs a field: price, inverse/)
    expect(() => parseOperandText('cmma:24')).toThrow(/cmma takes 2 parameters/)
  })
  it('round-trips through operandText', () => {
    for (const text of ['close', '30', 'sma:20', 'bbands:20:2:lower', 'macd:12:26:9:signal']) {
      expect(operandText(parseOperandText(text))).toBe(text)
    }
  })
})

describe('source lag identity in saved and draft rules', () => {
  const spec = {
    name: 'Twenty-day momentum',
    history: 21,
    long_when: [{ left: { source: 'close' }, op: '>', right: { source: 'close', lag: 20 } }],
    short_when: [],
  }

  it('parses and displays bounded source lag, omitting canonical zero', () => {
    expect(parseOperandText(' Close:lag:20 ')).toEqual({ source: 'close', lag: 20 })
    expect(parseOperandText('high:lag:1999')).toEqual({ source: 'high', lag: 1999 })
    expect(parseOperandText('low:lag:0')).toEqual({ source: 'low' })
    expect(operandText({ source: 'close', lag: 20 })).toBe('close:lag:20')
    expect(operandText({ source: 'low', lag: 0 })).toBe('low')
  })

  it.each(['close:lag:-1', 'close:lag:2000', 'close:lag:1.5', 'close:lag:1.0',
    'close:lag:true', 'close:lag:', 'close:lag', 'close:20', 'close:lag:20:extra',
    'close:unknown:20'])('rejects malformed source text %s', (text) => {
    expect(() => parseOperandText(text)).toThrow(/lag/)
  })

  it('round-trips saved records and assistant drafts without changing the rule', () => {
    const record: RuleRecord = {
      name: 'momentum', spec_name: spec.name, sha256: 'abc', path: '/x/momentum.json',
      history: 21, warmup: 21, long_conditions: ['close > close:lag:20'], short_conditions: [],
      spec: { version: 1, ...spec },
    }
    const form = recordToForm(record)
    expect(form.history).toBe('21')
    expect(form.longRows).toEqual([{ left: 'close', op: '>', right: 'close:lag:20' }])
    expect(formToSpec(form)).toEqual(spec)
    expect(formToSpec(draftToForm({ version: 1, ...spec }))).toEqual(spec)
  })

  it.each([-1, 2000, 1.5, '20', true, null, undefined])(
    'refuses malformed saved source lag %s instead of erasing it', (lag) => {
      const malformed = { ...spec,
        long_when: [{ left: { source: 'close' }, op: '>', right: { source: 'close', lag } }] }
      expect(() => draftToForm(malformed)).toThrow(/lag/)
    },
  )

  it('refuses unknown saved source fields and lag on non-source operands', () => {
    for (const right of [{ source: 'close', lag: 20, future: true },
      { value: 1, lag: 20 }, { indicator: 'sma', params: [20], lag: 1 }]) {
      expect(() => draftToForm({ ...spec,
        long_when: [{ left: { source: 'close' }, op: '>', right }] })).toThrow()
    }
  })
})

describe('form <-> spec', () => {
  const record: RuleRecord = {
    name: 'trend',
    sha256: 'abc',
    path: '/x/trend.json',
    spec_name: 'Trend follower',
    history: 40,
    warmup: 20,
    long_conditions: ['sma:5 > sma:20'],
    short_conditions: ['sma:5 < sma:20'],
    spec: {
      version: 1,
      name: 'Trend follower',
      history: 40,
      long_when: [{ left: { indicator: 'sma', params: [5] }, op: '>', right: { indicator: 'sma', params: [20] } }],
      short_when: [{ left: { indicator: 'sma', params: [5] }, op: '<', right: { indicator: 'sma', params: [20] } }],
    },
  }
  it('validates with a placeholder spec name until the file name is typed', () => {
    expect(formToSpec({ ...EMPTY_FORM, longRows: [{ left: 'sma:5', op: '>', right: 'sma:20' }] }).name).toBe('unsaved')
  })
  it('builds the CLI spec from rows, skipping blank rows and defaulting history', () => {
    const spec = formToSpec({
      id: 'trend',
      name: '',
      history: '',
      longRows: [{ left: 'sma:5', op: '>', right: 'sma:20' }, { left: '', op: '>', right: '' }],
      shortRows: [],
    })
    expect(spec).toEqual({
      name: 'trend',
      long_when: [{ left: { indicator: 'sma', params: [5] }, op: '>', right: { indicator: 'sma', params: [20] } }],
      short_when: [],
    })
    expect(formToSpec({ ...EMPTY_FORM, id: 'x', history: '120', longRows: [{ left: 'rsi:14', op: '<', right: '30' }] })).toMatchObject({ history: 120 })
    expect(() => formToSpec({ ...EMPTY_FORM, id: 'x', longRows: [{ left: 'nope', op: '>', right: '1' }] })).toThrow(/not a source/)
  })
  it('loads a saved record back into rows', () => {
    expect(recordToForm(record)).toEqual({
      id: 'trend',
      name: 'Trend follower',
      history: '40',
      longRows: [{ left: 'sma:5', op: '>', right: 'sma:20' }],
      shortRows: [{ left: 'sma:5', op: '<', right: 'sma:20' }],
    })
    expect(formToSpec(recordToForm(record))).toEqual({
      name: 'Trend follower',
      history: 40,
      long_when: record.spec.long_when,
      short_when: record.spec.short_when,
    })
  })
  it('checks the file name and builds the sandbox command', () => {
    expect(ruleIdError('')).toMatch(/file name/)
    expect(ruleIdError('Bad Name')).toMatch(/lowercase/)
    expect(ruleIdError('trend-v2')).toBeNull()
    expect(sandboxArgs('BTC/USDT', 'trend', true)).toBe('BTC/USDT --strategy rules --rules trend --account-type MARGIN')
    expect(sandboxArgs('SPY', 'trend', false)).toBe('SPY --strategy rules --rules trend')
  })
})
