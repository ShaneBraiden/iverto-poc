import { AlertTriangle, ShieldCheck } from 'lucide-react'
import { clockSeconds } from '../format'
import { EmptyState } from './ui/States'

export default function Alerts({ events }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <span>Alert log</span>
      </div>
      {events.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="No alerts" text="Nothing has gone over a limit on this feed." />
      ) : (
        events.map((e) => (
          <div className="alert-row" key={`${e.ts}-${e.kind}`}>
            <AlertTriangle size={14} color="var(--color-danger)" />
            <span>{e.message}</span>
            <span className="alert-value">{e.value}</span>
            <span className="alert-time">{clockSeconds(e.ts)}</span>
          </div>
        ))
      )}
    </div>
  )
}
