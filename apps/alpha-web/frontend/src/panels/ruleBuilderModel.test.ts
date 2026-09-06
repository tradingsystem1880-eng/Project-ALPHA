import { describe, expect, it } from 'vitest'

import type { RuleRecord } from '../api/types'
import {
  EMPTY_FORM,
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
  })
  it('names the defect before anything reaches the CLI', () => {
    expect(() => parseOperandText('')).toThrow(/empty/)
    expect(() => parseOperandText('vwap:20')).toThrow(/"vwap" is not/)
    expect(() => parseOperandText('sma')).toThrow(/sma takes 1 parameter/)
    expect(() => parseOperandText('sma:abc')).toThrow(/must be numbers/)
    expect(() => parseOperandText('bbands:20:2')).toThrow(/needs a field/)
    expect(() => parseOperandText('macd:12:26:9:foo')).toThrow(/field must be one of/)
  })
  it('round-trips through operandText', () => {
    for (const text of ['close', '30', 'sma:20', 'bbands:20:2:lower', 'macd:12:26:9:signal']) {
      expect(operandText(parseOperandText(text))).toBe(text)
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
