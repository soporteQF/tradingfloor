interface Props {
  title: string
  message: string
  onConfirm: () => void
  onCancel: () => void
  confirmText: string
  confirmVariant?: 'primary' | 'danger'
}

export default function ConfirmModal({ title, message, onConfirm, onCancel, confirmText, confirmVariant = 'danger' }: Props) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3 className="modal-title">{title}</h3>
        <p className="modal-message">{message}</p>
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
          <button className={`btn ${confirmVariant === 'danger' ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm}>
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}