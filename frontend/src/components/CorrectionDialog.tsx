import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CorrectionReason } from '../types'

const REASONS: { value: CorrectionReason; label: string }[] = [
  { value: 'wrong_fact', label: 'A fact is wrong' },
  { value: 'missing', label: 'Something is missing' },
  { value: 'wrong_source', label: 'Wrong source cited' },
  { value: 'outdated', label: 'Out of date' },
  { value: 'other', label: 'Something else' },
]

/**
 * Asked when someone marks an answer as needing correction. `kind` alone only
 * records that something was wrong; this is where they say what.
 */
export function CorrectionDialog({ onSubmit, onClose }: {
  onSubmit: (reason: CorrectionReason, note: string) => Promise<void>
  onClose: () => void
}) {
  const [reason, setReason] = useState<CorrectionReason>('wrong_fact')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const boxRef = useRef<HTMLTextAreaElement | null>(null)
  const cardRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => { boxRef.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  const submit = async () => {
    const text = note.trim()
    if (!text || busy) return
    setBusy(true); setError('')
    try { await onSubmit(reason, text); onClose() }
    catch (e) { setError((e as Error).message || 'Could not save this correction'); setBusy(false) }
  }

  return createPortal(
    <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget && !busy) onClose() }}>
      <div className="modal correction-modal" role="dialog" aria-modal="true" aria-labelledby="correction-title" ref={cardRef}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">FEEDBACK</span>
            <h2 id="correction-title">What&rsquo;s wrong with this answer?</h2>
          </div>
          <button className="icon-btn" onClick={onClose} disabled={busy} aria-label="Close">&times;</button>
        </div>
        <p className="modal-intro">Your note is saved against this answer so the corpus can be corrected. Nobody is notified right now.</p>

        <fieldset className="reason-set">
          <legend>What kind of problem is it?</legend>
          <div className="reason-grid">
            {REASONS.map(r => (
              <label key={r.value} className={`reason-chip ${reason === r.value ? 'on' : ''}`}>
                <input type="radio" name="reason" value={r.value} checked={reason === r.value} onChange={() => setReason(r.value)} disabled={busy} />
                <span>{r.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <label className="correction-note">
          Tell us what it should say
          <textarea
            ref={boxRef}
            value={note}
            maxLength={4000}
            rows={5}
            disabled={busy}
            onChange={e => setNote(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void submit() } }}
            placeholder="For example: Bagh Tola has 12 rooms, not 8. The March rate sheet is the current one."
          />
        </label>

        {error && <div className="notice red" role="alert">{error}</div>}

        <div className="modal-actions">
          <span className="modal-hint">{note.trim().length ? `${note.trim().length} characters` : 'A sentence is enough'}</span>
          <button className="ghost-btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="primary-btn compact" onClick={submit} disabled={busy || !note.trim()}>
            {busy ? 'Saving…' : 'Send correction'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
