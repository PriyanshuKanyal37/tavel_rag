import { humanise } from './errors'
import type {Account,Connection,Fact,FeedbackBody,FeedbackRow,Property,PropertyDetail,SavedAnswer,SavedSourceRef,SearchHit,Session,SessionDetail,SourceDoc,SourceRef,SignedUrl} from '../types'
export class ApiError extends Error { constructor(public status:number,message:string){super(message)} }
async function request<T>(path:string, init:RequestInit={}){ const r=await fetch(path,{...init,credentials:'include',headers:{'Content-Type':'application/json',...(init.headers||{})}}); if(!r.ok){let m=`Request failed (${r.status})`;try{const b=await r.json();m=typeof b.detail==='string'?b.detail:b.detail?.message||b.message||m}catch{} throw new ApiError(r.status,humanise(m))} return r.status===204?undefined as T:r.json() as Promise<T> }
const qs=(o:Record<string,string|number|undefined>)=>{const p=new URLSearchParams();for(const[k,v]of Object.entries(o))if(v!==undefined&&v!=='' &&v!==0)p.set(k,String(v));const s=p.toString();return s?`?${s}`:''}

export const api={
  me:()=>request<Account>('/api/auth/me'), login:async(password:string)=>{await request<{ok:boolean}>('/api/auth/login',{method:'POST',body:JSON.stringify({password})});return request<Account>('/api/auth/me')}, logout:()=>request('/api/auth/logout',{method:'POST'}),

  sessions:()=>request<{sessions:Session[]}>('/api/chat/sessions'),
  // Searching titles could only find a conversation you already remembered the
  // name of. This one reads the messages, so it runs on the server.
  searchChats:(q:string)=>request<{results:SearchHit[]}>(`/api/chat/search?q=${encodeURIComponent(q)}`), detail:(id:number)=>request<SessionDetail>(`/api/chat/sessions/${id}`), create:(title?:string)=>request<Session>('/api/chat/sessions',{method:'POST',body:JSON.stringify({title:title||null})}), remove:(id:number)=>request(`/api/chat/sessions/${id}`,{method:'DELETE'}),

  // Saved answers live in the database, not this browser: the team shares one workspace.
  savedAnswers:()=>request<{answers:SavedAnswer[]}>('/api/saved-answers'),
  saveAnswer:(a:{id:string;text:string;session_id:number|null})=>request<{ok:boolean}>(`/api/saved-answers/${encodeURIComponent(a.id)}`,{method:'PUT',body:JSON.stringify(a)}),
  unsaveAnswer:(id:string)=>request<{ok:boolean}>(`/api/saved-answers/${encodeURIComponent(id)}`,{method:'DELETE'}),

  feedback:(body:FeedbackBody)=>request<{ok:boolean}>('/api/answer-feedback',{method:'POST',body:JSON.stringify(body)}),
  corrections:()=>request<{feedback:FeedbackRow[]}>('/api/answer-feedback'),
  clearFeedback:(id:string)=>request<{ok:boolean}>(`/api/answer-feedback/${encodeURIComponent(id)}`,{method:'DELETE'}),

  savedSources:()=>request<{sources:SavedSourceRef[]}>('/api/saved-sources'),
  saveSource:(sha1:string)=>request<{ok:boolean}>(`/api/saved-sources/${sha1}`,{method:'PUT'}),
  unsaveSource:(sha1:string)=>request<{ok:boolean}>(`/api/saved-sources/${sha1}`,{method:'DELETE'}),

  properties:(f:{q?:string;state?:string;city?:string;entity_type?:string;near?:string;has_pool?:string;rooms_max?:number}={})=>request<{count:number;properties:Property[]}>(`/api/properties${qs(f)}`),
  property:(pid:number)=>request<PropertyDetail>(`/api/properties/${pid}`),
  propertyFacts:(pid:number)=>request<{facts:Fact[]}>(`/api/properties/${pid}/facts`),
  propertyConnections:(pid:number)=>request<{connections:Connection[]}>(`/api/properties/${pid}/connections`),
  propertyDocuments:(pid:number)=>request<{documents:SourceDoc[]}>(`/api/properties/${pid}/documents`),

  source:(ref:SourceRef)=>request<SourceDoc>(`/api/sources/${ref.sha1}`),
  sourceMeta:(sha1:string)=>request<SourceDoc>(`/api/sources/${sha1}`),
  sourcePage:(sha1:string,page:number)=>request<SignedUrl>(`/api/sources/${sha1}/page/${page}`),
  sourceCrop:(sha1:string,page:number,fact:number)=>request<SignedUrl>(`/api/sources/${sha1}/page/${page}/crop?fact=${fact}`),
  sourceOriginal:(sha1:string)=>request<SignedUrl>(`/api/sources/${sha1}/original`),
}
