import { show } from '@bokeh/bokehjs/build/js/lib/api/io'
import { documents } from '@bokeh/bokehjs/build/js/lib/document/document'
import type { Figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
/** Each plot owns a standalone document. Release its graph and global registry on every exit. */
export async function showScientificPlot(plot: Figure, node: HTMLElement) {
  const mounting = show(plot, node)
  const documentModel = plot.document!
  let disposed = false
  const destroy = () => {
    if (disposed) return
    disposed = true
    documentModel.views_manager?.clear(); documentModel.clear()
    const index = documents.indexOf(documentModel); if (index >= 0) documents.splice(index, 1)
  }
  try { return { view: await mounting, destroy } } catch (error) { destroy(); throw error }
}
