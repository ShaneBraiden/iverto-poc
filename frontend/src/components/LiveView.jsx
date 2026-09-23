import { AlertTriangle } from 'lucide-react'
import { videoUrl } from '../api'
import { STATUS } from '../format'

const LEGEND = [
  { label: 'Entrance', color: 'var(--line)' },
  { label: 'Waiting area', color: 'var(--area)' },
  { label: 'Queue', color: 'var(--queue)' },
]

export default function LiveView({ name, status, alerts }) {
  return (
    <div className="video">
      <img src={videoUrl(name)} alt="Annotated live video" />
      {status && status !== 'live' && (
        <div className="video-status">{(STATUS[status]?.label ?? status) + '…'}</div>
      )}
      {alerts.length > 0 && (
        <div className="banner alert-pulse" role="alert">
          <AlertTriangle size={15} />
          {alerts.map((a) => a.message).join(' · ')}
        </div>
      )}
      <div className="video-legend">
        {LEGEND.map((l) => (
          <span key={l.label}>
            <span className="key" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  )
}
