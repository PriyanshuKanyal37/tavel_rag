// Routing check: every view has an address you can bookmark, share and reload.
// Run:  npm run build && TI_PASSWORD=... npm run test:routes
//
// DEPLOYMENT NOTE. These pass here because vite dev and vite preview both fall
// back to index.html for unknown paths. A production host must do the same, or
// reloading /c/42 returns the host's own 404 and never reaches the app:
//   nginx   location / { try_files $uri $uri/ /index.html; }
//   caddy   try_files {path} /index.html
//   S3      set the error document to index.html
// Netlify, Vercel and Cloudflare Pages do it by default for SPAs.
import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { setTimeout as sleep } from 'node:timers/promises'

const PORT = 5203, APP = `http://127.0.0.1:${PORT}`, OUT = process.argv[2]
const PW = process.env.TI_PASSWORD || 'travelinn'
const fails = []
const check = (ok, label) => { if (!ok) fails.push(label); console.log(`${ok ? 'ok  ' : 'FAIL'}  ${label}`) }

const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(PORT)], { stdio: 'ignore' })
try {
  for (let i = 0; i < 60; i++) { try { await fetch(APP + '/') ; break } catch { await sleep(250) } }

  // the server must hand back the app for a deep path, not a 404
  for (const p of ['/', '/saved', '/c/123', '/c/123?source=' + 'a'.repeat(40)]) {
    const r = await fetch(APP + p)
    check(r.status === 200, `server serves the app at ${p} (${r.status})`)
  }

  const b = await chromium.launch()
  const ctx = await b.newContext({ viewport: { width: 1400, height: 900 } })
  const page = await ctx.newPage()
  const path = () => page.evaluate(() => location.pathname + location.search)

  // sign in once; the cookie persists for the rest of the run
  await page.goto(APP + '/', { waitUntil: 'networkidle' })
  await page.fill('.pw-field input', PW)
  await page.click('.primary-btn')
  await page.waitForSelector('.workspace', { timeout: 20000 })
  await page.waitForTimeout(1500)
  check(await path() === '/', 'signing in lands on a new conversation at /')
  check(await page.locator('.start-here').count() === 1, 'a new conversation shows the start screen')

  // opening a conversation puts it in the address bar
  await page.locator('.history-open').first().click()
  await page.waitForSelector('.turn', { timeout: 20000 })
  const chatPath = await path()
  check(/^\/c\/\d+$/.test(chatPath), `opening a conversation gives it an address (${chatPath})`)
  const chatTitle = await page.title()
  check(chatTitle.includes('Travel Inn Knowledge Assistant') && !chatTitle.startsWith('Travel Inn Knowledge'), `the tab is named after the conversation ("${chatTitle.slice(0, 44)}")`)

  // reload must land in the same place
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForSelector('.turn', { timeout: 20000 })
  check(await path() === chatPath, 'reloading stays in the same conversation')

  // saved answers has its own address
  await page.locator('.nav-item', { hasText: 'Saved answers' }).click()
  await page.waitForTimeout(800)
  check(await path() === '/saved', 'saved answers lives at /saved')
  check((await page.title()).includes('Saved answers'), 'the tab says Saved answers')

  // back and forward walk the history
  await page.goBack(); await page.waitForTimeout(900)
  check(await path() === chatPath, 'Back returns to the conversation')
  await page.goForward(); await page.waitForTimeout(900)
  check(await path() === '/saved', 'Forward returns to saved answers')

  // a pasted conversation link opens that conversation directly
  await page.goto(APP + chatPath, { waitUntil: 'networkidle' })
  await page.waitForSelector('.turn', { timeout: 20000 })
  check(await page.locator('.turn').count() > 0, 'a pasted conversation link opens it directly')

  // a citation is shareable: opening one puts it in the URL
  if (await page.locator('.inline-citation').count()) {
    await page.locator('.inline-citation').first().click()
    await page.waitForSelector('.source-modal', { timeout: 15000 })
    const withSrc = await path()
    check(/[?&]source=[0-9a-f]{40}/.test(withSrc), `opening a source is in the address (${withSrc.slice(0, 56)}…)`)

    await page.goBack(); await page.waitForTimeout(700)
    check(await page.locator('.source-modal').count() === 0, 'Back closes the source dialog')

    // and that link, pasted cold, opens the document
    await page.goto(APP + withSrc, { waitUntil: 'networkidle' })
    await page.waitForSelector('.source-modal', { timeout: 20000 })
    check(true, 'a pasted citation link opens that document')
    await page.waitForSelector('.source-stage img', { timeout: 25000 }).catch(() => {})
    await page.screenshot({ path: `${OUT}/route-deeplink.png` })
    await page.keyboard.press('Escape'); await page.waitForTimeout(600)
    check(!/source=/.test(await path()), 'closing removes it from the address')
  }

  // a nonsense address gets a real page
  await page.goto(APP + '/totally-made-up', { waitUntil: 'networkidle' })
  await page.waitForSelector('.notfound', { timeout: 15000 })
  check(true, 'an unknown path shows a not-found page')
  check((await page.title()).includes('Not found'), 'the tab says Not found')
  await page.screenshot({ path: `${OUT}/route-404.png` })
  await page.locator('.notfound button').click()
  await page.waitForTimeout(800)
  check(await path() === '/', 'the not-found page can get you home')

  // a conversation id that does not exist
  await page.goto(APP + '/c/99999999', { waitUntil: 'networkidle' })
  await page.waitForSelector('.notfound', { timeout: 20000 })
  check(true, 'a deleted conversation shows a gone page rather than a blank chat')

  // a deep link while signed out keeps the destination
  await ctx.clearCookies()
  await page.goto(APP + chatPath, { waitUntil: 'networkidle' })
  check(await page.locator('.login-card').count() === 1, 'signed out, a deep link shows the password gate')
  check(await path() === chatPath, 'the address you asked for survives the gate')
  await page.fill('.pw-field input', PW)
  await page.click('.primary-btn')
  await page.waitForSelector('.turn', { timeout: 25000 })
  check(await path() === chatPath, 'after signing in you land where you were going')

  await b.close()
} finally { server.kill() }

console.log(fails.length ? `\n${fails.length} FAILING` : '\nall routing checks passed')
process.exit(fails.length ? 1 : 0)
