import { useState } from 'react'
import Modal from './ui/Modal'

const KINDS = [
  { value: 'upload', label: 'Upload video' },
  { value: 'rtsp', label: 'RTSP camera', hint: 'e.g. rtsp://user:pass@192.168.1.20:554/stream1' },
  { value: 'web', label: 'Web stream', hint: 'A YouTube live or video URL, or any page yt-dlp can read. Videos loop.' },
]

export default function AddStreamModal({ onAdd, onClose }) {
  const [label, setLabel] = useState('')
  const [kind, setKind] = useState('upload')
  const [uri, setUri] = useState('')
  const [file, setFile] = useState(null)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const upload = kind === 'upload'

  const pickFile = (e) => {
    const picked = e.target.files[0] ?? null
    setFile(picked)
    if (picked && !label.trim()) setLabel(picked.name.replace(/\.[^.]+$/, ''))
  }

  const submit = (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const body = upload ? { label: label.trim(), file } : { label: label.trim(), kind, uri: uri.trim() }
    onAdd(body, setProgress)
      .catch((err) => {
        setError(err.message)
        setBusy(false)
      })
  }

  const hint = KINDS.find((k) => k.value === kind).hint
  const ready = label.trim() && (upload ? file : uri.trim())

  return (
    <Modal title="Add stream" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-rows">
          <div>
            <label className="field-label field-required" htmlFor="stream-label">
              Name
            </label>
            <input
              id="stream-label"
              className="field"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Main entrance"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="field-label" htmlFor="stream-kind">
              Type
            </label>
            <select id="stream-kind" className="field" value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field-label field-required" htmlFor="stream-source">
              {upload ? 'Video' : 'Source'}
            </label>
            {upload ? (
              <input
                id="stream-source"
                className={`field${error ? ' field-invalid' : ''}`}
                type="file"
                accept="video/*,.mkv"
                onChange={pickFile}
                required
              />
            ) : (
              <input
                id="stream-source"
                className={`field${error ? ' field-invalid' : ''}`}
                value={uri}
                onChange={(e) => setUri(e.target.value)}
                placeholder="rtsp://…"
                required
              />
            )}
            {error ? <div className="field-error">{error}</div> : hint && <div className="field-hint">{hint}</div>}
          </div>
        </div>
        <div className="modal-foot">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={busy || !ready}>
            {busy ? (upload && progress != null && progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : 'Starting…') : 'Add stream'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
