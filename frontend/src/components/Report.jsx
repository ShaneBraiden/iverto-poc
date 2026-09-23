import { useEffect, useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { api } from '../api'
import { clock, duration, num, percent, stamp } from '../format'

export const RANGES = [15, 60, 360, 1440]
export const rangeLabel = (m) => (m < 60 ? `${m}m` : `${m / 60}h`)

/** Period aggregates for one feed (`name`) or, with name = null, every feed. */
export function useReport(name, minutes, refreshMs = 30000) {
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    const load = () =>
      api
        .report(name, minutes)
        .then((r) => {
          if (!live) return
          setReport(r)
          setError(null)
        })
        .catch((e) => live && setError(e.message))
    load()
    const id = setInterval(load, refreshMs)
    return () => {
      live = false
      clearInterval(id)
    }
  }, [name, minutes, refreshMs])

  return { report, error }
}

/** Print with a useful default filename: browsers name the PDF after the document title. */
function print(name) {
  const previous = document.title
  document.title = name
  const restore = () => {
    document.title = previous
    window.removeEventListener('afterprint', restore)
  }
  window.addEventListener('afterprint', restore)
  window.print()
}

export function ReportBar({ minutes, onMinutes, csvHref, printName, disabled }) {
  return (
    <div className="report-bar">
      <div className="seg">
        {RANGES.map((m) => (
          <button key={m} className={m === minutes ? 'on' : ''} onClick={() => onMinutes(m)}>
            {rangeLabel(m)}
          </button>
        ))}
      </div>
      <div className="spacer" />
      <a className={`btn-secondary${disabled ? ' disabled' : ''}`} href={csvHref} download>
        <Download size={16} />
        CSV
      </a>
      <button className="btn-secondary" onClick={() => print(printName)} disabled={disabled}>
        <FileText size={16} />
        PDF
      </button>
    </div>
  )
}

export function Stat({ label, value, note }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-note">{note || ' '}</div>
    </div>
  )
}

const peakNote = (peak, format = num) => (peak ? `peak ${format(peak.value)} at ${clock(peak.ts)}` : null)

/** One feed's period summary. Every value is an aggregate of stored samples. */
export function ReportStats({ summary: s }) {
  return (
    <div className="stats">
      <Stat label="People avg" value={num(s.people_avg)} note={peakNote(s.people_peak)} />
      <Stat label="Entries" value={s.entries} note={`net ${s.entries - s.exits >= 0 ? '+' : ''}${s.entries - s.exits}`} />
      <Stat label="Exits" value={s.exits} />
      <Stat
        label="Waiting avg"
        value={num(s.area_avg)}
        note={s.area_stay_avg_s != null ? `avg stay ${duration(s.area_stay_avg_s)}` : peakNote(s.area_peak)}
      />
      <Stat label="Queue avg" value={num(s.queue_avg)} note={peakNote(s.queue_peak)} />
      <Stat
        label="Est. wait avg"
        value={duration(s.wait_avg_s)}
        note={peakNote(s.wait_peak_s, duration)}
      />
      <Stat label="Alerts" value={s.alerts} note={Object.keys(s.alerts_by_kind).join(' · ') || null} />
    </div>
  )
}

/** How much of the period this feed was actually analysed - the numbers above are
    aggregates of these samples, so the reader should see how many there were. */
export function Coverage({ summary: s }) {
  return ` · ${percent(s.coverage)} analysed, ${s.samples} samples`
}

/** Facility-wide numbers. Occupancy is summed per second, so the peak is a real head count. */
export function TotalsStats({ totals: t }) {
  return (
    <div className="stats">
      <Stat label="Feeds" value={t.feeds} note={`${t.samples} samples`} />
      <Stat label="People avg" value={num(t.people_avg)} note={peakNote(t.people_peak)} />
      <Stat label="Entries" value={t.entries} />
      <Stat label="Exits" value={t.exits} />
      <Stat label="Net" value={`${t.entries - t.exits >= 0 ? '+' : ''}${t.entries - t.exits}`} />
      <Stat label="Alerts" value={t.alerts} />
    </div>
  )
}

export function ReportTable({ feeds, onOpen }) {
  return (
    <div className="table-scroll">
      <table className="report-table">
        <thead>
          <tr>
            <th>Feed</th>
            <th>People avg</th>
            <th>People peak</th>
            <th>Entries</th>
            <th>Exits</th>
            <th>Waiting avg</th>
            <th>Queue avg</th>
            <th>Est. wait avg</th>
            <th>Alerts</th>
            <th>Analysed</th>
          </tr>
        </thead>
        <tbody>
          {feeds.map(({ name, label, status, summary: s }) => (
            <tr key={name} className={onOpen ? 'clickable' : ''} onClick={onOpen && (() => onOpen(name))}>
              <th scope="row">
                <span className="feed-cell">
                  <span className={`dot ${status}`} />
                  {label}
                </span>
              </th>
              <td>{num(s.people_avg)}</td>
              <td>{s.people_peak ? `${num(s.people_peak.value)} · ${clock(s.people_peak.ts)}` : '—'}</td>
              <td>{s.entries}</td>
              <td>{s.exits}</td>
              <td>{num(s.area_avg)}</td>
              <td>{num(s.queue_avg)}</td>
              <td>{duration(s.wait_avg_s)}</td>
              <td>{s.alerts}</td>
              <td>{percent(s.coverage)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Period({ report }) {
  return (
    <>
      {stamp(report.from)} → {stamp(report.to)}
    </>
  )
}
