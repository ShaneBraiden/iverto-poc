import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { clock, clockSeconds } from '../format'

const SERIES = [
  { key: 'area', name: 'Waiting area', color: 'var(--area)' },
  { key: 'queue', name: 'Queue', color: 'var(--queue)' },
]

function Key({ color }) {
  return <span className="key" style={{ background: color }} />
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <div className="tooltip-time">{clockSeconds(label)}</div>
      {SERIES.map((s) => {
        const p = payload.find((x) => x.dataKey === s.key)
        return (
          <div className="tooltip-row" key={s.key}>
            <Key color={s.color} />
            <strong>{p?.value ?? '—'}</strong>
            <span>{s.name}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function TrendChart({ data, windowS }) {
  // Fixed window ending at the newest sample, with ticks on even 2-minute marks.
  const end = data.length ? data[data.length - 1].ts : Date.now() / 1000
  const start = end - windowS
  const ticks = []
  for (let t = Math.ceil(start / 120) * 120; t <= end; t += 120) ticks.push(t)
  return (
    <div className="panel">
      <div className="panel-head">
        <span>Occupancy · last {Math.round(windowS / 60)} min</span>
        <span className="legend">
          {SERIES.map((s) => (
            <span key={s.key}>
              <Key color={s.color} />
              {s.name}
            </span>
          ))}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -20 }}>
          <defs>
            {SERIES.map((s) => (
              <linearGradient key={s.key} id={`fill-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="ts"
            type="number"
            scale="time"
            domain={[start, end]}
            ticks={ticks}
            allowDataOverflow
            tickFormatter={clock}
            stroke="var(--axis)"
            tick={{ fill: 'var(--gray-500)', fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'var(--gray-500)', fontSize: 11 }}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }} isAnimationActive={false} />
          {SERIES.map((s) => (
            <Area
              key={s.key}
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              fill={`url(#fill-${s.key})`}
              dot={false}
              activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }}
              isAnimationActive={false}
              connectNulls={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
