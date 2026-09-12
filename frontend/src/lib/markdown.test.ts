import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('renders headings, bullets and numbered lists', () => {
    const html = renderMarkdown('## Matches\n- **Bagh Tola** pool [1]\n- **Kinwani** pool [2]')
    expect(html).toContain('<h3>Matches</h3>')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>')
    expect(html).toContain('<strong>Bagh Tola</strong>')
    expect(html).toContain('data-citation="1"')
  })

  it('keeps numbered lists ordered and separate from bullets', () => {
    const html = renderMarkdown('1. First\n2. Second\n\n- Bullet')
    expect(html).toContain('<ol>')
    expect(html).toContain('<ul>')
    expect(html.indexOf('<ol>')).toBeLessThan(html.indexOf('<ul>'))
  })

  it('leaves emoji and plain prose intact', () => {
    expect(renderMarkdown('🏊 Three properties have a pool.')).toContain('🏊 Three properties have a pool.')
  })

  // The payloads below must end up as visible TEXT, never as live nodes, so the
  // check parses the result instead of matching on escaped substrings.
  const dom = (html: string) => {
    const host = document.createElement('div')
    host.innerHTML = html
    return host
  }

  it('never creates a live node outside the allowlist', () => {
    const host = dom(renderMarkdown('<img src=x onerror=alert(1)> <script>alert(1)</script> <iframe src=//evil></iframe>'))
    expect(host.querySelector('img')).toBeNull()
    expect(host.querySelector('script')).toBeNull()
    expect(host.querySelector('iframe')).toBeNull()
    expect(host.textContent).toContain('<img src=x onerror=alert(1)>')
  })

  it('does not let a document smuggle an anchor or a handler through', () => {
    const host = dom(renderMarkdown('**bold** <a href="http://evil" onclick="x()">click</a>'))
    expect(host.querySelector('strong')?.textContent).toBe('bold')
    expect(host.querySelector('a')).toBeNull()
    expect(host.querySelectorAll('*').length).toBeGreaterThan(0)
    for (const el of host.querySelectorAll('*')) {
      for (const attr of el.getAttributeNames()) {
        expect(attr.startsWith('on')).toBe(false)
        expect(['href', 'src', 'style', 'formaction']).not.toContain(attr)
      }
    }
  })

  it('only ever emits the citation button as an interactive element', () => {
    const host = dom(renderMarkdown('- **A** pool [1]\n- **B** pool [2]'))
    for (const el of host.querySelectorAll('button')) {
      expect(el.className).toBe('inline-citation')
      expect(el.getAttribute('data-citation')).toMatch(/^\d+$/)
    }
    expect(host.querySelectorAll('button')).toHaveLength(2)
  })

  it('renders inline code without re-parsing its contents', () => {
    const html = renderMarkdown('Use `**not bold**` here')
    expect(html).toContain('<code>**not bold**</code>')
    expect(html).not.toContain('<strong>not bold</strong>')
  })

  it('treats a blank line as a paragraph break', () => {
    const html = renderMarkdown('One line.\n\nAnother line.')
    expect(html.match(/<p>/g)).toHaveLength(2)
  })

  it('survives empty and undefined input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(undefined as unknown as string)).toBe('')
  })
})
