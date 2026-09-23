import { useCallback, useEffect, useState } from 'react'
import { api, connectLive } from './api'
import AddStreamModal from './components/AddStreamModal'
import { CenteredSpinner } from './components/ui/States'
import DashboardLayout from './layouts/DashboardLayout'
import FeedDetail from './pages/FeedDetail'
import Feeds from './pages/Feeds'
import Reports from './pages/Reports'

// Hash routing: #/ = all feeds, #/reports = report, #/feed/<name> = one feed.
// Keeps back/forward and reload working.
const REPORTS = '#/reports'
const readHash = () => decodeURIComponent(location.hash.match(/^#\/feed\/(.+)$/)?.[1] ?? '') || null
const readReports = () => location.hash === REPORTS

export default function App() {
  const [info, setInfo] = useState(null)
  const [live, setLive] = useState(null)
  const [selected, setSelected] = useState(readHash)
  const [reports, setReports] = useState(readReports)
  const [adding, setAdding] = useState(false)

  useEffect(() => connectLive((msg) => setLive(msg.streams)), [])
  useEffect(() => {
    api.state().then(setInfo).catch(() => {})
  }, [])

  useEffect(() => {
    const onHash = () => {
      setSelected(readHash())
      setReports(readReports())
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const select = useCallback((name) => {
    location.hash = name ? `#/feed/${encodeURIComponent(name)}` : '#/'
    setSelected(name)
    setReports(false)
  }, [])

  const openReports = useCallback(() => {
    location.hash = REPORTS
    setSelected(null)
    setReports(true)
  }, [])

  const addStream = ({ file, ...body }, onProgress) =>
    (file ? api.uploadStream(body.label, file, onProgress) : api.addStream(body)).then((created) => {
      setInfo((i) => ({ ...i, streams: [...i.streams, created] }))
      setAdding(false)
      select(created.name)
    })

  const removeStream = (name) =>
    api.removeStream(name).then(() => {
      setInfo((i) => ({ ...i, streams: i.streams.filter((s) => s.name !== name) }))
      select(null)
    })

  const onZonesSaved = (name, zones) =>
    setInfo((i) => ({ ...i, streams: i.streams.map((s) => (s.name === name ? { ...s, zones } : s)) }))

  if (!info) return <CenteredSpinner />

  const streams = info.streams
  const stream = streams.find((s) => s.name === selected)
  const note = `${info.model} · ${info.device}`

  return (
    <DashboardLayout
      streams={streams}
      live={live}
      selected={stream ? stream.name : null}
      reports={reports}
      onSelect={select}
      onReports={openReports}
      onAdd={() => setAdding(true)}
      footNote={note}
    >
      {stream ? (
        <FeedDetail
          key={stream.name}
          stream={stream}
          state={live?.[stream.name]}
          onBack={() => select(null)}
          onZonesSaved={onZonesSaved}
          onRemove={removeStream}
        />
      ) : reports ? (
        <Reports onOpen={select} note={note} />
      ) : (
        <Feeds streams={streams} live={live} onOpen={select} onAdd={() => setAdding(true)} device={info.device} />
      )}

      {adding && <AddStreamModal onAdd={addStream} onClose={() => setAdding(false)} />}
    </DashboardLayout>
  )
}
