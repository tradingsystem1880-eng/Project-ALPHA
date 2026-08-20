import { describe, expect, it } from 'vitest'

import { LEVELS, levelColor, levelHint } from './evidence'

describe('evidence styling', () => {
  it('covers every level with a distinct color and a hint', () => {
    const colors = LEVELS.map((level) => levelColor(level))
    expect(new Set(colors).size).toBe(LEVELS.length)
    for (const level of LEVELS) {
      expect(levelHint(level)).toBeTruthy()
    }
  })

  it('ladder order matches the schema', () => {
    expect(LEVELS[0]).toBe('unknown')
    expect(LEVELS[LEVELS.length - 1]).toBe('observed')
  })
})
