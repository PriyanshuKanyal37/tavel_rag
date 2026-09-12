import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'
import type { SourceDoc, SourceRef } from '../types'

const fileName = (path?: string | null) => {
  if (!path) return 'Approved document'
  const parts = path.split(/[\\/]/).filter(Boolean)
  return parts[parts.length - 1] || path
}

/**
 * The document itself, on screen. Pages are signed R2 URLs minted per request
 * and valid for 15 minutes, so they are fetched when the dialog opens rather
 * than stored anywhere.
 */
export function SourceDialog({ source, onClose }: { source: SourceRef; onClose: () => void }) {
  const [meta, setMeta] = useState<SourceDoc | null>(null)
  const [page, setPage] = useState(source.page || 1)
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // Signed links last 15 minutes and this dialog lives seconds, so a page
  // already fetched can be shown again without another round trip.
  const seen = useRef<Map<number, string>>(new Map())

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    let live = true
    api.sourceMeta(source.sha1).then(m => { if (live) setMeta(m) }).catch(() => {})
    return () => { live = false }
  }, [source.sha1])

  useEffect(() => { seen.current.clear() }, [source.sha1])
  useEffect(() => {
    const cached = seen.current.get(page)
    if (cached) { setUrl(cached); setError(''); setLoading(false); return }
    let live = true
    setLoading(true); setError(''); setUrl('')
    api.sourcePage(source.sha1, page)
      .then(r => { if (live) { seen.current.set(page, r.url); setUrl(r.url) } })
      .catch(e => { if (live) setError((e as Error).message || 'This page could not be loaded') })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [source.sha1, page])

  const pages = meta?.page_count || 1
  const openTab = useCallback(async (which: 'page' | 'original') => {
    try {
      const signed = which === 'page' ? await api.sourcePage(source.sha1, page) : await api.sourceOriginal(source.sha1)
      window.open(signed.url, '_blank', 'noopener,noreferrer')
    } catch (e) { setError((e as Error).message || 'Could not open that link') }
  }, [source.sha1, page])

  return createPortal(
    <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal source-modal" role="dialog" aria-modal="true" aria-labelledby="source-title">
        <div className="modal-head">
          <div className="source-modal-title">
            <span className="eyebrow">SOURCE</span>
            <h2 id="source-title">{fileName(source.rel_path||meta?.rel_path)}</h2>
            <small>Page {page}{pages > 1 ? ` of ${pages}` : ''} · SHA {source.sha1.slice(0, 12)}</small>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close source">&times;</button>
        </div>

        <div className="source-stage">
          {loading && <p className="source-stage-msg">Loading page {page}…</p>}
          {error && !loading && <p className="source-stage-msg error">{error}</p>}
          {url && !loading && !error && (
            <img src={url} alt={`${fileName(source.rel_path||meta?.rel_path)} page ${page}`} onError={() => setError('This page could not be displayed')} />
          )}
        </div>

        <div className="source-modal-actions">
          {pages > 1 && (
            <div className="pager">
              <button className="ghost-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>&larr; Prev</button>
              <span>{page} / {pages}</span>
              <button className="ghost-btn" onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages}>Next &rarr;</button>
            </div>
          )}
          <div className="source-modal-links">
            <button className="ghost-btn" onClick={() => openTab('page')}>Open page in new tab &#8599;</button>
            <button className="primary-btn compact" onClick={() => openTab('original')}>Open original file &#8599;</button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
