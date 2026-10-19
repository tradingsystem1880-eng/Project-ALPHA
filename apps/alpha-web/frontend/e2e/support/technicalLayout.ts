import { expect, type Locator } from '@playwright/test'

/** This three-panel fixture must finish its pending maximize-width resize before hover targeting. */
export async function waitForTechnicalChartWidth(host: Locator) {
  await expect(host.locator('.technical-legend')).toHaveCount(3)
  await expect.poll(async () => {
    const width = await host.evaluate(node => node.clientWidth)
    const canvasWidths = await host.locator('canvas').evaluateAll(nodes =>
      nodes.map(node => node.getBoundingClientRect().width))
    return width > 0 && canvasWidths.length >= 3
      && canvasWidths.every(canvasWidth => Math.abs(canvasWidth - width) < 1)
  }).toBe(true)
}
