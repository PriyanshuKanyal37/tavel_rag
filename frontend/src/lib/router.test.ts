import { describe, expect, it } from 'vitest'
import { href, parse, sourceOf, title, withSource } from './router'

const SHA = 'a'.repeat(40)

describe('parse', () => {
  it('reads the three real routes', () => {
    expect(parse('/')).toEqual({ name: 'new', source: undefined })
    expect(parse('/c/42')).toEqual({ name: 'chat', id: 42, source: undefined })
    expect(parse('/saved')).toEqual({ name: 'saved' })
  })

  it('ignores a trailing slash', () => {
    expect(parse('/c/42/')).toMatchObject({ name: 'chat', id: 42 })
    expect(parse('/saved/')).toEqual({ name: 'saved' })
    expect(parse('//')).toMatchObject({ name: 'new' })
  })

  it('treats anything else as not found rather than guessing', () => {
    expect(parse('/nope')).toEqual({ name: 'notFound', path: '/nope' })
    expect(parse('/c/abc')).toMatchObject({ name: 'notFound' })
    expect(parse('/c/')).toMatchObject({ name: 'notFound' })
    expect(parse('/c/1/2')).toMatchObject({ name: 'notFound' })
    // ids start at 1: /c/0 used to look valid and then 404 on load
    expect(parse('/c/0')).toMatchObject({ name: 'notFound' })
    expect(parse('/c/007')).toMatchObject({ name: 'notFound' })
  })

  it('reads a deep-linked source', () => {
    expect(parse('/c/7', `?source=${SHA}&page=3`)).toEqual({
      name: 'chat', id: 7, source: { sha1: SHA, page: 3 },
    })
  })

  it('defaults a missing or junk page to 1', () => {
    expect(sourceOf(parse('/c/7', `?source=${SHA}`))).toEqual({ sha1: SHA, page: 1 })
    expect(sourceOf(parse('/c/7', `?source=${SHA}&page=abc`))).toEqual({ sha1: SHA, page: 1 })
    expect(sourceOf(parse('/c/7', `?source=${SHA}&page=-4`))).toEqual({ sha1: SHA, page: 1 })
  })

  it('refuses a source id that is not a sha1', () => {
    expect(sourceOf(parse('/c/7', '?source=../../etc/passwd'))).toBeUndefined()
    expect(sourceOf(parse('/c/7', '?source=123'))).toBeUndefined()
  })
})

describe('href', () => {
  it('round-trips every route', () => {
    for (const path of ['/', '/c/42', '/saved']) {
      expect(href(parse(path))).toBe(path)
    }
  })

  it('round-trips a source deep link', () => {
    const url = `/c/7?source=${SHA}&page=2`
    expect(href(parse('/c/7', `?source=${SHA}&page=2`))).toBe(url)
  })
})

describe('title', () => {
  it('names the conversation in the tab', () => {
    expect(title({ name: 'chat', id: 1 }, 'Pool properties')).toBe('Pool properties · Travel Inn Knowledge Assistant')
  })

  it('falls back when a conversation has no title yet', () => {
    expect(title({ name: 'chat', id: 1 }, null)).toContain('Conversation')
    expect(title({ name: 'chat', id: 1 }, '   ')).toContain('Conversation')
  })

  it('names the other views', () => {
    expect(title({ name: 'saved' })).toContain('Saved answers')
    expect(title({ name: 'new' })).toBe('Travel Inn Knowledge Assistant')
    expect(title({ name: 'notFound', path: '/x' })).toContain('Not found')
  })
})

describe('withSource', () => {
  it('attaches and removes a source on a conversation', () => {
    const open = withSource(parse('/c/9'), { sha1: SHA, page: 4 })
    expect(href(open)).toBe(`/c/9?source=${SHA}&page=4`)
    expect(href(withSource(open, undefined))).toBe('/c/9')
  })

  it('leaves routes that cannot carry one alone', () => {
    expect(withSource(parse('/saved'), { sha1: SHA, page: 1 })).toEqual({ name: 'saved' })
  })
})
