// Strategy Builder (spec 2026-09-01 §4.2 Phase 5 S4): the no-code editor for the owner's rule
// strategies. A rule row is `left  op  right` where each side is typed the way the chart names
// things — `close`, `sma:20`, `bbands:20:2:lower`, `macd:12:26:9:histogram`, or a number — and
// the rows become the strict JSON `alpha rules save` validates. This module only maps rows <->
// spec JSON and builds the sandbox test command; every judgement (grammar defects, warm-up,
// evaluation) stays in Python.

import type { RuleRecord } from '../api/types'

export const OPS = ['>', '<', '>=', '<='] as const
export type Op = (typeof OPS)[number]

export const SOURCES = ['high', 'low', 'close'] as const
const ARITY: Readonly<Record<string, number>> = Object.freeze({ sma: 1, ema: 1, bbands: 2, rsi: 1, atr: 1, macd: 3 })
const FIELDS: Readonly<Record<string, readonly string[]>> = Object.freeze({
  bbands: ['upper', 'middle', 'lower'],
  macd: ['line', 'signal', 'histogram'],
})

export const OPERAND_EXAMPLES: readonly string[] = Object.freeze([
  'close',
  'sma:20',
  'ema:50',
  'rsi:14',
  'atr:14',
  'bbands:20:2:lower',
  'macd:12:26:9:histogram',
  '30',
])

export interface Row {
  left: string
  op: Op
  right: string
}

export interface BuilderForm {
  /** File name under data_dir/rules (lowercase slug); the spec's display name follows it. */
  id: string
  name: string
  /** Trailing bars every decision reads; blank means the CLI default (4 × warm-up, min 60). */
  history: string
  longRows: Row[]
  shortRows: Row[]
}

export const EMPTY_ROW: Row = Object.freeze({ left: '', op: '>', right: '' })

export const EMPTY_FORM: BuilderForm = Object.freeze({
  id: '',
  name: '',
  history: '',
  longRows: [{ ...EMPTY_ROW }],
  shortRows: [],
})

export type OperandJson =
  | { source: string }
  | { value: number }
  | { indicator: string; params: number[]; field?: string }

/** `close` | `30` | `sma:20` | `bbands:20:2:lower` → the CLI's operand object, or a message. */
export function parseOperandText(text: string): OperandJson {
  const trimmed = text.trim().toLowerCase()
  if (!trimmed) throw new Error('empty — type a source, an indicator or a number')
  if ((SOURCES as readonly string[]).includes(trimmed)) return { source: trimmed }
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return { value: Number(trimmed) }
  const [head, ...rest] = trimmed.split(':')
  const arity = ARITY[head]
  if (arity === undefined) {
    throw new Error(`"${head}" is not a source (${SOURCES.join(', ')}), an indicator (${Object.keys(ARITY).join(', ')}) or a number`)
  }
  const fields = FIELDS[head]
  const field = fields && rest.length === arity + 1 ? rest.pop() : undefined
  if (rest.length !== arity) throw new Error(`${head} takes ${arity} parameter${arity === 1 ? '' : 's'}${fields ? ` and a field (${fields.join('/')})` : ''}`)
  const params = rest.map((part) => Number(part))
  if (params.some((value) => !Number.isFinite(value))) throw new Error(`${head} parameters must be numbers`)
  if (fields && !field) throw new Error(`${head} needs a field: ${fields.join(', ')}`)
  if (fields && field && !fields.includes(field)) throw new Error(`${head} field must be one of ${fields.join(', ')}`)
  return field ? { indicator: head, params, field } : { indicator: head, params }
}

export function operandText(operand: OperandJson): string {
  if ('source' in operand) return operand.source
  if ('value' in operand) return String(operand.value)
  const head = [operand.indicator, ...operand.params.map(String)].join(':')
  return operand.field ? `${head}:${operand.field}` : head
}

function rowsToJson(rows: readonly Row[]): { left: OperandJson; op: Op; right: OperandJson }[] {
  return rows
    .filter((row) => row.left.trim() || row.right.trim())
    .map((row) => ({ left: parseOperandText(row.left), op: row.op, right: parseOperandText(row.right) }))
}

/** The spec object for `POST /api/rules/validate` and `/api/rules`; row typos throw here first. */
export function formToSpec(form: BuilderForm): Record<string, unknown> {
  const spec: Record<string, unknown> = {
    name: form.name.trim() || form.id.trim(),
    long_when: rowsToJson(form.longRows),
    short_when: rowsToJson(form.shortRows),
  }
  if (form.history.trim()) spec.history = Number(form.history)
  return spec
}

function jsonToRows(side: unknown): Row[] {
  if (!Array.isArray(side)) return []
  return side.map((item) => {
    const row = item as { left: OperandJson; op: Op; right: OperandJson }
    return { left: operandText(row.left), op: row.op, right: operandText(row.right) }
  })
}

/** A saved record back into the editor. */
export function recordToForm(record: RuleRecord): BuilderForm {
  const spec = record.spec as { name?: unknown; history?: unknown; long_when?: unknown; short_when?: unknown }
  return {
    id: record.name,
    name: typeof spec.name === 'string' ? spec.name : record.name,
    history: typeof spec.history === 'number' ? String(spec.history) : '',
    longRows: jsonToRows(spec.long_when),
    shortRows: jsonToRows(spec.short_when),
  }
}

export const RULE_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/

export function ruleIdError(id: string): string | null {
  if (!id.trim()) return 'give the rule set a file name'
  return RULE_ID_PATTERN.test(id) ? null : 'lowercase letters, digits, - or _ only (1–64 characters)'
}

/** `alpha backtest run` arguments for a sandbox test of a saved rule set on a symbol. */
export function sandboxArgs(symbol: string, ruleId: string, marginAccount: boolean): string {
  const parts = [symbol.trim(), '--strategy', 'rules', '--rules', ruleId.trim()]
  if (marginAccount) parts.push('--account-type', 'MARGIN')
  return parts.join(' ')
}
