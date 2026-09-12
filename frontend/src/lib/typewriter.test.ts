import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { STEP_MS, revealStep, useTypewriter } from './typewriter'

const TEXT = 'x'.repeat(900)
// One timeout is scheduled per commit, so the clock has to be advanced once
// per frame -- a single large jump fires only the one timer already pending.
const frames = (n: number) => { for (let i = 0; i < n; i++) act(() => { vi.advanceTimersByTime(STEP_MS) }) }

describe('useTypewriter', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('reveals nothing before the first frame', () => {
    const { result } = renderHook(() => useTypewriter(TEXT, true))
    expect(result.current).toBe('')
  })

  it('grows in many small paints rather than one jump', () => {
    const { result } = renderHook(() => useTypewriter(TEXT, true))
    const seen = new Set<number>()
    for (let i = 0; i < 200; i++) { frames(1); seen.add(result.current.length) }
    expect(seen.size).toBeGreaterThan(30)
  })

  it('finishes a long answer in about a second', () => {
    const { result } = renderHook(() => useTypewriter(TEXT, true))
    frames(400)
    expect(result.current).toBe(TEXT)
  })

  // A short answer must not take the same second a long one does.
  it('is length-independent: the step shrinks with the gap', () => {
    expect(revealStep(0, 900)).toBe(15)
    expect(revealStep(890, 900)).toBe(1)
    expect(revealStep(900, 900)).toBe(1)
  })

  it('snaps to the whole text the moment the stream ends', () => {
    const { rerender, result } = renderHook(({ t, l }) => useTypewriter(t, l),
      { initialProps: { t: TEXT, l: true } })
    frames(3)
    expect(result.current.length).toBeLessThan(TEXT.length)
    rerender({ t: TEXT, l: false })
    expect(result.current).toBe(TEXT)
  })

  it('resets when the next question clears the answer', () => {
    const { rerender, result } = renderHook(({ t, l }) => useTypewriter(t, l),
      { initialProps: { t: TEXT, l: true } })
    frames(400)
    rerender({ t: '', l: true })
    expect(result.current).toBe('')
    rerender({ t: 'new answer', l: true })
    frames(60)
    expect(result.current).toBe('new answer')
  })

  it('keeps up when more text arrives mid-reveal', () => {
    const { rerender, result } = renderHook(({ t, l }) => useTypewriter(t, l),
      { initialProps: { t: 'first half. ', l: true } })
    frames(60)
    expect(result.current).toBe('first half. ')
    rerender({ t: 'first half. second half.', l: true })
    frames(120)
    expect(result.current).toBe('first half. second half.')
  })
})
