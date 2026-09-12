import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

/**
 * A RAG over property documents answers almost every question with a number:
 * room counts, depths, distances, rates. None of them may be mangled.
 */
describe('renderMarkdown with numbers in the prose', () => {
  const CASES = [
    'It has 12 rooms.',
    'Bagh Tola has 12 rooms and 4 cottages.',
    'The pool is 4 ft deep and sleeps 2 guests.',
    'Rates start from 24000 per night for 2 adults.',
    'Located 60 km (a 2-hour drive) from Kaziranga.',
    'Approximately 70% of the park\'s 350 bird species are found here.',
    '- 🛏️ **Kathoni** has 2 rooms [3].',
    '31 properties have a pool.',
  ]

  for (const text of CASES) {
    it(`keeps every number in: ${text.slice(0, 46)}`, () => {
      const html = renderMarkdown(text)
      expect(html).not.toContain('undefined')
      for (const n of text.match(/\d+/g) || []) {
        expect(html).toContain(n)
      }
    })
  }

  it('still restores inline code when numbers sit beside it', () => {
    const html = renderMarkdown('Set `has_pool` to true for all 12 rooms.')
    expect(html).toContain('<code>has_pool</code>')
    expect(html).toContain('12')
    expect(html).not.toContain('undefined')
  })

  it('handles several code spans in one line', () => {
    const html = renderMarkdown('Use `a` and `b` and `c` together.')
    expect(html).toContain('<code>a</code>')
    expect(html).toContain('<code>b</code>')
    expect(html).toContain('<code>c</code>')
    expect(html).not.toContain('undefined')
  })
})
