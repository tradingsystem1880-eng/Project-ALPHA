import { describe, expect, it } from 'vitest'
import * as format from './format'
import * as common from '../panels/rundetail/commonUtils'

type AsObj = (v: unknown) => Record<string, unknown> | null

const formatAsObj = (): AsObj => {
  const fn = (format as unknown as { asObj?: AsObj }).asObj
  expect(typeof fn).toBe('function')
  return fn as AsObj
}

const notObjects: unknown[] = [null, undefined, [], [1, 2], 0, 3.5, '', 'text', true, false]

describe('plain-object check in util/format', () => {
  it('util/format asObj returns the same plain object it is given', () => {
    const asObj = formatAsObj()
    const value = { a: 1, nested: { b: 'x' } }
    expect(asObj(value)).toBe(value)
    const empty = {}
    expect(asObj(empty)).toBe(empty)
  })

  it('util/format asObj returns null for null, undefined, arrays and primitives', () => {
    const asObj = formatAsObj()
    for (const value of notObjects) {
      expect(asObj(value)).toBeNull()
    }
  })

  it('util/format asObj agrees with the asObj that rundetail/commonUtils exports', () => {
    const asObj = formatAsObj()
    const commonAsObj = (common as unknown as { asObj: AsObj }).asObj
    const obj = { k: 'v' }
    for (const value of [...notObjects, obj]) {
      expect(asObj(value)).toBe(commonAsObj(value))
    }
  })

  it('rundetail/commonUtils still exports asObj for its importers', () => {
    const commonAsObj = (common as unknown as { asObj?: AsObj }).asObj
    expect(typeof commonAsObj).toBe('function')
    const obj = { k: 1 }
    expect((commonAsObj as AsObj)(obj)).toBe(obj)
    expect((commonAsObj as AsObj)(null)).toBeNull()
  })
})
