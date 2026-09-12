import { describe, expect, it } from 'vitest'
import { humanise } from './errors'

describe('humanise', () => {
  it('turns the provider quota dict into something a salesperson can act on', () => {
    const raw = "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Your project has exceeded its monthly spending cap. Please go to AI Studio at https://ai.studio/spend to manage your project spend cap.', 'status': 'RESOURCE_EXHAUSTED'}}"
    const out = humanise(raw)
    expect(out).toContain('monthly spending cap')
    expect(out).not.toContain('{')
    expect(out).not.toContain("'code'")
    expect(out).not.toContain('RESOURCE_EXHAUSTED')
  })

  it('separates a rate limit from a spending cap', () => {
    expect(humanise('429 RESOURCE_EXHAUSTED: rate limit')).toContain('rate limited')
    expect(humanise('exceeded its monthly spending cap')).toContain('spending cap')
  })

  it('explains an expired session', () => {
    expect(humanise('sign in first')).toContain('Sign in again')
    expect(humanise('Request failed (401)')).toContain('Sign in again')
  })

  it('explains an overloaded model and a timeout', () => {
    expect(humanise('503 UNAVAILABLE: model overloaded')).toContain('busy')
    expect(humanise('DEADLINE_EXCEEDED')).toContain('too long')
  })

  it('explains an unreachable backend', () => {
    expect(humanise('Failed to fetch')).toContain('backend is running')
  })

  it('keeps an unknown message rather than inventing a meaning', () => {
    expect(humanise('The working set could not be compacted')).toBe('The working set could not be compacted.')
  })

  it('trims a dict off an unknown failure instead of showing it', () => {
    const out = humanise("Something odd. {'detail': {'a': 1}}")
    expect(out).toBe('Something odd.')
  })

  it('never returns an empty string', () => {
    expect(humanise('')).toBeTruthy()
    expect(humanise(undefined)).toBeTruthy()
    expect(humanise(null)).toBeTruthy()
  })
})

describe('messages we wrote ourselves', () => {
  it('keeps the whole throttle message, including the seconds', () => {
    const said = 'Too many questions at once. Try again in 42 seconds.'
    expect(humanise(said)).toBe(said)
  })

  it('still translates a provider 429 into something actionable', () => {
    expect(humanise("429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}"))
      .toMatch(/rate limited/i)
  })

  it('puts the spending cap ahead of the generic rate-limit rule', () => {
    expect(humanise("429 RESOURCE_EXHAUSTED. {'message': 'exceeded its monthly spending cap'}"))
      .toMatch(/spending cap/i)
  })
})

