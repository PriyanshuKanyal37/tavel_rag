import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnswerActions } from './AnswerActions'
import { api } from '../lib/api'

vi.mock('../lib/api', () => ({
  api: {
    saveAnswer: vi.fn().mockResolvedValue({ ok: true }),
    unsaveAnswer: vi.fn().mockResolvedValue({ ok: true }),
    feedback: vi.fn().mockResolvedValue({ ok: true }),
    clearFeedback: vi.fn().mockResolvedValue({ ok: true }),
  },
}))

const props = { answerId: '7:2', text: 'Bagh Tola has family rooms.', sessionId: 7 }

beforeEach(() => vi.clearAllMocks())

describe('AnswerActions', () => {
  it('saves an unsaved answer to the workspace, not the browser', async () => {
    const onSavedChange = vi.fn()
    render(<AnswerActions {...props} saved={false} onSavedChange={onSavedChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Save answer' }))
    expect(api.saveAnswer).toHaveBeenCalledWith({ id: '7:2', text: props.text, session_id: 7 })
    expect(onSavedChange).toHaveBeenCalled()
    expect(await screen.findByRole('status')).toHaveTextContent('Answer saved')
  })

  it('removes an answer that is already saved', async () => {
    const onSavedChange = vi.fn()
    render(<AnswerActions {...props} saved onSavedChange={onSavedChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Unsave answer' }))
    expect(api.unsaveAnswer).toHaveBeenCalledWith('7:2')
    expect(onSavedChange).toHaveBeenCalled()
  })

  it('reports a failed save instead of showing it as saved', async () => {
    vi.mocked(api.saveAnswer).mockRejectedValueOnce(new Error('Request failed (500)'))
    const onSavedChange = vi.fn()
    render(<AnswerActions {...props} saved={false} onSavedChange={onSavedChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Save answer' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Request failed (500)')
    expect(onSavedChange).not.toHaveBeenCalled()
  })

  it('asks what is wrong before recording anything', async () => {
    render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Helpful' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Needs correction' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(api.feedback).not.toHaveBeenCalled()
  })

  it('will not submit an empty correction', async () => {
    render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Needs correction' }))
    expect(screen.getByRole('button', { name: 'Send correction' })).toBeDisabled()
    expect(api.feedback).not.toHaveBeenCalled()
  })

  it('saves the note and the chosen category', async () => {
    render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Needs correction' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Out of date' }))
    await userEvent.type(screen.getByRole('textbox'), 'The March rate sheet is current.')
    await userEvent.click(screen.getByRole('button', { name: 'Send correction' }))
    expect(api.feedback).toHaveBeenCalledWith({
      answer_id: '7:2', kind: 'correction', reason: 'outdated',
      note: 'The March rate sheet is current.',
    })
    expect(await screen.findByRole('button', { name: 'Correction sent' })).toBeInTheDocument()
  })

  it('keeps the dialog open and reports a failed save', async () => {
    vi.mocked(api.feedback).mockRejectedValueOnce(new Error('Request failed (500)'))
    render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Needs correction' }))
    await userEvent.type(screen.getByRole('textbox'), 'wrong room count')
    await userEvent.click(screen.getByRole('button', { name: 'Send correction' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed (500)')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('closes the dialog without saving when cancelled', async () => {
    render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Needs correction' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(api.feedback).not.toHaveBeenCalled()
  })

  it('clears the status message instead of leaving it on screen', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const writeText = vi.fn().mockResolvedValue(undefined)
      Object.assign(navigator, { clipboard: { writeText } })
      render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
      await userEvent.click(screen.getByRole('button', { name: 'Copy' }))
      expect(await screen.findByRole('status')).toHaveTextContent('Copied')
      await vi.advanceTimersByTimeAsync(3000)
      expect(screen.getByRole('status')).toHaveTextContent('')
    } finally {
      vi.useRealTimers()
    }
  })

  it('offers no Save button while the answer is still streaming', () => {
    render(<AnswerActions {...props} saved={false} canSave={false} onSavedChange={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Save answer|Unsave answer/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Copy' })).toBeInTheDocument()
  })

  it('copies the answer text to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    render(<AnswerActions {...props} saved={false} onSavedChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Copy' }))
    expect(writeText).toHaveBeenCalledWith(props.text)
    expect(await screen.findByRole('status')).toHaveTextContent('Copied')
  })
})
