import { useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { reportCsvUrl } from '../api'
import PrintReport from '../components/PrintReport'
import ReportChart, { ChartLegend } from '../components/ReportChart'
import { Period, ReportBar, ReportTable, TotalsStats, rangeLabel, useReport } from '../components/Report'
import { EmptyState } from '../components/ui/States'
import PageHeader from '../components/ui/PageHeader'

export default function Reports({ onOpen, note }) {
  const [minutes, setMinutes] = useState(60)
  const { report, error } = useReport(null, minutes)

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle={report ? <Period report={report} /> : error || 'Loading…'}
      />

      <ReportBar
        minutes={minutes}
        onMinutes={setMinutes}
        csvHref={reportCsvUrl(null, minutes)}
        printName={`iverto-report-all-feeds-${rangeLabel(minutes)}`}
        disabled={!report}
      />

      {report && (
        <div className="report">
          <TotalsStats totals={report.totals} />

          <div className="panel">
            <div className="panel-head">
              <span>Occupancy · all feeds</span>
              <ChartLegend />
            </div>
            {report.series?.length ? (
              <ReportChart data={report.series} from={report.from} to={report.to} />
            ) : (
              <EmptyState icon={BarChart3} title="No samples" text="Nothing was recorded in this period." />
            )}
          </div>

          <div className="panel">
            <div className="panel-head">
              <span>Per feed</span>
            </div>
            <ReportTable feeds={report.feeds} onOpen={onOpen} />
          </div>
        </div>
      )}

      {report && <PrintReport title="All feeds" report={report} note={note} />}
    </>
  )
}
