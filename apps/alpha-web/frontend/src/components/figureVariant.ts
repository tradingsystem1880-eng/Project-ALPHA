// Pure decisions behind the figure pair: which chart is showing, what the toggle says, and the
// paragraphs of the long explanation. Every figure comes as a plain chart and an annotated chart
// that plot the same data; the card shows one at a time.

export type FigureVariant = 'plain' | 'annotated'

export const FIGURE_VARIANTS: readonly FigureVariant[] = ['plain', 'annotated']

/** The variant the toggle switches to. */
export function otherVariant(variant: FigureVariant): FigureVariant {
  return variant === 'plain' ? 'annotated' : 'plain'
}

/** The toggle's words name what pressing it shows next. */
export function toggleLabel(variant: FigureVariant): string {
  return variant === 'plain' ? 'Show annotated' : 'Show plain chart'
}

/** Sentences of the long explanation, trimmed; an empty entry is dropped, never shown blank. */
export function explanationSentences(explanation: readonly string[] | undefined): string[] {
  return (explanation ?? []).map((sentence) => sentence.trim()).filter((sentence) => sentence.length > 0)
}

/** Save-as name for a figure image: the variant is part of the name so a pair never collides. */
export function variantFileName(figureId: string, variant: FigureVariant, ext: 'svg' | 'png'): string {
  return `${figureId}.${variant}.${ext}`
}
