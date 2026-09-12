/**
 * Upstream failures arrive as whatever the provider said, which is often a
 * Python dict: `429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': ...`.
 * A salesperson mid-call cannot act on that. Translate the cases we know and
 * fall back to the raw text rather than hiding something we failed to classify.
 */
const RULES: { match: RegExp; say: string }[] = [
  { match: /spending cap|exceeded its monthly/i,
    say: 'The AI service has hit its monthly spending cap. Someone needs to raise it before answers will work again.' },
  { match: /RESOURCE_EXHAUSTED|\b429\b|rate limit|quota/i,
    say: 'The AI service is rate limited right now. Wait a moment and ask again.' },
  { match: /UNAVAILABLE|overloaded|\b503\b/i,
    say: 'The AI service is busy. Try that question again in a few seconds.' },
  { match: /DEADLINE_EXCEEDED|timed? ?out/i,
    say: 'That took too long and was stopped. Try a narrower question.' },
  { match: /sign in first|\b401\b|unauthor/i,
    say: 'Your session has expired. Sign in again to continue.' },
  { match: /no such conversation|\b404\b/i,
    say: 'That conversation no longer exists. Start a new one.' },
  { match: /PERMISSION_DENIED|API key|invalid.*credential/i,
    say: 'The AI service rejected our credentials. This needs an administrator.' },
  { match: /neon|could not connect|connection refused|ECONNREFUSED/i,
    say: 'The database could not be reached. The service may still be starting up.' },
  { match: /^Failed to fetch$|NetworkError/i,
    say: 'Could not reach the server. Check that the backend is running.' },
]

// Messages this service wrote itself are already plain English and carry a
// number the reader needs. The dict-stripping fallback below would cut them at
// the first full stop and throw the number away.
const OURS = /^(Too many questions|This answer ran out of room)/i

export function humanise(raw?: string | null): string {
  const text = (raw || '').trim()
  if (!text) return 'Something went wrong. Try again.'
  if (OURS.test(text)) return text
  for (const rule of RULES) if (rule.match.test(text)) return rule.say
  // Unknown failure: strip an embedded dict or JSON blob so at least the
  // leading sentence is readable, but never invent a friendlier meaning.
  const head = text.split(/[.{]\s*/)[0].trim()
  return head.length > 8 && head.length < 200 ? `${head}.` : text.slice(0, 200)
}
