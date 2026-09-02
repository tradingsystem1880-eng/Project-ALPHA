import { describe, expect, it } from 'vitest'

import { copyCapability, exportNames, notesVisible } from './figureExport'

describe('exportNames', () => {
  it('names a saved image after the run and the figure, content-addressed by the run prefix', () => {
    expect(exportNames('cafe0000deadbeef', 'equity_curve')).toEqual({
      png: 'cafe0000-equity_curve.png',
      svg: 'cafe0000-equity_curve.svg',
    })
  })
})

describe('copyCapability', () => {
  it('is enabled when the page is secure and the clipboard can take an image', () => {
    expect(copyCapability({ secure: true, clipboardWrite: true, clipboardItem: true })).toEqual({
      enabled: true,
      reason: null,
    })
  })
  it('explains an insecure page before anything else', () => {
    expect(copyCapability({ secure: false, clipboardWrite: false, clipboardItem: false })).toEqual({
      enabled: false,
      reason: 'Copy needs a secure page (https or localhost)',
    })
  })
  it('explains a browser that cannot write images to the clipboard', () => {
    expect(copyCapability({ secure: true, clipboardWrite: false, clipboardItem: true }).reason).toBe(
      'This browser cannot copy images to the clipboard',
    )
    expect(copyCapability({ secure: true, clipboardWrite: true, clipboardItem: false }).enabled).toBe(
      false,
    )
  })
})

describe('notesVisible', () => {
  it('shows the prose only in narrative mode; it stays in the DOM either way', () => {
    expect(notesVisible('narrative')).toBe(true)
    expect(notesVisible('terse')).toBe(false)
  })
})
