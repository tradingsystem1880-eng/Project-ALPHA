import type {
  AutoscaleInfo,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
  UTCTimestamp,
} from 'lightweight-charts'

import type { ChartAnnotation } from '../api/types'
import { CHART } from '../util/chartTheme'

class AnnotationRenderer implements IPrimitivePaneRenderer {
  private readonly annotations: readonly ChartAnnotation[]
  private readonly getAttached: () => SeriesAttachedParameter<Time> | null

  constructor(
    annotations: readonly ChartAnnotation[],
    attached: () => SeriesAttachedParameter<Time> | null,
  ) {
    this.annotations = annotations
    this.getAttached = attached
  }

  draw(target: Parameters<IPrimitivePaneRenderer['draw']>[0]): void {
    const attached = this.getAttached()
    if (!attached) return
    const timeScale = attached.chart.timeScale()
    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      context.save()
      context.lineWidth = 1
      context.lineJoin = 'round'
      context.lineCap = 'round'
      context.beginPath()
      context.rect(0, 0, mediaSize.width, mediaSize.height)
      context.clip()
      for (const annotation of this.annotations) {
        if (annotation.unit !== 'price' || annotation.anchors.length < 2) continue
        context.beginPath()
        context.strokeStyle = annotation.kind === 'zone' ? CHART.gold : CHART.accent
        context.setLineDash(annotation.kind === 'zone' ? [6, 4] : [])
        let started = false
        for (const anchor of annotation.anchors) {
          const x = timeScale.timeToCoordinate(anchor.ts as UTCTimestamp)
          const y = attached.series.priceToCoordinate(anchor.value)
          if (x === null || y === null) continue
          if (!started) {
            context.moveTo(x, y)
            started = true
          } else {
            context.lineTo(x, y)
          }
        }
        if (started) context.stroke()
      }
      context.restore()
    })
  }
}

class AnnotationPaneView implements IPrimitivePaneView {
  private readonly annotationRenderer: AnnotationRenderer

  constructor(annotationRenderer: AnnotationRenderer) {
    this.annotationRenderer = annotationRenderer
  }

  zOrder(): 'top' {
    return 'top'
  }

  renderer(): IPrimitivePaneRenderer {
    return this.annotationRenderer
  }
}

class ChartAnnotationPrimitive implements ISeriesPrimitive<Time> {
  private attachment: SeriesAttachedParameter<Time> | null = null
  private readonly views: readonly IPrimitivePaneView[]
  private readonly priceRange: AutoscaleInfo | null

  constructor(annotations: readonly ChartAnnotation[]) {
    this.views = [new AnnotationPaneView(new AnnotationRenderer(annotations, () => this.attachment))]
    const values = annotations
      .filter((annotation) => annotation.unit === 'price')
      .flatMap((annotation) => annotation.anchors.map((anchor) => anchor.value))
      .filter(Number.isFinite)
    this.priceRange = values.length > 0
      ? { priceRange: { minValue: Math.min(...values), maxValue: Math.max(...values) } }
      : null
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.attachment = param
  }

  detached(): void {
    this.attachment = null
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views
  }

  autoscaleInfo(): AutoscaleInfo | null {
    return this.priceRange
  }
}

export function createChartAnnotationPrimitive(
  annotations: readonly ChartAnnotation[],
): ISeriesPrimitive<Time> {
  return new ChartAnnotationPrimitive(annotations)
}
