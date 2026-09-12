import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { CorrectionReason } from '../types'
import { CorrectionDialog } from './CorrectionDialog'

type AnswerActionsProps = {
  answerId: string
  text: string
  sessionId?: number | null
  saved: boolean
  /** False while an answer is still streaming: its id changes once saved. */
  canSave?: boolean
  onSavedChange: () => void | Promise<void>
}

/**
 * Saving and feedback are workspace state, not browser state: both go to the
 * database so the team sees the same list from any machine. `saved` is owned by
 * the caller, so a card and the Saved view can never disagree.
 */
export function AnswerActions({ answerId, text, sessionId = null, saved, canSave = true, onSavedChange }: AnswerActionsProps) {
  const [copied, setCopied] = useState(false)
  const [status, setStatus] = useState('')
  const statusTimer = useRef<number | undefined>(undefined)
  // Say what happened, then get out of the way.
  const announce = (message: string) => {
    setStatus(message)
    window.clearTimeout(statusTimer.current)
    statusTimer.current = window.setTimeout(() => setStatus(''), 2600)
  }
  useEffect(() => () => window.clearTimeout(statusTimer.current), [])
  const [busy, setBusy] = useState(false)
  const [flagged, setFlagged] = useState(false)
  const [asking, setAsking] = useState(false)

  const copyAnswer = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(text)
      setCopied(true)
      announce('Copied')
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      announce('Could not copy answer')
    }
  }

  const toggleSaved = async () => {
    if (busy) return
    setBusy(true)
    try {
      if (saved) await api.unsaveAnswer(answerId)
      else await api.saveAnswer({ id: answerId, text, session_id: sessionId })
      announce(saved ? 'Answer removed from saved' : 'Answer saved')
      await onSavedChange()
    } catch (e) {
      announce((e as Error).message || 'Could not update saved answers')
    } finally {
      setBusy(false)
    }
  }

  const sendCorrection = async (reason: CorrectionReason, note: string) => {
    await api.feedback({ answer_id: answerId, kind: 'correction', reason, note })
    setFlagged(true)
    announce('Correction saved')
  }

  const clearCorrection = async () => {
    if (busy) return
    setBusy(true)
    try { await api.clearFeedback(answerId); setFlagged(false); announce('Correction removed') }
    catch (e) { announce((e as Error).message || 'Could not remove the correction') }
    finally { setBusy(false) }
  }

  return (
    <div className="answer-tools" aria-label="Answer actions">
      <button type="button" onClick={copyAnswer}>{copied ? 'Copied' : 'Copy'}</button>
      {canSave && <button type="button" onClick={toggleSaved} aria-pressed={saved} disabled={busy}>{saved ? 'Unsave answer' : 'Save answer'}</button>}
      <button type="button" onClick={() => flagged ? void clearCorrection() : setAsking(true)} aria-pressed={flagged} disabled={busy}>
        {flagged ? 'Correction sent' : 'Needs correction'}
      </button>
      <span className="answer-status" role="status" aria-live="polite">{status}</span>
      {asking && <CorrectionDialog onSubmit={sendCorrection} onClose={() => setAsking(false)} />}
    </div>
  )
}
