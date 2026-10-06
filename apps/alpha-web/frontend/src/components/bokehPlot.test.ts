import { afterEach, expect, it, vi } from 'vitest'
const state = vi.hoisted(() => ({ pending: [] as { resolve: (value: unknown) => void; destroy: ReturnType<typeof vi.fn> }[] }))
vi.mock('./bokehLifecycle', () => ({ showScientificPlot: () => new Promise(resolve => { state.pending.push({ resolve, destroy: vi.fn() }) }) }))
vi.mock('@bokeh/bokehjs/build/js/lib/api/figure', () => ({ figure: () => ({ axis: {}, grid: {}, line: () => ({}), segment: () => ({}), vbar: () => ({}), scatter: () => ({}), multi_line: () => ({}), add_tools() {}, add_layout() {}, on_event() {} }) }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/sources/column_data_source', () => ({ ColumnDataSource: class { selected = { change: { connect() {} } }; constructor(_: unknown) {} } }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/ranges/range1d', () => ({ Range1d: class { change = { connect() {} }; constructor(_: unknown) {} } }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/annotations/span', () => ({ Span: class { constructor(_: unknown) {} } }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool', () => ({ HoverTool: class { constructor(_: unknown) {} } }))
vi.mock('@bokeh/bokehjs/build/js/lib/core/bokeh_events', () => ({ MouseMove: {}, MouseLeave: {}, RangesUpdate: {}, LODStart: {}, LODEnd: {} }))
import { mountBokehPlot } from './bokehPlot'
import { createChartLinkRegistry } from '../shell/chartLinkRegistry'
afterEach(() => { state.pending.length = 0; vi.unstubAllGlobals() })
it.each([true, false])('stale asynchronous plot cannot take replacement links; old resolves first=%s', async oldFirst => {
  let frame: (() => void) | undefined
  vi.stubGlobal('requestAnimationFrame', (f: () => void) => { frame = f; return 1 })
  vi.stubGlobal('ResizeObserver', class { observe() {}; disconnect() {} })
  const registry = createChartLinkRegistry(); registry.configure(false, true)
  const node = { clientWidth: 500, clientHeight: 300, dataset: {}, ownerDocument: { createElement: () => ({ style: {}, remove() {} }) } } as unknown as HTMLElement
  const oldCursor = vi.fn(), newCursor = vi.fn()
  const old = mountBokehPlot(node, 'USD', 'panel', registry, oldCursor, false)
  const next = mountBokehPlot(node, 'USD', 'panel', registry, newCursor, false)
  const finish = (n: number) => state.pending[n].resolve({ destroy: state.pending[n].destroy, view: { el: { remove() {} }, canvas_view: { overlays_el: { append() {} } }, frame: { bbox: { left: 0, right: 500, top: 0, height: 300 }, x_scale: { compute: (x: number) => x } }, repainted: { connect() {}, disconnect() {} } } })
  if (oldFirst) { finish(0); (await old).destroy(); finish(1); (await next).activate() }
  else { finish(1); (await next).activate(); finish(0); (await old).destroy() }
  registry.publish('other', 'cursor'); frame!()
  expect(newCursor).toHaveBeenCalledWith('Cursor —'); expect(oldCursor).not.toHaveBeenCalled()
  expect(state.pending[0].destroy).toHaveBeenCalledOnce()
  ;(await next).destroy()
})
