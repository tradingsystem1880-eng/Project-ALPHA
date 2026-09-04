import { describe, expect, it } from 'vitest'

import { AREA_TEXT, STORE_AREAS, storeChangedPatch, type ActivityState } from './activity'

const base: ActivityState = {
  connection: 'live',
  runsVersion: 0,
  jobsVersion: 0,
  areaVersions: { research: 0, control: 3, bars: 0, paper: 0, workspaces: 0, alerts: 0 },
  runningJobs: 0,
  feed: [],
}

describe('activity store areas', () => {
  it('bumps exactly the named area', () => {
    const patch = storeChangedPatch(base, { area: 'control', at: 1 })
    expect(patch).toEqual({
      area: 'control',
      areaVersions: { research: 0, control: 4, bars: 0, paper: 0, workspaces: 0, alerts: 0 },
    })
  })

  it('ignores unknown or malformed areas rather than inventing one', () => {
    expect(storeChangedPatch(base, { area: 'figures' })).toBeNull()
    expect(storeChangedPatch(base, { at: 1 })).toBeNull()
    expect(storeChangedPatch(base, null)).toBeNull()
  })

  it('has a feed sentence for every area the server watches', () => {
    for (const area of STORE_AREAS) expect(AREA_TEXT[area]).toMatch(/changed/)
  })
})
