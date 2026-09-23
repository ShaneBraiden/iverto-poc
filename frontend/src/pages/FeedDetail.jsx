import { useEffect, useState } from 'react'
import { ArrowLeft, Flame, RotateCcw, Shapes, Trash2, UserRoundX } from 'lucide-react'
import { api } from '../api'
import Alerts from '../components/Alerts'
import Counters from '../components/Counters'
import FeedReport from '../components/FeedReport'
import LiveView from '../components/LiveView'
import TrendChart from '../components/TrendChart'
import ZoneEditor from '../components/ZoneEditor'
import Modal from '../components/ui/Modal'
import PageHeader from '../components/ui/PageHeader'
import { KIND, STATUS } from '../format'

const WINDOW_S = 600

// Insert a null point where samples are missing (> 5 s) so the line breaks instead of bridging.
function appendWithGaps(series, rows) {
  const out = [...series]
  for (const { ts, area, queue } of rows) {
    const prev = out[out.length - 1]
    if (prev && ts - prev.ts > 5) out.push({ ts: prev.ts + 1, area: null, queue: null })
    out.push({ ts, area, queue })
  }
  return out
}

export default function FeedDetail({ stream, state, onBack, onZonesSaved, onRemove }) {
  const [series, setSeries] = useState([])
  const [events, setEvents] = useState([])
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const name = stream.name
  const status = state?.status
  const metrics = state?.metrics ?? {}
  const settings = state?.settings ?? stream.settings ?? {}
  const alerts = metrics.alerts ?? []
  const alertKey = alerts.map((a) => a.kind).join()

  // The chart shows exactly what is stored: load history, then poll for new rows.
  useEffect(() => {
    let last = 0
    let busy = false
    setSeries([])
    const poll = () => {
      if (busy) return
      busy = true
      api
        .history(name, WINDOW_S / 60, last)
        .then((rows) => {
          if (!rows.length) return
          last = rows[rows.length - 1].ts
          setSeries((s) => appendWithGaps(s, rows).filter((p) => p.ts >= Date.now() / 1000 - WINDOW_S))
        })
        .catch(() => {})
        .finally(() => (busy = false))
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => clearInterval(id)
  }, [name])

  // Refresh the alert log on feed change and whenever an alert starts.
  useEffect(() => {
    api.events(name, 6).then(setEvents).catch(() => {})
  }, [name, alertKey])

  const toggle = (key) => api.setSettings(name, { [key]: !settings[key] }).catch(() => {})

  const saveZones = (zones) =>
    api.saveZones(name, zones).then((saved) => {
      onZonesSaved(name, saved)
      setEditing(false)
    })

  const info = STATUS[status] ?? { label: status ?? 'connecting', badge: 'badge-gray' }
  const fps = status === 'live' && metrics.fps != null ? ` · ${Math.round(metrics.fps)} fps` : ''

  return (
    <>
      <PageHeader
        title={
          <>
            <button className="icon-btn" onClick={onBack} aria-label="Back to feeds">
              <ArrowLeft size={18} />
            </button>
            {stream.label}
            <span className={`badge ${info.badge}`}>{info.label}</span>
          </>
        }
        subtitle={`${KIND[stream.kind] ?? stream.kind} · ${stream.uri}${fps}`}
        actions={
          <>
            <button className={`btn-secondary${settings.blur ? ' on' : ''}`} onClick={() => toggle('blur')}>
              <UserRoundX size={16} />
              Blur
            </button>
            <button className={`btn-secondary${settings.heatmap ? ' on' : ''}`} onClick={() => toggle('heatmap')}>
              <Flame size={16} />
              Heatmap
            </button>
            {settings.heatmap && (
              <button className="icon-btn" onClick={() => api.resetHeatmap(name)} title="Clear heatmap">
                <RotateCcw size={16} />
              </button>
            )}
            <button className={`btn-secondary${editing ? ' on' : ''}`} onClick={() => setEditing((e) => !e)}>
              <Shapes size={16} />
              Zones
            </button>
            <button className="btn-danger" onClick={() => setConfirming(true)}>
              <Trash2 size={16} />
              Remove
            </button>
          </>
        }
      />

      <div className="detail">
        <section>
          {editing ? (
            <ZoneEditor
              key={name}
              name={name}
              zones={stream.zones}
              onSave={saveZones}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <LiveView name={name} status={status} alerts={alerts} />
          )}
        </section>
        <aside className="detail-side">
          <Counters metrics={metrics} alerts={alerts} />
          <TrendChart data={series} windowS={WINDOW_S} />
          <Alerts events={events} />
        </aside>
      </div>

      <FeedReport name={name} label={stream.label} />

      {confirming && (
        <Modal
          title="Remove stream"
          onClose={() => setConfirming(false)}
          footer={
            <>
              <button className="btn-secondary" onClick={() => setConfirming(false)}>
                Cancel
              </button>
              <button className="btn-danger" onClick={() => onRemove(name)}>
                <Trash2 size={16} />
                Remove
              </button>
            </>
          }
        >
          <p style={{ margin: 0, color: 'var(--gray-500)', fontSize: '0.875rem' }}>
            {stream.label} stops being analysed
            {stream.upload ? ' and its uploaded video and zones are deleted' : stream.custom ? ' and its zones are deleted' : ''}.
            Recorded history stays in the database.
          </p>
        </Modal>
      )}
    </>
  )
}
