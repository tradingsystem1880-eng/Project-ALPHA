import { beforeEach, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ show: vi.fn(), documents: [] as unknown[] }))
vi.mock('@bokeh/bokehjs/build/js/lib/api/io', () => ({ show: mocks.show }))
vi.mock('@bokeh/bokehjs/build/js/lib/document/document', () => ({ documents: mocks.documents }))
import { showScientificPlot } from './bokehLifecycle'
import type { Figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
beforeEach(() => { mocks.show.mockReset(); mocks.documents.length = 0 })
it('releases the owned document and views exactly once without touching a peer', async () => {
  const doc = { views_manager: { clear: vi.fn() }, clear: vi.fn() }, peer = {}
  mocks.documents.push(peer, doc); mocks.show.mockResolvedValue({})
  const plot = await showScientificPlot({ document: doc } as unknown as Figure, {} as HTMLElement)
  plot.destroy(); plot.destroy()
  expect(doc.views_manager.clear).toHaveBeenCalledTimes(1); expect(doc.clear).toHaveBeenCalledTimes(1)
  expect(mocks.documents).toEqual([peer])
})
it('failed asynchronous mounting releases the graph and preserves the error', async () => {
  const doc = { views_manager: { clear: vi.fn() }, clear: vi.fn() }
  mocks.documents.push(doc); mocks.show.mockRejectedValue(new Error('mount failed'))
  await expect(showScientificPlot({ document: doc } as unknown as Figure, {} as HTMLElement)).rejects.toThrow('mount failed')
  expect(doc.clear).toHaveBeenCalledOnce(); expect(mocks.documents).toEqual([])
})
