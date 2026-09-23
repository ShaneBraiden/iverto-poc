import { useEffect, useState } from 'react'
import { FileBarChart, LayoutGrid, PanelLeftClose, PanelLeftOpen, Plus } from 'lucide-react'
import Logo from '../components/Logo'

const KEY = 'iverto.sidebar.collapsed'

export default function DashboardLayout({
  streams,
  live,
  selected,
  reports,
  onSelect,
  onReports,
  onAdd,
  footNote,
  children,
}) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(KEY) === '1')
  useEffect(() => localStorage.setItem(KEY, collapsed ? '1' : '0'), [collapsed])

  return (
    <div className={`shell${collapsed ? ' collapsed' : ''}`}>
      <nav className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Logo size={18} />
          </span>
          <span className="brand-text">
            <div className="brand-name">
              iverto<span>.ai</span>
            </div>
            <div className="brand-sub">Crowd &amp; Queue Analytics</div>
          </span>
        </div>

        <button className={`nav-item${selected == null && !reports ? ' on' : ''}`} onClick={() => onSelect(null)}>
          <LayoutGrid size={16} />
          <span className="nav-label">All feeds</span>
          <span className="nav-meta">{streams.length}</span>
        </button>

        <button className={`nav-item${reports ? ' on' : ''}`} onClick={onReports}>
          <FileBarChart size={16} />
          <span className="nav-label">Reports</span>
        </button>

        <div className="nav-group">Feeds</div>
        <div className="nav-list scrollbar-none">
          {streams.map((s) => {
            const state = live?.[s.name]
            return (
              <button
                key={s.name}
                className={`nav-item${selected === s.name ? ' on' : ''}`}
                onClick={() => onSelect(s.name)}
                title={s.label}
              >
                <span className={`dot ${state?.status ?? 'connecting'}`} />
                <span className="nav-label">{s.label}</span>
                <span className="nav-meta">{state?.metrics?.people ?? '—'}</span>
              </button>
            )
          })}
        </div>

        <div className="sidebar-foot">
          <button className="btn-primary" onClick={onAdd} title="Add stream">
            <Plus size={16} />
            <span className="btn-label">Add stream</span>
          </button>
          <button className="icon-btn" onClick={() => setCollapsed((c) => !c)} aria-label="Toggle sidebar">
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
          {footNote && <div className="sidebar-note">{footNote}</div>}
        </div>
      </nav>

      <main className="content">{children}</main>
    </div>
  )
}
