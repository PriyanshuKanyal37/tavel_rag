import { describe, expect, it } from 'vitest'

/**
 * The same rule the backend applies, repeated at render time so turns saved
 * before the rule existed also show only what they cited.
 * Mirrors citedSources() in App.tsx.
 */
function citedSources(text: string | undefined, refs: { n?: number; sha1: string }[] | undefined) {
  const all = (refs || []).map((r, i) => ({ ...r, n: r.n ?? i + 1 }))
  if (!all.length) return []
  const wanted: number[] = []
  for (const m of (text || '').matchAll(/\[(\d{1,3})\]/g)) {
    const n = Number(m[1])
    if (!wanted.includes(n)) wanted.push(n)
  }
  if (!wanted.length) return []
  const picked = wanted.map(n => all.find(s => s.n === n) || all[n - 1]).filter(Boolean)
  return picked.length ? picked : all
}

const pool = (n: number) => Array.from({ length: n }, (_, i) => ({ sha1: `s${i + 1}` }))

describe('evidence shown for a turn', () => {
  it('shows only what an old stored turn actually cited', () => {
    // a turn saved before the rule: 31 sources on the row, two markers in the text
    const out = citedSources('Kinwani is in Rishikesh [1], a 6-hour drive [2].', pool(31))
    expect(out).toHaveLength(2)
    expect(out.map(s => s.sha1)).toEqual(['s1', 's2'])
  })

  it('shows nothing when the answer cited nothing', () => {
    expect(citedSources('We do not have any properties in Dehradun.', pool(31))).toEqual([])
  })

  it('lists a repeated citation once', () => {
    expect(citedSources('A [3], again [3], once more [3].', pool(10))).toHaveLength(1)
  })

  it('keeps the order the answer used them in', () => {
    expect(citedSources('First [7] then [2].', pool(10)).map(s => s.sha1)).toEqual(['s7', 's2'])
  })

  it('ignores a citation with no matching source', () => {
    expect(citedSources('Real [2], invented [45].', pool(5)).map(s => s.sha1)).toEqual(['s2'])
  })

  it('respects backend numbering when it is already filtered', () => {
    const backend = [{ sha1: 'sA', n: 1 }, { sha1: 'sB', n: 2 }]
    expect(citedSources('Uses [1] and [2].', backend).map(s => s.sha1)).toEqual(['sA', 'sB'])
  })

  it('returns nothing rather than everything when there are no sources at all', () => {
    expect(citedSources('Cites [1].', [])).toEqual([])
  })
})
