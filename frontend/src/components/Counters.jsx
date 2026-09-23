import { Clock, LogIn, LogOut, Timer, Users, UsersRound } from 'lucide-react'
import { duration } from '../format'

function Tile({ icon: Icon, label, value, note, alert }) {
  return (
    <div className={`tile${alert ? ' tile-alert' : ''}`}>
      <div className="tile-label">
        <Icon size={13} />
        {label}
      </div>
      <div className="tile-value">{value ?? '—'}</div>
      {note && <div className="tile-note">{note}</div>}
    </div>
  )
}

export default function Counters({ metrics: m, alerts }) {
  const active = new Set(alerts.map((a) => a.kind))
  const little = m.L != null && m.lambda_pm ? `L ${m.L.toFixed(1)} ÷ λ ${m.lambda_pm.toFixed(1)}/min` : null
  return (
    <div className="tiles">
      <Tile icon={Users} label="People" value={m.people} />
      <Tile icon={LogIn} label="Entries" value={m.entries} />
      <Tile icon={LogOut} label="Exits" value={m.exits} />
      <Tile
        icon={UsersRound}
        label="Waiting area"
        value={m.area}
        note={m.area_stay_s != null ? `avg stay ${duration(m.area_stay_s)}` : null}
        alert={active.has('area')}
      />
      <Tile icon={Timer} label="Queue" value={m.queue} alert={active.has('queue')} />
      <Tile icon={Clock} label="Est. wait" value={duration(m.wait_s)} note={little} />
    </div>
  )
}
