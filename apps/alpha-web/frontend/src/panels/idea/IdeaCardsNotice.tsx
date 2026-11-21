import './IdeaWorkspace.css'
// Under "no research cases yet": the idea cards that do exist, with a link to the Ideas page.
// A display only; it reads the same list as the Ideas page.

import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { IdeaList } from '../../api/types'
import { useAreaVersion } from '../../state/activity'
import { newestFirst, shortDay } from './ideaModel'

export const IDEAS_HREF = '#page=research&pane=IdeaWorkspace'

export function IdeaCardsNoticeView({ data }: { data: IdeaList | null }) {
  if (!data || data.total === 0) return null
  const latest = newestFirst(data.cards)[0]
  return (
    <section className="idea-notice" aria-label="Idea cards">
      <p>
        <strong>{`${data.total} idea card${data.total === 1 ? '' : 's'} written.`}</strong>
        {` The newest, saved ${shortDay(latest.saved_at)}: “${latest.claim || 'claim not stated'}”.`}
      </p>
      <a href={IDEAS_HREF} className="btn">Open Ideas</a>
    </section>
  )
}

export function IdeaCardsNotice() {
  const version = useAreaVersion('ideas')
  const [data, setData] = useState<IdeaList | null>(null)
  useEffect(() => {
    let live = true
    api.ideaList().then(
      value => { if (live) setData(value) },
      () => { if (live) setData(null) },
    )
    return () => { live = false }
  }, [version])
  return <IdeaCardsNoticeView data={data} />
}
