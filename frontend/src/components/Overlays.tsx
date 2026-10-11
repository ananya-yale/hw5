import { useEffect } from 'react'
import { BulldogFace } from './Bulldog'

export interface Toast {
  id: number
  tone: 'good' | 'bad' | 'info'
  text: string
}

export function Toasts({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <button key={t.id} className={`toast tone-${t.tone}`} onClick={() => onDismiss(t.id)}>
          {t.text}
        </button>
      ))}
    </div>
  )
}

interface ModalProps {
  title: string
  children: React.ReactNode
  confirmLabel: string
  tone?: 'primary' | 'danger'
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({ title, children, confirmLabel, tone = 'primary', busy, onConfirm, onCancel }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCancel()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <BulldogFace size={52} />
        <h2>{title}</h2>
        <div className="modal-body">{children}</div>
        <div className="modal-actions">
          <button className="btn ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button className={`btn ${tone === 'danger' ? 'danger' : 'primary'}`} onClick={onConfirm} disabled={busy} autoFocus>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
