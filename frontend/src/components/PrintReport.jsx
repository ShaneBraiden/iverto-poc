import { createPortal } from 'react-dom'
import { clockSeconds, duration, num, percent, stamp } from '../format'
import Logo from './Logo'
import ReportChart, { ChartLegend } from './ReportChart'

// A4 portrait minus the 14 mm page margins, at 96 dpi. The chart needs an explicit
// size because the sheet has no layout to measure until the print dialog opens.
const SHEET_W = 680

const ROWS = [
  ['People avg', (s) => num(s.people_avg)],
  ['People peak', (s) => (s.people_peak ? `${num(s.people_peak.value)} at ${clockSeconds(s.people_peak.ts)}` : '—')],
  ['Entries', (s) => s.entries],
  ['Exits', (s) => s.exits],
  ['Net', (s) => (s.entries - s.exits >= 0 ? '+' : '') + (s.entries - s.exits)],
  ['Waiting area avg', (s) => num(s.area_avg)],
  ['Waiting area peak', (s) => (s.area_peak ? num(s.area_peak.value) : '—')],
  ['Waiting area avg stay', (s) => duration(s.area_stay_avg_s)],
  ['Queue avg', (s) => num(s.queue_avg)],
  ['Queue peak', (s) => (s.queue_peak ? `${num(s.queue_peak.value)} at ${clockSeconds(s.queue_peak.ts)}` : '—')],
  ['Est. wait avg', (s) => duration(s.wait_avg_s)],
  ['Est. wait peak', (s) => (s.wait_peak_s ? duration(s.wait_peak_s.value) : '—')],
  ['Service time avg', (s) => duration(s.dwell_avg_s)],
  ['Alerts', (s) => s.alerts],
  ['Period analysed', (s) => `${percent(s.coverage)} · ${s.samples} samples`],
]

function allEvents(feeds, multi) {
  return feeds
    .flatMap((f) => (f.events ?? []).map((e) => ({ ...e, feed: multi ? f.label : null })))
    .sort((a, b) => b.ts - a.ts)
    .slice(0, 25)
}

/** The printable report sheet: hidden on screen, laid out for A4 when printed
    (the browser's own "Save as PDF" is the export). */
export function PrintSheet({ title, report, note }) {
  const feeds = report.feeds ?? []
  const multi = feeds.length > 1
  const series = report.series ?? feeds[0]?.series ?? []
  const events = allEvents(feeds, multi)
  const t = report.totals

  return (
    <article className="print-sheet">
      <header className="print-head">
        <span className="print-mark">
          <Logo size={22} />
        </span>
        <div>
          <div className="print-brand">
            iverto<span>.ai</span>
          </div>
          <div className="print-sub">Crowd &amp; Queue Analytics</div>
        </div>
        <div className="print-meta">
          <div className="print-title">{title}</div>
          <div>
            {stamp(report.from)} → {stamp(report.to)}
          </div>
          <div>Generated {stamp(report.generated)}</div>
        </div>
      </header>

      {multi && (
        <section className="print-block">
          <h2>All feeds</h2>
          <dl className="print-pairs">
            <div>
              <dt>Feeds</dt>
              <dd>{t.feeds}</dd>
            </div>
            <div>
              <dt>People avg</dt>
              <dd>{num(t.people_avg)}</dd>
            </div>
            <div>
              <dt>People peak</dt>
              <dd>{t.people_peak ? `${num(t.people_peak.value)} at ${clockSeconds(t.people_peak.ts)}` : '—'}</dd>
            </div>
            <div>
              <dt>Entries</dt>
              <dd>{t.entries}</dd>
            </div>
            <div>
              <dt>Exits</dt>
              <dd>{t.exits}</dd>
            </div>
            <div>
              <dt>Alerts</dt>
              <dd>{t.alerts}</dd>
            </div>
          </dl>
        </section>
      )}

      {series.length > 0 && (
        <section className="print-block">
          <h2>
            Occupancy
            <ChartLegend />
          </h2>
          <ReportChart data={series} from={report.from} to={report.to} width={SHEET_W} height={200} />
        </section>
      )}

      {multi ? (
        <section className="print-block">
          <h2>Per feed</h2>
          <table className="print-table">
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
              {feeds.map(({ name, label, summary: s }) => (
                <tr key={name}>
                  <th scope="row">{label}</th>
                  <td>{num(s.people_avg)}</td>
                  <td>{s.people_peak ? num(s.people_peak.value) : '—'}</td>
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
        </section>
      ) : (
        feeds.map((f) => (
          <section className="print-block" key={f.name}>
            <h2>{f.label}</h2>
            <table className="print-table print-pairs-table">
              <tbody>
                {ROWS.map(([label, value]) => (
                  <tr key={label}>
                    <th scope="row">{label}</th>
                    <td>{value(f.summary)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))
      )}

      <section className="print-block">
        <h2>Alerts</h2>
        {events.length === 0 ? (
          <p className="print-none">Nothing went over a limit in this period.</p>
        ) : (
          <table className="print-table">
            <thead>
              <tr>
                <th>Time</th>
                {multi && <th>Feed</th>}
                <th>Alert</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={`${e.ts}-${e.feed}-${e.kind}`}>
                  <td>{stamp(e.ts)}</td>
                  {multi && <td>{e.feed}</td>}
                  <td>{e.message}</td>
                  <td>{num(e.value, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <footer className="print-foot">
        Every value is aggregated from per-second samples measured by the live pipeline.
        {note ? ` ${note}` : ''}
      </footer>
    </article>
  )
}

/** Mounted into <body>, outside the dashboard shell, so the print stylesheet can
    hide everything else on the page and leave just this sheet. */
export default function PrintReport(props) {
  return createPortal(<PrintSheet {...props} />, document.body)
}
