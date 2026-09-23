import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { thumbnailUrl } from '../api'
import { KIND, STATUS } from '../format'

// Preload the next frame and only swap it in once it decodes, so a feed that has no
// frame yet (or drops one) keeps showing the last good image instead of a broken icon.
function useThumbnail(name, tick) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    const img = new Image()
    img.onload = () => setSrc(img.src)
    img.src = thumbnailUrl(name, tick)
    return () => (img.onload = null)
  }, [name, tick])
  return src
}

export default function FeedCard({ stream, state, tick, onOpen }) {
  const src = useThumbnail(stream.name, tick)
  const status = state?.status ?? 'connecting'
  const m = state?.metrics ?? {}
  const alerts = m.alerts ?? []
  const info = STATUS[status] ?? { label: status, badge: 'badge-gray' }

  return (
    <button className={`card feed-card animate-fade-in-up${alerts.length ? ' alerting' : ''}`} onClick={onOpen}>
      <div className="feed-thumb">
        {src && <img src={src} alt={`${stream.label} latest frame`} />}
        <span className="badge">{KIND[stream.kind] ?? stream.kind}</span>
        {status !== 'live' && <span className="overlay">{info.label}…</span>}
      </div>

      <div className="feed-body">
        <div className="feed-head">
          <span className={`dot ${status}`} />
          <span className="feed-name">{stream.label}</span>
          <span className={`badge ${alerts.length ? 'badge-rose' : info.badge}`} style={{ marginLeft: 'auto' }}>
            {alerts.length ? <AlertTriangle size={11} /> : null}
            {alerts.length ? 'Alert' : info.label}
          </span>
        </div>

        <div className="feed-stats">
          <div className="feed-stat">
            <div className="feed-stat-label">People</div>
            <div className="feed-stat-value">{m.people ?? '—'}</div>
          </div>
          <div className="feed-stat">
            <div className="feed-stat-label">Queue</div>
            <div className="feed-stat-value">{m.queue ?? '—'}</div>
          </div>
          <div className="feed-stat">
            <div className="feed-stat-label">Waiting</div>
            <div className="feed-stat-value">{m.area ?? '—'}</div>
          </div>
        </div>
      </div>
    </button>
  )
}
