export function duration(s) {
  if (s == null) return '—'
  const t = Math.round(s)
  if (t < 60) return `${t}s`
  const m = Math.floor(t / 60)
  const r = t % 60
  return `${m}m ${String(r).padStart(2, '0')}s`
}

export function clock(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function stamp(ts) {
  return ts == null ? '—' : new Date(ts * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

// Measured values only: a missing number stays a dash, it is never shown as 0.
export function num(v, digits = 1) {
  return v == null ? '—' : Number(v).toFixed(digits).replace(/\.0+$/, '')
}

export function percent(v) {
  return v == null ? '—' : `${Math.round(v * 100)}%`
}

export function clockSeconds(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export const STATUS = {
  live: { label: 'Live', badge: 'badge-emerald' },
  connecting: { label: 'Connecting', badge: 'badge-orange' },
  reconnecting: { label: 'Reconnecting', badge: 'badge-rose' },
  error: { label: 'Unavailable', badge: 'badge-rose' },
}

export const KIND = { file: 'File', rtsp: 'RTSP', web: 'Web' }
