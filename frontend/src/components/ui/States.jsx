export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{Icon && <Icon size={22} />}</span>
      <span className="empty-title">{title}</span>
      {text && <span className="empty-text">{text}</span>}
      {action}
    </div>
  )
}

export function CenteredSpinner() {
  return (
    <div className="centered-spinner">
      <span className="spinner" role="status" aria-label="Loading" />
    </div>
  )
}
