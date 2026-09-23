import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { clock, clockSeconds, num } from '../format'

const SERIES = [
  { key: 'people', name: 'People', color: 'var(--gray-400)' },
  { key: 'area', name: 'Waiting area', color: 'var(--area)' },
  { key: 'queue', name: 'Queue', color: 'var(--queue)' },
]

function Key({ color }) {
  return <span className="key" style={{ background: color }} />
}

export function ChartLegend() {
  return (
    <span className="legend">
      {SERIES.map((s) => (
        <span key={s.key}>
          <Key color={s.color} />
          {s.name}
        </span>
      ))}
    </span>
  )
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <div className="tooltip-time">{clockSeconds(label)}</div>
      {SERIES.map((s) => (
        <div className="tooltip-row" key={s.key}>
          <Key color={s.color} />
          <strong>{num(payload.find((x) => x.dataKey === s.key)?.value)}</strong>
          <span>{s.name}</span>
        </div>
      ))}
    </div>
  )
}

/** Averages per bucket over a report period. `width` renders a fixed-size chart
    (the print sheet has no layout to measure); without it the chart is responsive. */
export default function ReportChart({ data, from, to, height = 200, width }) {
  const step = (to - from) / 6
  const ticks = Array.from({ length: 7 }, (_, i) => from + i * step)

  const chart = (
    <AreaChart data={data} width={width} height={width ? height : undefined} margin={{ top: 8, right: 12, bottom: 0, left: -20 }}>
      <defs>
        {SERIES.map((s) => (
          <linearGradient key={s.key} id={`report-fill-${s.key}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={s.color} stopOpacity={0.22} />
            <stop offset="100%" stopColor={s.color} stopOpacity={0} />
          </linearGradient>
        ))}
      </defs>
      <CartesianGrid vertical={false} stroke="var(--grid)" />
      <XAxis
        dataKey="ts"
        type="number"
        scale="time"
        domain={[from, to]}
        ticks={ticks}
        allowDataOverflow
        tickFormatter={clock}
        stroke="var(--axis)"
        tick={{ fill: 'var(--gray-500)', fontSize: 11 }}
        tickLine={false}
      />
      <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: 'var(--gray-500)', fontSize: 11 }} />
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
          fill={`url(#report-fill-${s.key})`}
          dot={false}
          activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }}
          isAnimationActive={false}
          connectNulls={false}
        />
      ))}
    </AreaChart>
  )

  if (width) return chart
  return (
    <ResponsiveContainer width="100%" height={height}>
      {chart}
    </ResponsiveContainer>
  )
}
