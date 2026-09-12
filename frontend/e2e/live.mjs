// Live end-to-end check against a RUNNING backend and a real database.
// Run:  npm run build && TI_PASSWORD=... npm run test:live
// Point elsewhere with VITE_API_TARGET=http://127.0.0.1:8001
// It signs in, asks a real question, and exercises every wired feature:
// citations, saved answers, feedback, saved sources, properties, delete.
import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { setTimeout as sleep } from 'node:timers/promises'

const PORT = 5188
const APP = `http://127.0.0.1:${PORT}/`
const PASSWORD = process.env.TI_PASSWORD
if (!PASSWORD) { console.error('set TI_PASSWORD to the workspace password'); process.exit(2) }
const OUT = process.argv[2] || 'e2e/shots'

const fails = []
const check = (ok, label) => { if (!ok) fails.push(label); console.log(`${ok ? 'ok  ' : 'FAIL'}  ${label}`) }

// vite preview with the same /api proxy the dev server uses
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(PORT)], { stdio: 'ignore', env: { ...process.env, VITE_API_TARGET: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000' } })
try {
  for (let i = 0; i < 60; i++) { try { await fetch(APP); break } catch { await sleep(250) } }
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', e => errors.push(`pageerror: ${e.message}`))
  page.on('console', m => { if (m.type() === 'error' && !/401|Unauthorized/.test(m.text())) errors.push(m.text()) })
  const failedReqs = []
  page.on('response', r => { if (r.url().includes('/api/') && r.status() >= 400 && !(r.status() === 401 && r.url().includes('/auth/me'))) failedReqs.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`) })

  await page.goto(APP, { waitUntil: 'networkidle' })

  // ---- login against the real backend ----
  check(await page.locator('input[type=password]').count() === 1, 'login screen shown when signed out')
  await page.fill('input[type=password]', PASSWORD)
  await page.click('.primary-btn')
  await page.waitForSelector('.workspace', { timeout: 15000 })
  check(true, 'login succeeds with the real password')
  const profile = await page.locator('.profile').innerText()
  check(profile.includes('Travel Inn') && profile.includes('team@travelinn.local'), `profile shows the real account (${profile.replace(/\n/g, ' ')})`)
  check(!/Priyanshu|Demo Workspace/.test(profile), 'no demo identity anywhere')

  // ---- a new conversation is a draft: nothing is stored until a question is sent ----
  const beforeNew = await page.evaluate(async () => (await (await fetch('/api/chat/sessions', { credentials: 'include' })).json()).sessions.length)
  await page.click('.new-chat')
  await page.waitForSelector('.start-here', { timeout: 15000 })
  check(true, 'a new conversation shows the start screen')
  await page.waitForTimeout(900)
  const afterNew = await page.evaluate(async () => (await (await fetch('/api/chat/sessions', { credentials: 'include' })).json()).sessions.length)
  check(afterNew === beforeNew, `clicking New conversation stores nothing (${beforeNew} -> ${afterNew})`)

  // clicking away from an unused draft must leave no trace either
  if (await page.locator('.history-open').count()) {
    await page.locator('.history-open').first().click()
    await page.waitForTimeout(900)
    const afterSwitch = await page.evaluate(async () => (await (await fetch('/api/chat/sessions', { credentials: 'include' })).json()).sessions.length)
    check(afterSwitch === beforeNew, `switching away from an empty draft leaves nothing behind (${afterSwitch})`)
    await page.click('.new-chat')
    await page.waitForSelector('.start-here', { timeout: 15000 })
  }
  check(await page.locator('.start-chip').count() === 0, 'no suggested questions on the start screen')
  check(await page.locator('.history-icon').count() === 0, 'no dot marker before conversation names')
  const copy = await page.locator('.workspace').innerText()
  check(!/approved corpus/i.test(copy), 'the phrase "approved corpus" is gone from the UI')
  check(await page.locator('.nav-item', { hasText: 'Properties' }).count() === 0, 'Properties is gone from the sidebar')

  // every column in the chat pane shares one left edge, and so does the sidebar search
  const edges = await page.evaluate(() => {
    const L = s => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().left) : null }
    return {
      chat: [L('.chat-statusbar>span'), L('.composer'), L('.composer-meta'), L('.start-here')].filter(x => x !== null),
      side: [L('.new-chat'), L('.nav-item'), L('.search-input'), L('.history-open')].filter(x => x !== null),
    }
  })
  check(Math.max(...edges.chat) - Math.min(...edges.chat) <= 1, `chat pane shares a left edge (${edges.chat.join(', ')})`)
  check(Math.max(...edges.side) - Math.min(...edges.side) <= 1, `sidebar shares a left edge (${edges.side.join(', ')})`)

  // ---- ask a real question end to end ----
  const before = await page.evaluate(async () => (await (await fetch('/api/chat/sessions', { credentials: 'include' })).json()).sessions.length)
  await page.fill('.composer textarea', 'Which properties have a swimming pool?')
  await page.click('.send-btn')
  await page.waitForSelector('.thinking', { timeout: 15000 })
  check(true, 'streaming starts (the thinking line appears)')
  check(await page.locator('.dots').count() > 0, 'a three-dot indicator is animating while it works')
  check(await page.locator('.thinking-body').count() === 0, 'the reasoning is folded away until the reader asks for it')
  await page.locator('.thinking-head').click()
  await page.waitForSelector('.thinking-body', { timeout: 4000 })
  check(true, 'clicking the line opens the steps and notes')
  await page.locator('.thinking-head').click()

  // the question must be on screen DURING generation, not only after it
  const asked = await page.locator('.turn.user p').last().innerText().catch(() => '')
  check(asked.includes('swimming pool'), `the question is visible while the answer streams ("${asked.slice(0, 40)}")`)
  check(await page.locator('.turn.assistant.live .answer-tools button', { hasText: 'Save answer' }).count() === 0,
    'no Save button on a half-written answer')
  await page.waitForFunction(() => {
    const el = document.querySelector('.turn.assistant.live .answer')
    return el && el.textContent.trim().length > 30
  }, { timeout: 180000 }).catch(() => {})
  const answerText = await page.locator('.turn.assistant.live .answer').innerText().catch(() => '')
  const streamError = await page.locator('.chat-error').innerText().catch(() => '')
  if (streamError) {
    check(false, `STREAM FAILED, downstream checks skipped: ${streamError.replace(/\s+/g, ' ').slice(0, 160)}`)
    check(true, 'the failure is shown to the user in the chat view')
  }
  check(!!streamError || answerText.trim().length > 30, `answer streamed back (${answerText.trim().length} chars)`)
  if (streamError) {
    console.log('\nEverything below needs a working answer, so the run stops here.')
    console.log('Fix the model quota, then re-run to verify the rest.')
    await ctx.close(); await browser.close()
    console.log(`\n${fails.length} FAILING`)
    process.exit(1)
  }
  await page.waitForSelector('.stop-btn', { state: 'detached', timeout: 180000 }).catch(() => {})
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT}/live-answer.png` })

  const after = await page.evaluate(async () => (await (await fetch('/api/chat/sessions', { credentials: 'include' })).json()).sessions.length)
  check(after >= 1 && after <= before + 1, `asking used or created one conversation (${before} -> ${after})`)

  const citations = await page.locator('.inline-citation').count()
  if (!streamError) check(citations > 0, `answer carries ${citations} citation chips`)
  if (citations > 0 && !streamError) {
    await page.locator('.inline-citation').first().click()
    await page.waitForSelector('.source-modal', { timeout: 15000 })
    check(true, 'clicking a citation opens that document on screen')
    const modal = await page.locator('.source-modal').innerText()
    check(!modal.includes('Approved corpus evidence for this answer'), 'no fabricated excerpt text in the dialog')
    await page.waitForSelector('.source-stage img', { timeout: 25000 }).catch(() => {})
    await page.screenshot({ path: `${OUT}/live-citation.png` })
    await page.keyboard.press('Escape')
    await page.waitForSelector('.source-modal', { state: 'detached', timeout: 10000 })
  }

  // Evidence must be what the answer cited, not what retrieval opened.
  const cards = await page.locator('.source-card').count()
  const inText = await page.evaluate(() => {
    const el = document.querySelector('.turn.assistant .answer')
    const seen = new Set()
    for (const m of (el?.textContent || '').matchAll(/\[(\d{1,3})\]/g)) seen.add(m[1])
    return [...seen]
  })
  check(cards === inText.length, `evidence shows exactly the cited sources (${cards} cards, ${inText.length} distinct citations)`)
  check(inText.length === 0 || Math.max(...inText.map(Number)) <= cards,
    `citation numbers run 1..${cards}, none point past the list (${inText.join(',')})`)
  const everyChipOpens = await page.evaluate(() => {
    const nums = [...document.querySelectorAll('.turn.assistant .inline-citation')].map(b => b.dataset.citation)
    return nums.every(n => Number(n) >= 1)
  })
  check(everyChipOpens, 'every citation chip carries a resolvable number')
  check(await page.locator('.source-card img').count() === 0, 'source cards cost no request (no per-card thumbnail)')

  // ---- saved answers round trip through the database ----
  await page.locator('.turn.assistant .answer-tools button', { hasText: 'Save answer' }).first().click()
  await page.waitForTimeout(1200)
  const savedViaApi = await page.evaluate(async () => (await (await fetch('/api/saved-answers', { credentials: 'include' })).json()).answers.length)
  check(savedViaApi > 0, `saved answer persisted to the database (${savedViaApi} row(s))`)
  await page.locator('.nav-item', { hasText: 'Saved answers' }).click()
  await page.waitForSelector('.saved-card', { timeout: 15000 })
  await page.waitForTimeout(600)
  check(await page.locator('.saved-card').count() === savedViaApi, 'Saved view renders what the database returns')
  await page.screenshot({ path: `${OUT}/live-saved.png` })
  await page.locator('.saved-card .answer-tools button', { hasText: 'Unsave answer' }).first().click()
  await page.waitForTimeout(1200)
  const afterUnsave = await page.evaluate(async () => (await (await fetch('/api/saved-answers', { credentials: 'include' })).json()).answers.length)
  check(afterUnsave === savedViaApi - 1, `unsave removed the row (${savedViaApi} -> ${afterUnsave})`)

  // ---- feedback reaches the backend ----
  await page.locator('.nav-item', { hasText: 'All conversations' }).click()
  await page.waitForSelector('.turn.assistant', { timeout: 20000 })
  await page.waitForTimeout(1200)
  check(await page.locator('.answer-tools button', { hasText: 'Helpful' }).count() === 0, 'Helpful button is gone')
  const fbTurn = page.locator('.turn.assistant').first()
  await fbTurn.locator('.answer-tools button', { hasText: 'Needs correction' }).click()
  await page.waitForSelector('.correction-modal', { timeout: 10000 })
  check(true, 'Needs correction opens the correction dialog')
  check(await page.locator('.reason-chip').count() === 5, 'dialog offers all five reason categories')
  await page.locator('.reason-chip', { hasText: 'Out of date' }).click()
  await page.fill('.correction-note textarea', 'The March rate sheet is the current one, not January.')
  await page.locator('.correction-modal button', { hasText: 'Send correction' }).click()
  await page.waitForSelector('.correction-modal', { state: 'detached', timeout: 15000 })
  const stored = await page.evaluate(async () => (await (await fetch('/api/answer-feedback', { credentials: 'include' })).json()).feedback[0])
  check(stored?.note?.includes('March rate sheet'), `correction text saved to the database ("${(stored?.note || '').slice(0, 40)}")`)
  check(stored?.reason === 'outdated', `correction category saved (reason=${stored?.reason})`)
  check(stored?.kind === 'correction', 'correction stored with kind=correction')

  // ---- saved sources ----
  if (await page.locator('.evidence').count() === 0) await page.click('.sources-btn')
  await page.waitForSelector('.source-card', { timeout: 15000 }).catch(() => {})
  if (await page.locator('.source-card').count() === 0) { console.log('    (no sources on screen, skipping source checks)') } else {
  await page.waitForTimeout(500)
  check(await page.locator('.source-actions button', { hasText: 'Copy path' }).count() === 0, 'Copy path button is gone')
  const saveSrc = page.locator('.source-actions button', { hasText: 'Save source' }).first()
  await saveSrc.click()
  await page.waitForTimeout(1200)
  const srcRows = await page.evaluate(async () => (await (await fetch('/api/saved-sources', { credentials: 'include' })).json()).sources.length)
  check(srcRows > 0, `saved source persisted to the database (${srcRows} row(s))`)

  // View source opens the real document on screen
  await page.locator('.source-actions button', { hasText: 'View source' }).first().click()
  await page.waitForSelector('.source-modal', { timeout: 15000 })
  await page.waitForSelector('.source-stage img', { timeout: 25000 }).catch(() => {})
  const shown = await page.locator('.source-stage img').getAttribute('src').catch(() => '')
  check(/r2\.cloudflarestorage|X-Amz|amazonaws/.test(shown || ''), `document renders from storage (${(shown || 'none').slice(0, 46)})`)
  check(await page.locator('.source-modal-links button', { hasText: 'Open original file' }).count() === 1, 'dialog offers open-in-new-tab for the original file')

  // a page already fetched in this dialog must not be fetched again
  if (await page.locator('.pager').count()) {
    let pageCalls = 0
    const count = r => { if (/\/api\/sources\/.+\/page\//.test(r.url())) pageCalls++ }
    page.on('request', count)
    await page.locator('.pager button', { hasText: 'Next' }).click()
    await page.waitForTimeout(1500)
    const afterNext = pageCalls
    await page.locator('.pager button', { hasText: 'Prev' }).click()
    await page.waitForTimeout(1500)
    page.off('request', count)
    check(pageCalls === afterNext, `going back reuses the signed link (${afterNext} fetch(es), then ${pageCalls - afterNext} more)`)
  }
  await page.keyboard.press('Escape')
  await page.waitForSelector('.source-modal', { state: 'detached', timeout: 10000 })
  check(true, 'source dialog closes with Escape')
  }

  // ---- the conversation names itself, and search reads what is inside ----
  // The thread so far has exactly one real question, so its name is that
  // question. A second real question is what earns the single model call.
  const named = () => page.locator('.history-item.selected strong').innerText().catch(() => '')
  const seeded = await named()
  check(seeded.toLowerCase().includes('pool'), `named after the first real question ("${seeded}")`)

  await page.fill('.composer textarea', 'And what are the room rates at those ones?')
  await page.click('.send-btn')
  await page.waitForSelector('.composer .send-btn', { timeout: 180000 })
  await page.waitForTimeout(1500)
  const settled = await named()
  // A failed answer must not rename anything, so only assert the rename when
  // the second answer actually arrived.
  const answered = await page.locator('.turn.assistant .answer').count() >= 2
  if (answered) {
    check(settled !== seeded, `the second real question renames it, with no reload ("${settled}")`)
    check(settled.length <= 40, `the name fits the sidebar (${settled.length} chars, cap 40)`)
    check(settled.split(/\s+/).length <= 6, `it is ${settled.split(/\s+/).length} words, not a sentence`)
  } else {
    check(settled === seeded, 'a failed answer leaves the name alone')
  }

  // "swimm" is mid-word and appears only inside messages, never in a name:
  // finding anything at all proves the search reads the conversation.
  await page.fill('.search-input', 'swimm')
  await page.waitForSelector('.history-snip', { timeout: 20000 })
  check(await page.locator('.history-item').count() > 0, 'search finds conversations by what is inside them')
  check(await page.locator('.history-snip mark').count() > 0, 'it shows the matching sentence with the words marked')
  const snip = await page.locator('.history-snip').first().innerText()
  check(!/<\/?b>/.test(snip), `no raw markup reaches the page ("${snip.slice(0, 46)}")`)
  await page.fill('.search-input', 'zzzqqqxyz')
  await page.waitForSelector('.history-none', { timeout: 20000 })
  check(true, 'a miss says so instead of listing everything')
  await page.fill('.search-input', '')
  await page.waitForSelector('.history-group-label', { timeout: 10000 })
  check(true, 'clearing the box restores the grouped list')

  // ---- delete conversation ----
  await page.locator('.nav-item', { hasText: 'All conversations' }).click()
  await page.waitForSelector('.history-item', { timeout: 15000 })
  await page.waitForTimeout(700)
  // a native confirm() would be auto-dismissed by Playwright, so this failing
  // to open is itself the check that the browser box is gone
  let nativeBox = false
  page.once('dialog', d => { nativeBox = true; d.accept() })
  const preDel = await page.locator('.history-item').count()
  await page.locator('.history-del').first().click()
  await page.waitForSelector('.confirm-modal', { timeout: 5000 })
  check(!nativeBox, 'delete asks in a themed dialog, not the browser box')
  check((await page.locator('.confirm-modal').innerText()).includes('cannot be undone'), 'the dialog spells out that it cannot be undone')
  await page.keyboard.press('Escape')
  await page.waitForSelector('.confirm-modal', { state: 'detached', timeout: 4000 })
  check(await page.locator('.history-item').count() === preDel, 'Escape cancels and keeps the conversation')
  await page.locator('.history-del').first().click()
  await page.waitForSelector('.confirm-modal', { timeout: 5000 })
  await page.locator('.confirm-modal .primary-btn').click()
  // deleting the OPEN conversation chains a detail fetch, so wait for the list
  // to actually change rather than guessing at a sleep
  await page.waitForFunction(n => document.querySelectorAll('.history-item').length < n, preDel, { timeout: 15000 }).catch(() => {})
  const postDel = await page.locator('.history-item').count()
  check(postDel === preDel - 1, `delete conversation works (${preDel} -> ${postDel})`)

  // ---- the three dots open a menu; they used to sign you out on the spot ----
  await page.locator('.profile-menu .icon-btn').click()
  await page.waitForSelector('.menu', { timeout: 4000 })
  check(await page.locator('.workspace').count() === 1, 'opening the account menu does NOT sign you out')
  check((await page.locator('.menu-who').innerText()).includes('team@travelinn.local'), 'the menu names the signed-in account')
  await page.keyboard.press('Escape')
  check(await page.locator('.menu').count() === 0, 'Escape closes the account menu')
  await page.locator('.profile-menu .icon-btn').click()
  await page.locator('.menu-item', { hasText: 'Sign out' }).click()
  await page.waitForSelector('.login-card', { timeout: 10000 })
  check(true, 'Sign out inside the menu does sign you out')

  check(errors.length === 0, `no console errors ${errors.slice(0, 2).join(' | ')}`)
  check(failedReqs.length === 0, `no failed API calls ${failedReqs.slice(0, 4).join(' | ')}`)

  await ctx.close(); await browser.close()
} finally { server.kill() }

console.log(fails.length ? `\n${fails.length} FAILING` : '\nall live checks passed')
process.exit(fails.length ? 1 : 0)
