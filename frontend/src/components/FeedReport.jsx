import { useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { reportCsvUrl } from '../api'
import PrintReport from './PrintReport'
import ReportChart, { ChartLegend } from './ReportChart'
import { Coverage, Period, ReportBar, ReportStats, rangeLabel, useReport } from './Report'
import { EmptyState } from './ui/States'

/** The tiles above this show "right now"; this section shows the same metrics
    aggregated over a period, and exports them as CSV or PDF. */
export default function FeedReport({ name, label }) {
  const [minutes, setMinutes] = useState(60)
  const { report, error } = useReport(name, minutes)
  const feed = report?.feeds?.[0]

  return (
    <section className="report">
      <div className="panel-head report-head">
        <span>Report</span>
        <span className="report-period">
          {report ? (
            <>
              <Period report={report} />
              {feed && <Coverage summary={feed.summary} />}
            </>
          ) : (
            error || 'Loading…'
          )}
        </span>
      </div>

      <ReportBar
        minutes={minutes}
        onMinutes={setMinutes}
        csvHref={reportCsvUrl(name, minutes, 'samples')}
        printName={`iverto-report-${name}-${rangeLabel(minutes)}`}
        disabled={!report}
      />

      {feed && (
        <>
          <ReportStats summary={feed.summary} />
          <div className="panel">
            <div className="panel-head">
              <span>Occupancy · {rangeLabel(minutes)}</span>
              <ChartLegend />
            </div>
            {feed.series?.length ? (
              <ReportChart data={feed.series} from={report.from} to={report.to} />
            ) : (
              <EmptyState icon={BarChart3} title="No samples" text="Nothing was recorded in this period." />
            )}
          </div>
          <PrintReport title={label} report={report} />
        </>
      )}
    </section>
  )
}
