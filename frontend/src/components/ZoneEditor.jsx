import { useRef, useState } from 'react'
import { snapshotUrl } from '../api'

const SHAPES = [
  { key: 'line', label: 'Entrance line', color: 'var(--line)' },
  { key: 'queue', label: 'Queue', color: 'var(--queue)' },
  { key: 'area', label: 'Waiting area', color: 'var(--area)' },
]

const clamp = (v) => Math.min(1, Math.max(0, v))

function valid(d) {
  return (
    (d.line.length === 0 || d.line.length === 2) &&
    (d.queue.length === 0 || d.queue.length >= 3) &&
    (d.area.length === 0 || d.area.length >= 3)
  )
}

function Limit({ label, value, onChange }) {
  return (
    <label className="limit">
      {label}
      <input
        className="field"
        type="number"
        min="0"
        value={value ?? ''}
        placeholder="—"
        onChange={(e) => onChange(e.target.value === '' ? null : Math.max(0, parseInt(e.target.value, 10)))}
      />
    </label>
  )
}

export default function ZoneEditor({ name, zones, onSave, onCancel }) {
  const [draft, setDraft] = useState(() => structuredClone(zones))
  const [active, setActive] = useState('line')
  const [drawing, setDrawing] = useState(false)
  const [src] = useState(() => snapshotUrl(name))
  const [size, setSize] = useState({ w: 1280, h: 720 })
  const canvas = useRef(null)
  const drag = useRef(null)

  const toNorm = (e) => {
    const r = canvas.current.getBoundingClientRect()
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)]
  }
  const setPoints = (key, pts) => setDraft((d) => ({ ...d, [key]: pts }))

  const select = (key) => {
    setActive(key)
    setDrawing(draft[key].length === 0)
  }

  const addPoint = (e) => {
    if (!drawing) return
    const pts = [...draft[active], toNorm(e)]
    setPoints(active, pts)
    if (active === 'line' && pts.length === 2) setDrawing(false)
  }

  const onHandleDown = (e, key, i) => {
    e.stopPropagation()
    if (drawing && key === active && active !== 'line' && i === 0 && draft[key].length >= 3) {
      setDrawing(false) // clicking the first point closes the polygon
      return
    }
    drag.current = { key, i }
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const onHandleMove = (e) => {
    if (!drag.current) return
    const { key, i } = drag.current
    setDraft((d) => ({ ...d, [key]: d[key].map((p, j) => (j === i ? toNorm(e) : p)) }))
  }

  const px = ([x, y]) => [x * size.w, y * size.h]
  const pointsAttr = (pts) => pts.map((p) => px(p).join(',')).join(' ')

  const renderLine = (pts, color) => {
    if (pts.length < 2) return null
    const [[x1, y1], [x2, y2]] = pts.map(px)
    const len = Math.hypot(x2 - x1, y2 - y1) || 1
    const nx = (y2 - y1) / len // "in" side, matching the backend's LineZone
    const ny = -(x2 - x1) / len
    const mx = (x1 + x2) / 2
    const my = (y1 + y2) / 2
    const a = size.w / 30 // arrow length scales with frame size
    const tip = [mx + nx * a, my + ny * a]
    const head = [
      [tip[0] - nx * a * 0.4 + ny * a * 0.25, tip[1] - ny * a * 0.4 - nx * a * 0.25],
      [tip[0] - nx * a * 0.4 - ny * a * 0.25, tip[1] - ny * a * 0.4 + nx * a * 0.25],
    ]
    return (
      <g stroke={color} fill={color}>
        <line x1={x1} y1={y1} x2={x2} y2={y2} strokeWidth="3" vectorEffect="non-scaling-stroke" />
        <line x1={mx} y1={my} x2={tip[0]} y2={tip[1]} strokeWidth="3" vectorEffect="non-scaling-stroke" />
        <polygon points={[tip, ...head].map((p) => p.join(',')).join(' ')} />
      </g>
    )
  }

  const renderPolygon = (key, pts, color) => {
    if (pts.length === 0) return null
    const open = drawing && key === active
    return open || pts.length < 3 ? (
      <polyline points={pointsAttr(pts)} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    ) : (
      <polygon points={pointsAttr(pts)} fill={color} fillOpacity="0.15" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    )
  }

  return (
    <div>
      <div className="editor-bar">
        <div className="seg">
          {SHAPES.map((s) => (
            <button key={s.key} className={active === s.key ? 'on' : ''} onClick={() => select(s.key)}>
              <span className="key" style={{ background: active === s.key ? '#fff' : s.color }} />
              {s.label}
            </button>
          ))}
        </div>
        <button
          className="btn-secondary"
          onClick={() => {
            setPoints(active, [])
            setDrawing(true)
          }}
        >
          Redraw
        </button>
        {active === 'line' && draft.line.length === 2 && (
          <button className="btn-secondary" onClick={() => setPoints('line', [...draft.line].reverse())}>
            Flip direction
          </button>
        )}
        <span className="spacer" />
        <Limit label="Queue limit" value={draft.queue_limit} onChange={(v) => setDraft({ ...draft, queue_limit: v })} />
        <Limit label="Area limit" value={draft.area_limit} onChange={(v) => setDraft({ ...draft, area_limit: v })} />
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn-primary" disabled={!valid(draft)} onClick={() => onSave(draft)}>
          Save zones
        </button>
      </div>

      <div ref={canvas} className={`editor-canvas${drawing ? ' drawing' : ''}`} onClick={addPoint}>
        <img src={src} alt="Current frame" onLoad={(e) => setSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })} />
        <svg viewBox={`0 0 ${size.w} ${size.h}`} preserveAspectRatio="none">
          {renderPolygon('area', draft.area, 'var(--area)')}
          {renderPolygon('queue', draft.queue, 'var(--queue)')}
          {renderLine(draft.line, 'var(--line)')}
        </svg>
        {SHAPES.flatMap((s) =>
          draft[s.key].map(([x, y], i) => (
            <div
              key={`${s.key}-${i}`}
              className={`handle${s.key === active ? ' active' : ''}`}
              style={{ left: `${x * 100}%`, top: `${y * 100}%`, borderColor: s.color }}
              onPointerDown={(e) => onHandleDown(e, s.key, i)}
              onPointerMove={onHandleMove}
              onPointerUp={() => (drag.current = null)}
              onClick={(e) => e.stopPropagation()}
            />
          )),
        )}
        {drawing && (
          <div className="editor-hint">
            {active === 'line' ? 'Click two points' : 'Click to add points · click the first point to finish'}
          </div>
        )}
      </div>
    </div>
  )
}
