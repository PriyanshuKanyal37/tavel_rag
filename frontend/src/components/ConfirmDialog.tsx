import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

/**
 * Themed stand-in for window.confirm, which paints the browser's own grey box
 * over the product. Portalled to the body for the same reason the other
 * dialogs are: an ancestor with its own stacking context used to trap them.
 */
export function ConfirmDialog({ title, body, confirmLabel, danger, onConfirm, onClose }: {
  title: string
  body: string
  confirmLabel: string
  danger?: boolean
  onConfirm: () => Promise<void> | void
  onClose: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const okRef = useRef<HTMLButtonElement | null>(null)

  // window.confirm focuses OK, so this does too: the keyboard path is unchanged.
  useEffect(() => { okRef.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  const go = async () => {
    if (busy) return
    setBusy(true); setError('')
    try { await onConfirm(); onClose() }
    catch (e) { setError((e as Error).message || 'That did not work.'); setBusy(false) }
  }

  return createPortal(
    <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget && !busy) onClose() }}>
      <div className="modal confirm-modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-body">
        <div className="modal-head">
          <h2 id="confirm-title">{title}</h2>
          <button className="icon-btn" onClick={onClose} disabled={busy} aria-label="Close">&times;</button>
        </div>
        <p className="modal-intro" id="confirm-body">{body}</p>
        {error && <div className="notice red" role="alert">{error}</div>}
        <div className="modal-actions">
          <span className="modal-hint" />
          <button className="ghost-btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button ref={okRef} className={`primary-btn compact ${danger ? 'danger' : ''}`} onClick={go} disabled={busy}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
