// Responsive + contrast regression check.
// Run: npm run build && TI_PASSWORD=... npm run test:ui  (starts its own preview server)
// There is no demo mode: this signs in to the real backend like a person would.
// Guards: no horizontal overflow at any width, mobile drawers open/close,
// and every sampled text style meets WCAG AA in both themes.
import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { setTimeout as sleep } from 'node:timers/promises'

const PORT = 5174
const PASSWORD = process.env.TI_PASSWORD
if (!PASSWORD) { console.error('set TI_PASSWORD to the workspace password'); process.exit(2) }
const URL = `http://127.0.0.1:${PORT}/`

const WIDTHS = [[1440, 900], [1280, 820], [1024, 720], [768, 1024], [390, 844], [320, 640], [740, 400]]
const SAMPLES = ['.answer', '.turn-meta', '.inline-citation', '.crumb strong', '.history-item small',
  '.composer textarea', '.composer-meta span', '.sources-btn', '.evidence-intro', '.chat-statusbar',
  '.source-body small', '.side-label', '.turn.user p']

const relLum = ([r, g, b]) => {
  const f = c => (c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
const contrast = (a, b) => { const [hi, lo] = [relLum(a), relLum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05) }
const toRgb = s => s.match(/\d+/g).slice(0, 3).map(Number)

async function signIn(page) {
  if (await page.locator('input[type=password]').count()) {
    await page.fill('input[type=password]', PASSWORD)
    await page.click('.primary-btn')
  }
  await page.waitForSelector('.workspace', { timeout: 20000 })
  await page.waitForTimeout(400)
}

const fails = []
const check = (ok, label) => { if (!ok) fails.push(label); console.log(`${ok ? 'ok  ' : 'FAIL'}  ${label}`) }

const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(PORT)], { stdio: 'ignore' })
try {
  for (let i = 0; i < 40; i++) {
    try { await fetch(URL); break } catch { await sleep(250) }
  }
  const browser = await chromium.launch()

  for (const [width, height] of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width, height } })
    const page = await ctx.newPage()
    const errors = []
    page.on('pageerror', e => errors.push(e.message))
    page.on('console', m => { const t = m.text(); if (m.type() === 'error' && !/401|Unauthorized/.test(t)) errors.push(t) })
    await page.goto(URL, { waitUntil: 'networkidle' })
    await signIn(page)
    const m = await page.evaluate(() => ({ scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth }))
    check(m.scrollW <= m.clientW, `${width}x${height}: no horizontal page overflow (${m.scrollW} <= ${m.clientW})`)
    check(errors.length === 0, `${width}x${height}: no console errors ${errors[0] || ''}`)
    await ctx.close()
  }

  // Mobile drawers: scrim opens with them and dismisses them.
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const page = await ctx.newPage()
  await page.goto(URL, { waitUntil: 'networkidle' })
  await signIn(page)
  // deterministic titles for the search check; removed again at the end
  // a token unique to this run, so leftovers from an earlier run cannot match
  const tag = `zz${Date.now().toString(36)}`
  const made = await page.evaluate(async t => {
    const ids = []
    for (const title of [`Monsoon ${t} access`, `Kanha ${t} stays`]) {
      const r = await fetch('/api/chat/sessions', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) })
      ids.push((await r.json()).id)
    }
    return ids
  }, tag)
  await page.reload({ waitUntil: 'networkidle' })
  await signIn(page)
  check(await page.locator('.sidebar:not(.collapsed)').count() === 0, 'mobile: sidebar starts closed')
  await page.click('.menu-btn'); await page.waitForTimeout(300)
  check(await page.locator('.sidebar:not(.collapsed)').count() === 1, 'mobile: menu opens sidebar')
  check(await page.locator('.scrim').count() === 1, 'mobile: scrim covers content behind drawer')
  await page.locator('.scrim').click({ position: { x: 360, y: 700 } }); await page.waitForTimeout(300)
  check(await page.locator('.sidebar:not(.collapsed)').count() === 0, 'mobile: scrim tap closes sidebar')
  await page.click('.sources-btn'); await page.waitForTimeout(300)
  check(await page.locator('.evidence').count() === 1, 'mobile: sources drawer opens')
  await page.keyboard.press('Escape'); await page.waitForTimeout(300)
  check(await page.locator('.evidence').count() === 0, 'mobile: Escape closes sources drawer')

  // Sidebar: search filters the list, Saved answers lives in the foot above the profile.
  await page.click('.menu-btn'); await page.waitForTimeout(300)
  const foot = await page.evaluate(() => {
    const f = document.querySelector('.side-bottom')
    const nav = f?.querySelector('.nav-item'), prof = f?.querySelector('.profile')
    if (!nav || !prof) return null
    return { saved: nav.innerText.includes('Saved answers'), above: nav.getBoundingClientRect().bottom <= prof.getBoundingClientRect().top + 1 }
  })
  check(foot?.saved === true, 'sidebar: Saved answers sits in the foot')
  check(foot?.above === true, 'sidebar: Saved answers is above the profile')
  const total = await page.locator('.history-item').count()
  check(total >= 2, `search: sidebar lists the seeded conversations (${total})`)
  // Search is answered by the server now and debounced, so waiting a fixed
  // 250ms raced it and read the unfiltered list. Wait for the result instead.
  await page.fill('.search-input', `Monsoon ${tag}`)
  await page.waitForFunction(n => document.querySelectorAll('.history-item').length < n, total, { timeout: 20000 }).catch(() => {})
  check(await page.locator('.history-item').count() === 1, `search: a unique name filters ${total} conversations to 1`)
  await page.fill('.search-input', 'zzzzqqqq')
  await page.waitForSelector('.history-none', { timeout: 20000 }).catch(() => {})
  check(await page.locator('.history-none').count() === 1, 'search: no-match message shown')
  await page.click('.search-clear')
  await page.waitForFunction(n => document.querySelectorAll('.history-item').length === n, total, { timeout: 20000 }).catch(() => {})
  check(await page.locator('.history-item').count() === total, 'search: clear restores the list')
  await page.locator('.scrim').click({ position: { x: 360, y: 700 } }); await page.waitForTimeout(300)
  // the seeds are empty conversations and would otherwise be the most recent,
  // so the layout checks below would open a chat with no turns
  await page.evaluate(async ids => {
    for (const id of ids) await fetch(`/api/chat/sessions/${id}`, { method: 'DELETE', credentials: 'include' })
  }, made)
  await page.reload({ waitUntil: 'networkidle' })
  await signIn(page)

  // Layout checks need a COMPLETED answer on screen. Try the conversations that
  // already exist first: checking alignment is not worth a model call, and it
  // must not depend on the provider being up to run at all.
  // Back to a desktop viewport: the drawer checks above left it narrow with the
  // sidebar shut, and these checks are about the desktop layout anyway.
  await page.setViewportSize({ width: 1280, height: 860 })
  const opened = async () => await page.locator('.turn.assistant .answer').count() > 0
  // Ask the API which conversation actually HAS a completed answer. Taking the
  // most recent few is not enough: a failed answer still makes a conversation.
  const ids = await page.evaluate(async () => {
    const list = (await (await fetch('/api/chat/sessions', { credentials: 'include' })).json()).sessions
    const out = []
    for (const s of list.slice(0, 15)) {
      const d = await (await fetch(`/api/chat/sessions/${s.id}`, { credentials: 'include' })).json()
      if ((d.turns || []).some(t => t.role === 'assistant' && (t.text || '').trim())) { out.push(s.id); break }
    }
    return out
  })
  // by address, not by clicking a row that may be scrolled out of view
  for (const id of ids) {
    if (await opened()) break
    await page.goto(`${URL}c/${id}`, { waitUntil: 'networkidle' })
    await page.waitForSelector('.turn.assistant .answer', { timeout: 15000 }).catch(() => {})
  }
  if (!(await opened())) {
    // nothing answered anywhere: this is the only path that spends anything
    await page.fill('.composer textarea', 'Name one property with a pool.')
    await page.click('.send-btn')
    await page.waitForSelector('.turn.assistant .answer', { timeout: 300000 }).catch(() => {})
    await page.waitForSelector('.stop-btn', { state: 'detached', timeout: 300000 }).catch(() => {})
  }
  await page.waitForTimeout(900)
  // An answer that FAILED still renders a .turn.assistant, but with an
  // explanation instead of an .answer. The layout checks need a real one, so
  // they are skipped rather than crashed when the provider is down.
  const hasTurns = await page.locator('.turn.user').count() > 0
    && await page.locator('.turn.assistant .answer').count() > 0
  check(hasTurns, 'a conversation with real turns is on screen for the layout checks')
  if (!hasTurns) console.log('      (skipping the alignment checks: no completed answer on screen)')

  // User turns sit right, assistant turns stay left and untinted.
  const align = hasTurns ? await page.evaluate(() => {
    const u = document.querySelector('.turn.user')
    const a = document.querySelector('.turn.assistant .answer')?.closest('.turn.assistant')
    if (!u || !a || !u.querySelector('p')) return null
    const ur = u.getBoundingClientRect(), av = u.querySelector('.avatar').getBoundingClientRect()
    const ub = u.querySelector('.turn-body').getBoundingClientRect()
    const ab = a.querySelector('.turn-body').getBoundingClientRect()
    return {
      userPacksRight: Math.abs(av.right - ur.right) < 2 && ub.right <= av.left && ub.width <= ur.width * 0.9,
      bubbleTinted: getComputedStyle(u.querySelector('p')).backgroundColor !== 'rgba(0, 0, 0, 0)',
      assistantLeft: ab.left - a.getBoundingClientRect().left < 60,
      assistantPlain: getComputedStyle(a.querySelector('.answer')).backgroundColor === 'rgba(0, 0, 0, 0)',
    }
  }) : null
  if (align) {
    check(align.userPacksRight, 'conversation: user turn is right-aligned')
    check(align.bubbleTinted, 'conversation: user turn has a tinted bubble')
    check(align.assistantLeft && align.assistantPlain, 'conversation: assistant turn stays left and untinted')
  }

  // Removed chrome stays removed.
  check(await page.locator('.turn-foot').count() === 0, 'chrome: per-answer timing/cost footer removed')
  check(!(await page.locator('.composer-meta').innerText()).includes('4,000'), 'chrome: composer character counter removed')
  check(await page.locator('.chat-statusbar .ready').count() === 0, 'chrome: Ready pill removed')
  check(await page.locator('.welcome').count() === 0, 'chrome: hardcoded corpus count removed')

  // Composer grows with content and stays inside its shell.
  const box = page.locator('.composer textarea')
  const empty = (await box.boundingBox()).height
  await box.fill('a\n'.repeat(12))
  await page.waitForTimeout(150)
  const grown = (await box.boundingBox()).height
  check(grown > empty && grown <= 165, `composer grows then caps (${Math.round(empty)} -> ${Math.round(grown)}px)`)
  await box.fill('pool and family rooms')
  await page.click('.send-btn'); await page.waitForTimeout(120)
  const fits = await page.evaluate(() => {
    const s = document.querySelector('.composer').getBoundingClientRect(), b = document.querySelector('.stop-btn').getBoundingClientRect()
    return b.right <= s.right + 0.5 && b.left >= s.left - 0.5 && b.bottom <= s.bottom + 0.5
  })
  check(fits, 'streaming: stop button stays inside the composer')

  // an empty composer must sit level with its send button at every width
  await page.fill('.composer textarea', '')
  await page.waitForTimeout(250)
  const level = await page.evaluate(() => {
    const ta = document.querySelector('.composer textarea').getBoundingClientRect()
    const btn = document.querySelector('.send-btn, .stop-btn')?.getBoundingClientRect()
    if (!btn) return null
    return Math.abs((ta.top + ta.height / 2) - (btn.top + btn.height / 2))
  })
  check(level !== null && level <= 1, `composer text is level with the send button (off by ${level?.toFixed(1)}px)`)
  await ctx.close()

  // WCAG AA on sampled text, both themes.
  for (const theme of ['light', 'dark']) {
    const c = await browser.newContext({ viewport: { width: 1280, height: 820 } })
    const p = await c.newPage()
    await p.goto(URL, { waitUntil: 'networkidle' })
    await signIn(p)
    if (theme === 'dark') { await p.click('.theme-btn'); await p.waitForTimeout(250) }
    // signing in already loads the most recent conversation, so there is
    // nothing to click; just wait for its turns to paint
    await p.waitForSelector('.turn.assistant', { timeout: 25000 }).catch(() => {})
    await p.waitForTimeout(600)
    const got = await p.evaluate(sels => sels.map(sel => {
      const el = document.querySelector(sel)
      if (!el) return null
      const cs = getComputedStyle(el)
      let bg = cs.backgroundColor, node = el
      while (bg === 'rgba(0, 0, 0, 0)' && node.parentElement) { node = node.parentElement; bg = getComputedStyle(node).backgroundColor }
      return { sel, fg: cs.color, bg, size: parseFloat(cs.fontSize), weight: cs.fontWeight }
    }).filter(Boolean), SAMPLES)
    for (const s of got) {
      const large = s.size >= 24 || (s.size >= 18.66 && Number(s.weight) >= 700)
      const need = large ? 3 : 4.5
      const r = contrast(toRgb(s.fg), toRgb(s.bg))
      check(r >= need, `${theme}: ${s.sel} contrast ${r.toFixed(2)}:1 (need ${need})`)
    }
    await c.close()
  }
  await browser.close()
} finally {
  server.kill()
}

console.log(fails.length ? `\n${fails.length} failing check(s)` : '\nall checks passed')
process.exit(fails.length ? 1 : 0)
