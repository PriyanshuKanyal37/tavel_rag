import { useEffect, useState } from 'react'

/** Reveal `full` at a readable rate while `live`, then snap to all of it.
 *
 * The model hands over a whole answer in three or four large chunks, so
 * painting each one as it lands reads as three jumps rather than as streaming.
 * Chasing a fraction of the remaining gap makes the reveal take about a second
 * whatever the answer's length, and stops a long one crawling behind a stream
 * that has already finished.
 */
export const STEP_MS = 16
export const revealStep = (shown: number, total: number) =>
  Math.max(1, Math.ceil((total - shown) / 60))

export function useTypewriter(full: string, live: boolean) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!live || n >= full.length) { if (!live && n !== full.length) setN(full.length); return }
    const id = setTimeout(() => setN(x => Math.min(full.length, x + revealStep(x, full.length))), STEP_MS)
    return () => clearTimeout(id)
  }, [full, n, live])
  useEffect(() => { if (!full) setN(0) }, [full])
  return full.slice(0, n)
}
