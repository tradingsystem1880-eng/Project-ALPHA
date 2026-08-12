import { describe, expect, it } from 'vitest'

import type { Settings } from './settings'
import { workspaceModeFor } from './settings'

const settings: Settings = {
  density: 'comfortable',
  explain: 'narrative',
  projectModes: { advanced_project: 'advanced' },
}

describe('workspace detail mode', () => {
  it('defaults every project and the unlinked workspace to guided mode', () => {
    expect(workspaceModeFor(settings, null)).toBe('guided')
    expect(workspaceModeFor(settings, 'new_project')).toBe('guided')
  })

  it('restores advanced mode only for the project that selected it', () => {
    expect(workspaceModeFor(settings, 'advanced_project')).toBe('advanced')
    expect(workspaceModeFor(settings, 'another_project')).toBe('guided')
  })
})
