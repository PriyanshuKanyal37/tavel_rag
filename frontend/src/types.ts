export type Mode = 'chat' | 'fast' | 'think' | 'agent'
export type SourceRef = { n?: number; orig?: number; sha1: string; rel_path?: string; name?: string; page?: number }
export type Turn = { seq: number; role: 'user'|'assistant'; text: string; status?: string; sources?: SourceRef[]; cost_inr?: number|null; ms?: number|null; created_at?: string }
export type Session = { id: number; title: string|null; last_active?: string; tokens_est?: number }
export type SessionDetail = { id: number; title: string|null; turns: Turn[]; summary?: string|null; working_set?: {sha1:string;level:string;turn_added:number}[] }
export type Account = { name: string; email: string }
export type Activity = { id: string; label: string; detail?: string; state: 'active'|'done'|'error' }
export type StreamEvent =
  | {type:'mode'; mode:Mode; why?:string; est_seconds?:number; max_rounds?:number; escalated?:boolean}
  | {type:'step'; round?:number; source?:string; from?:string; detail?:string; found?:number; opened?:number; chars?:number; count?:number; missing?:string}
  | {type:'thought'; text:string}
  | {type:'token'; text:string}
  | {type:'sources'; sources:SourceRef[]}
  | {type:'title'; title:string}
  | {type:'compacting'; working_set:number; tokens_before:number; tokens_after:number; demoted?:{sha1:string;from:string;to:string}[]}
  | {type:'done'; mode?:Mode; model?:string; rounds?:number; truncated?:boolean; answer_cut?:boolean; answer_length?:string; max_output?:number; found?:number; count?:number; cost_inr?:number; seconds?:number}
  | {type:'error'; message:string}
// A search result is a conversation plus WHY it matched: the sentence from the
// message that hit, already marked up by the database.
export type SearchHit = { id:number; title:string|null; last_active?:string; on_title:boolean; snippet?:string|null; role?:string|null }
export type SavedAnswer = { id: string; text: string; session_id?: number|null; saved_at?: string }
export type SavedSourceRef = { sha1: string; saved_at?: string }
export type SignedUrl = { url: string; expires_in: number }
export type SourceDoc = { sha1: string; rel_path: string; ext?: string; page_count?: number|null; is_tiled?: boolean }
export type Property = { id: number; name: string; state?: string|null; entity_type?: string|null; facts?: Record<string,unknown>|null }
export type PropertyDetail = { id: number; name: string; entity_type?: string|null; state?: string|null; city?: string|null; aliases?: string[]|null; facts?: Record<string,unknown>|null }
export type Fact = { key: string; value: string|number|null; unit?: string|null; scope?: string|null; asserted_as?: string|null; evidence?: string|null; sha1?: string|null; page?: number|null }
export type Connection = { from: string; kind: string; to: string; distance_km: number|null; duration_h: number|null; evidence?: string|null; sha1?: string|null }
export type CorrectionReason = 'wrong_fact' | 'missing' | 'wrong_source' | 'outdated' | 'other'
export type FeedbackBody = { answer_id: string; kind: 'correction'; reason: CorrectionReason; note: string }
export type FeedbackRow = { answer_id: string; kind: string; reason?: string|null; note?: string|null; created_at?: string }
