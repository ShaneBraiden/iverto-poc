const json = (r) => {
  if (!r.ok) return r.json().catch(() => ({})).then((b) => Promise.reject(new Error(b.detail || `${r.status} ${r.statusText}`)))
  return r.json()
}

const send = (method, url, body) =>
  fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(json)

const stream = (name) => `/api/streams/${encodeURIComponent(name)}`

export const videoUrl = (name) => `${stream(name)}/video`
export const snapshotUrl = (name) => `${stream(name)}/snapshot?t=${Date.now()}`
export const thumbnailUrl = (name, tick) => `${stream(name)}/thumbnail?t=${tick}`

// CSV downloads are plain links: the browser saves the file, no fetch/blob dance.
export const reportCsvUrl = (name, minutes, detail = 'samples') =>
  name
    ? `${stream(name)}/report.csv?minutes=${minutes}&detail=${detail}`
    : `/api/report.csv?minutes=${minutes}`

// Upload goes through XHR because fetch cannot report upload progress. The body is the raw file.
const uploadStream = (label, file, onProgress) =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/streams/upload?label=${encodeURIComponent(label)}&filename=${encodeURIComponent(file.name)}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onerror = () => reject(new Error('Upload failed'))
    xhr.onload = () => {
      let body = {}
      try {
        body = JSON.parse(xhr.responseText)
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(body)
      else reject(new Error(typeof body.detail === 'string' ? body.detail : `${xhr.status} ${xhr.statusText}`))
    }
    xhr.send(file)
  })

export const api = {
  state: () => fetch('/api/state').then(json),
  history: (name, minutes, after) =>
    fetch(`${stream(name)}/history?minutes=${minutes}${after ? `&after=${after}` : ''}`).then(json),
  events: (name, limit = 6) => fetch(`${stream(name)}/events?limit=${limit}`).then(json),
  report: (name, minutes) =>
    fetch(name ? `${stream(name)}/report?minutes=${minutes}` : `/api/report?minutes=${minutes}`).then(json),
  setSettings: (name, settings) => send('POST', `${stream(name)}/settings`, settings),
  resetHeatmap: (name) => send('POST', `${stream(name)}/heatmap/reset`),
  saveZones: (name, zones) => send('PUT', `${stream(name)}/zones`, zones),
  addStream: (body) => send('POST', '/api/streams', body),
  uploadStream,
  removeStream: (name) => send('DELETE', stream(name)),
}

export function connectLive(onMessage) {
  let ws
  let closed = false
  let retry
  const open = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/api/ws`)
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    ws.onclose = () => {
      if (!closed) retry = setTimeout(open, 1000)
    }
  }
  open()
  return () => {
    closed = true
    clearTimeout(retry)
    ws?.close()
  }
}
