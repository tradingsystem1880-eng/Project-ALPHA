import { describe, expect, it } from 'vitest'

import { gradeColor, gradeSoft, isGrade } from './verdict'

describe('gradeColor', () => {
  it('maps every grade to its own token', () => {
    expect(gradeColor('A')).toBe('var(--verdict-a)')
    expect(gradeColor('B')).toBe('var(--verdict-b)')
    expect(gradeColor('C')).toBe('var(--verdict-c)')
    expect(gradeColor('D')).toBe('var(--verdict-d)')
    expect(gradeColor('F')).toBe('var(--verdict-f)')
  })

  it('falls back to muted for unknown grades', () => {
    expect(gradeColor('E')).toBe('var(--muted)')
    expect(gradeColor('')).toBe('var(--muted)')
    expect(gradeColor('a')).toBe('var(--muted)')
  })
})

describe('gradeSoft', () => {
  it('maps grades to soft tokens', () => {
    expect(gradeSoft('A')).toBe('var(--verdict-a-soft)')
    expect(gradeSoft('F')).toBe('var(--verdict-f-soft)')
  })
  it('falls back for unknown grades', () => {
    expect(gradeSoft('?')).toBe('var(--panel-2)')
  })
})

describe('isGrade', () => {
  it('accepts only A/B/C/D/F', () => {
    for (const g of ['A', 'B', 'C', 'D', 'F']) expect(isGrade(g)).toBe(true)
    for (const g of ['E', 'G', 'AA', 1, null, undefined]) expect(isGrade(g)).toBe(false)
  })
})
