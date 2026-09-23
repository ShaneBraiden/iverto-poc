import { useEffect, useState } from 'react'
import { Plus, Video } from 'lucide-react'
import FeedCard from '../components/FeedCard'
import PageHeader from '../components/ui/PageHeader'
import { EmptyState } from '../components/ui/States'

// One timer for the whole grid: every card refreshes its thumbnail on the same tick.
const THUMB_MS = 1000

export default function Feeds({ streams, live, onOpen, onAdd, device }) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), THUMB_MS)
    return () => clearInterval(id)
  }, [])

  const liveCount = streams.filter((s) => live?.[s.name]?.status === 'live').length
  const people = streams.reduce((n, s) => n + (live?.[s.name]?.metrics?.people ?? 0), 0)

  return (
    <>
      <PageHeader
        title="Feeds"
        subtitle={`${liveCount}/${streams.length} live · ${people} people right now · ${device ?? ''}`}
        actions={
          <button className="btn-primary" onClick={onAdd}>
            <Plus size={16} />
            Add stream
          </button>
        }
      />
      {streams.length === 0 ? (
        <div className="card-static">
          <EmptyState
            icon={Video}
            title="No streams yet"
            text="Add a video file, an RTSP camera or a public live page to start counting."
            action={
              <button className="btn-primary" onClick={onAdd}>
                <Plus size={16} />
                Add stream
              </button>
            }
          />
        </div>
      ) : (
        <div className="feed-grid">
          {streams.map((s) => (
            <FeedCard key={s.name} stream={s} state={live?.[s.name]} tick={tick} onOpen={() => onOpen(s.name)} />
          ))}
        </div>
      )}
    </>
  )
}
