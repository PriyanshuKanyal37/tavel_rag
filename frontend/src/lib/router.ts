import { useEffect, useState } from 'react'

/**
 * The URL is the state. Every view the reader can reach has an address they can
 * bookmark, share, reload and walk back through.
 *
 *   /              a new conversation, nothing sent yet
 *   /c/:id         one conversation
 *   /saved         saved answers
 *   anything else  not found
 *
 * A source can be deep-linked from a conversation with ?source=<sha1>&page=<n>,
 * so a citation can be sent to a colleague and open on the same page.
 *
 * Signing in is a gate, not a route: the address you asked for is kept while the
 * password card is shown, so a deep link survives authentication instead of
 * dumping you on a home page afterwards.
 *
 * Hand-written rather than routed by a library: three shapes, no nesting, no
 * loaders. The History API already does the work, and a router would be more
 * machinery than the thing it routes.
 */
export type Route =
  | { name: 'new'; source?: SourceLink }
  | { name: 'chat'; id: number; source?: SourceLink }
  | { name: 'saved' }
  | { name: 'notFound'; path: string }

export type SourceLink = { sha1: string; page: number }

const SHA1 = /^[0-9a-f]{40}$/i

function readSource(search: string): SourceLink | undefined {
  const q = new URLSearchParams(search)
  const sha1 = q.get('source')
  if (!sha1 || !SHA1.test(sha1)) return undefined
  const page = Number(q.get('page') || 1)
  return { sha1, page: Number.isFinite(page) && page >= 1 ? Math.floor(page) : 1 }
}

export function parse(pathname: string, search = ''): Route {
  const path = pathname.replace(/\/+$/, '') || '/'
  if (path === '/') return { name: 'new', source: readSource(search) }
  if (path === '/saved') return { name: 'saved' }
  const chat = path.match(/^\/c\/([1-9]\d*)$/)
  if (chat) return { name: 'chat', id: Number(chat[1]), source: readSource(search) }
  return { name: 'notFound', path }
}

export function href(route: Route): string {
  const q = (s?: SourceLink) => (s ? `?source=${s.sha1}&page=${s.page}` : '')
  switch (route.name) {
    case 'new': return `/${q(route.source)}`
    case 'chat': return `/c/${route.id}${q(route.source)}`
    case 'saved': return '/saved'
    default: return route.path
  }
}


/** Only a conversation or a new chat can carry a source; narrow without casts. */
export function sourceOf(route: Route): SourceLink | undefined {
  return route.name === 'chat' || route.name === 'new' ? route.source : undefined
}

export function withSource(route: Route, source?: SourceLink): Route {
  if (route.name === 'chat') return { name: 'chat', id: route.id, source }
  if (route.name === 'new') return { name: 'new', source }
  return route
}

/** Page title, because a tab full of identical names is useless. */
const BRAND = 'Travel Inn Knowledge Assistant'
export function title(route: Route, chatTitle?: string | null): string {
  switch (route.name) {
    case 'chat': return `${chatTitle?.trim() || 'Conversation'} · ${BRAND}`
    case 'saved': return `Saved answers · ${BRAND}`
    case 'notFound': return `Not found · ${BRAND}`
    default: return BRAND
  }
}

// One subscriber list, so a navigate() anywhere updates every hook.
const listeners = new Set<() => void>()
const announce = () => listeners.forEach(fn => fn())

export function navigate(route: Route, opts: { replace?: boolean } = {}) {
  const url = href(route)
  if (url === window.location.pathname + window.location.search) return
  window.history[opts.replace ? 'replaceState' : 'pushState']({}, '', url)
  announce()
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.pathname, window.location.search))
  useEffect(() => {
    const sync = () => setRoute(parse(window.location.pathname, window.location.search))
    listeners.add(sync)
    // Back and forward are the browser's job; we only have to listen.
    window.addEventListener('popstate', sync)
    return () => { listeners.delete(sync); window.removeEventListener('popstate', sync) }
  }, [])
  return route
}
