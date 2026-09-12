import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, RefObject } from 'react'
import { AnswerActions as AnswerActionBar } from './components/AnswerActions'
import { ConfirmDialog } from './components/ConfirmDialog'
import { SourceDialog } from './components/SourceDialog'
import { api, ApiError } from './lib/api'
import { streamAsk } from './lib/sse'
import { renderMarkdown } from './lib/markdown'
import { humanise } from './lib/errors'
import { useTypewriter } from './lib/typewriter'
import { navigate, sourceOf, title as pageTitle, useRoute, withSource } from './lib/router'
import type {Account,Activity,Mode,SavedAnswer,SearchHit,Session,SessionDetail,SourceRef,StreamEvent,Turn} from './types'

const MOBILE=window.matchMedia('(max-width:800px)')
const MOD=/Mac|iPhone|iPad|iPod/.test(navigator.userAgent)?'Cmd':'Ctrl'
// crypto.randomUUID is secure-context only; a plain-http host must not crash mid-stream.
let stepSeq=0; const stepId=()=>`step-${++stepSeq}`
// Plain language, not pipeline vocabulary. The reader is a salesperson waiting
// on an answer, not an engineer watching a retrieval run.
const PHASE:Record<Mode,string>={agent:'Researching the documents',think:'Thinking it through',chat:'Replying',fast:'Searching the documents'}
const numberedSources=(refs:SourceRef[]|undefined):SourceRef[] => (refs||[]).map((ref,index)=>({...ref,n:ref.n??index+1}))
// Evidence is what the answer cited, never what retrieval happened to open.
// Turns saved before this rule still carry the whole retrieved pile, so the
// panel is derived from the marker numbers in the answer itself.
function citedSources(text:string|undefined,refs:SourceRef[]|undefined):SourceRef[]{
  const all=numberedSources(refs); if(!all.length) return []
  const wanted:number[]=[]; for(const m of (text||'').matchAll(/\[(\d{1,3})\]/g)){const n=Number(m[1]); if(!wanted.includes(n)) wanted.push(n)}
  if(!wanted.length) return []
  const picked=wanted.map(n=>all.find(s=>s.n===n)||all[n-1]).filter(Boolean) as SourceRef[]
  // already filtered and renumbered by the backend: nothing to do
  return picked.length?picked:all
}

function App(){
  const route=useRoute()
  const view:'chat'|'saved'=route.name==='saved'?'saved':'chat'
  const selected=route.name==='chat'?route.id:0
  const [savedAnswers,setSavedAnswers]=useState<SavedAnswer[]>([])
  const [account,setAccount]=useState<Account|null>(null),[sessions,setSessions]=useState<Session[]>([]),[detail,setDetail]=useState<SessionDetail>({id:0,title:null,turns:[]}),[sidebarOpen,setSidebarOpen]=useState(()=>!MOBILE.matches),[sourcesOpen,setSourcesOpen]=useState(()=>!MOBILE.matches),[theme,setTheme]=useState<'light'|'dark'>((localStorage.getItem('theme') as 'light'|'dark')||'light'),[draft,setDraft]=useState(''),[streaming,setStreaming]=useState(false),[answer,setAnswer]=useState(''),[activities,setActivities]=useState<Activity[]>([]),[notes,setNotes]=useState(''),[sources,setSources]=useState<SourceRef[]>([]),[selectedSource,setSelectedSource]=useState<SourceRef|null>(null),[streamMeta,setStreamMeta]=useState<{mode?:Mode;rounds?:number;seconds?:number;cost?:number;truncated?:boolean;answerCut?:boolean}>({}),[error,setError]=useState('')
  const [savedSources,setSavedSources]=useState<Set<string>>(new Set())
  const savedIds=new Set(savedAnswers.map(a=>a.id))
  const refreshSaved=useCallback(async()=>{try{setSavedAnswers((await api.savedAnswers()).answers)}catch{/* the Saved view shows its own empty state */}},[])
  const abortRef=useRef<AbortController|null>(null); useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem('theme',theme)},[theme])
  const [isMobile,setIsMobile]=useState(()=>MOBILE.matches)
  useEffect(()=>{const sync=()=>{setIsMobile(MOBILE.matches);setSidebarOpen(!MOBILE.matches);setSourcesOpen(!MOBILE.matches)};MOBILE.addEventListener('change',sync);return()=>MOBILE.removeEventListener('change',sync)},[])
  const scrollRef=useRef<HTMLDivElement|null>(null),stickRef=useRef(true),composerRef=useRef<HTMLTextAreaElement|null>(null),loadedRef=useRef(0)
  // A run is twelve seconds of silence, then everything at once. A ticking
  // counter is the only proof on screen that the wait is progress, not a hang.
  const [elapsed,setElapsed]=useState(0)
  useEffect(()=>{if(!streaming)return;const t0=Date.now();setElapsed(0);const id=setInterval(()=>setElapsed(Math.round((Date.now()-t0)/1000)),1000);return()=>clearInterval(id)},[streaming])
  const shown=useTypewriter(answer,streaming)
  useEffect(()=>{const last=[...detail.turns].reverse().find(t=>t.role==='assistant');setSources(citedSources(last?.text,last?.sources))},[detail])
  const refreshSavedSources=useCallback(async()=>{try{setSavedSources(new Set((await api.savedSources()).sources.map(x=>x.sha1)))}catch{/* the rail still works unsaved */}},[])
  const toggleSource=useCallback(async(sha1:string,next:boolean)=>{setSavedSources(prev=>{const s=new Set(prev);if(next)s.add(sha1);else s.delete(sha1);return s});try{if(next)await api.saveSource(sha1);else await api.unsaveSource(sha1)}catch(e){setError((e as Error).message);void refreshSavedSources()}},[refreshSavedSources])
  useEffect(()=>{if(account){void refreshSaved();void refreshSavedSources()}},[account,refreshSaved,refreshSavedSources])
  useEffect(()=>{const el=scrollRef.current;if(el&&stickRef.current)el.scrollTop=el.scrollHeight})
  useEffect(()=>{(async()=>{try{setAccount(await api.me());setSessions((await api.sessions()).sessions)}catch(e){if(!(e instanceof ApiError&&e.status===401))setError((e as Error).message||'Unable to reach the Travel Inn backend.');setAccount(null);setSessions([])}})()},[])
  const selectSession=useCallback((id:number)=>{navigate({name:'chat',id});if(MOBILE.matches)setSidebarOpen(false)},[])
  // Asking and doing are separate: the question is a themed dialog, and a
  // failure is reported inside it rather than behind it.
  const [pendingDelete,setPendingDelete]=useState<number|null>(null)
  const removeSession=useCallback(async(id:number)=>{await api.remove(id);const rest=sessions.filter(x=>x.id!==id);setSessions(rest);if(selected===id){if(rest[0])navigate({name:'chat',id:rest[0].id},{replace:true});else navigate({name:'new'},{replace:true})}},[sessions,selected])
  const login=async(password:string)=>{try{setAccount(await api.login(password));setSessions((await api.sessions()).sessions)}catch(e){setError((e as Error).message)}}
  const newChat=useCallback(()=>{abortRef.current?.abort();navigate({name:'new'});setDraft('');if(MOBILE.matches)setSidebarOpen(false)},[])
  const submit=async()=>{const q=draft.trim();if(!q||q.length>4000||streaming)return;setDraft('');setError('');setAnswer('');setNotes('');// Show the question immediately. It used to appear only after the stream
    // finished and the conversation was refetched, so pressing Stop, or any
    // failure, left the reader with no record of what they had asked.
    setDetail(d=>({...d,turns:[...d.turns,{seq:(d.turns[d.turns.length-1]?.seq??0)+1,role:'user' as const,text:q,created_at:new Date().toISOString()}]}));stickRef.current=true;setActivities([{id:'mode',label:'Thinking',state:'active'}]);setStreamMeta({});setStreaming(true);abortRef.current=new AbortController(); try{let sid=selected;if(!sessions.some(x=>x.id===sid)){const created=await api.create(q.slice(0,80));setSessions(x=>[created,...x]);sid=created.id;loadedRef.current=sid;navigate({name:'chat',id:sid},{replace:true})}setSessions(x=>x.map(item=>item.id===sid?{...item,last_active:new Date().toISOString()}:item));await streamAsk(sid,q,abortRef.current.signal,(ev)=>handleEvent(ev,sid));const fresh=await api.detail(sid);
      // The saved turn renders the same text, so the live copy must go in the
      // SAME update. It used to be cleared after another await, and React
      // painted in the gap -- which is the answer appearing twice for an instant.
      // Only once the server confirms the save: otherwise a failed write would
      // silently erase the answer from the screen.
      const last=[...fresh.turns].reverse().find(t=>t.role==='assistant');const persisted=!!last?.text?.trim()
      setDetail(fresh);if(persisted){setAnswer('');setActivities([]);setNotes('')}
      setStreaming(false)
      setSessions((await api.sessions()).sessions)}catch(e){if((e as Error).name!=='AbortError'){setError((e as Error).message);setActivities(x=>x.map(a=>({...a,state:'error' as const})))}setStreaming(false)}}
  const advance=(next:Activity)=>setActivities(x=>x.some(a=>a.id===next.id)?x:(x.map(a=>({...a,state:'done' as const})) as Activity[]).concat(next))
  const handleEvent=(ev:StreamEvent,sid:number)=>{if(ev.type==='mode'){setStreamMeta(m=>({...m,mode:ev.mode}));setActivities([{id:'mode',label:PHASE[ev.mode]||'Working on it',detail:ev.why,state:'active'}])}else if(ev.type==='step'){advance({id:ev.missing?`gap-${ev.round}`:stepId(),label:ev.missing?'Looking for what is still missing':ev.source==='calendar'?'Checking the date table':`Read ${ev.opened??ev.found??0} ${(ev.opened??ev.found)===1?'document':'documents'}`,detail:ev.missing||ev.detail||`round ${ev.round||1} · ${ev.found??ev.count??0} matches · ${((ev.chars||0)/1000).toFixed(0)}k characters`,state:'active'})}else if(ev.type==='thought'){setNotes(x=>x?`${x}\n${ev.text}`:ev.text);advance({id:'reason',label:'Working through what it found',state:'active'})}else if(ev.type==='token'){advance({id:'writing',label:'Writing the answer',state:'active'});setAnswer(x=>x+ev.text)}else if(ev.type==='sources')setSources(numberedSources(ev.sources));else if(ev.type==='title'){const named=ev.title;setSessions(x=>x.map(item=>item.id===sid?{...item,title:named}:item));setDetail(d=>d.id===sid||!d.id?{...d,title:named}:d)}else if(ev.type==='compacting')advance({id:'compact',label:'Updating conversation context',detail:`${ev.tokens_before.toLocaleString()} → ${ev.tokens_after.toLocaleString()} tokens`,state:'active'});else if(ev.type==='done')setStreamMeta({mode:ev.mode,rounds:ev.rounds,seconds:ev.seconds,cost:ev.cost_inr,truncated:ev.truncated,answerCut:ev.answer_cut});else if(ev.type==='error')setError(humanise(ev.message))}
  const stop=()=>{abortRef.current?.abort();setStreaming(false);setActivities(x=>(x.map(a=>({...a,state:'done' as const})) as Activity[]).concat({id:'stop',label:'Stopped · partial answer saved',state:'error'}))}
  const [missing,setMissing]=useState(false)
  // The URL decides what is on screen. Reload, Back, Forward and a pasted link
  // all arrive here, and this is the only place a conversation is fetched.
  useEffect(()=>{
    if(!account) return
    if(route.name==='saved'){void refreshSaved();return}
    if(route.name==='notFound'){setMissing(false);return}
    if(route.name==='new'){
      if(loadedRef.current!==0){loadedRef.current=0;setDetail({id:0,title:null,turns:[]});setSources([]);setSelectedSource(null);setAnswer('');setNotes('');setActivities([]);setStreamMeta({});setError('')}
      setMissing(false);return
    }
    if(loadedRef.current===route.id) return
    const want=loadedRef.current=route.id
    setError('');setMissing(false);setSelectedSource(null);setAnswer('');setNotes('');setActivities([]);setStreamMeta({});stickRef.current=true
    // The stale check is "is this STILL the conversation on screen", not a
    // per-run flag. A per-run flag cancelled the request whenever this effect
    // re-ran, and the guard above then refused to ask again -- so a load that
    // outlived one re-render was thrown away and never retried, leaving the
    // start screen on a conversation that had sixty messages in it. React's
    // StrictMode calls api.me() twice on mount, which is enough to trigger it,
    // and the bigger the conversation the wider the window.
    api.detail(want)
      .then(d=>{if(loadedRef.current===want)setDetail(d)})
      .catch(e=>{
        if(loadedRef.current!==want) return
        // a deleted or mistyped conversation is a 404, not a crash
        if(e instanceof ApiError&&e.status===404){setMissing(true);setDetail({id:0,title:null,turns:[]});setSources([])}
        // anything else may be transient, so let a later render ask again
        else {loadedRef.current=0;setError((e as Error).message)}
      })
  },[route,account,refreshSaved])

  const logout=useCallback(()=>{abortRef.current?.abort();api.logout().catch(()=>{});setAccount(null);setSessions([]);setDetail({id:0,title:null,turns:[]});setSources([]);setSelectedSource(null);setActivities([]);setAnswer('');setNotes('');setStreaming(false);setError('');navigate({name:'new'},{replace:true})},[])
  useEffect(()=>{const onKey=(e:KeyboardEvent)=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();newChat()}else if(e.key==='Escape'&&MOBILE.matches){setSidebarOpen(false);setSourcesOpen(false)}};window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey)})
  const deepSource=sourceOf(route)
  const viewing:SourceRef|null=deepSource?{sha1:deepSource.sha1,page:deepSource.page}:null
  const viewSource=useCallback((s:SourceRef)=>{setSelectedSource(s);navigate(withSource(route,{sha1:s.sha1,page:s.page||1}))},[route])
  const closeSource=useCallback(()=>navigate(withSource(route,undefined),{replace:true}),[route])
  const currentTitle=detail.title||sessions.find(s=>s.id===selected)?.title||'New conversation'
  useEffect(()=>{document.title=pageTitle(route,route.name==='chat'?currentTitle:null)},[route,currentTitle])
  if(!account) return <LoginScreen onLogin={login} error={error}/>
  if(route.name==='notFound') return <NotFound path={route.path} onHome={()=>navigate({name:'new'},{replace:true})}/>
  return <div className={`app ${sidebarOpen?'sidebar-open':''}`}>
    <Sidebar open={sidebarOpen} sessions={sessions} selected={selected} account={account} view={view} savedCount={savedAnswers.length} onSaved={()=>{navigate({name:'saved'});void refreshSaved();if(MOBILE.matches)setSidebarOpen(false)}} onChats={()=>{navigate(sessions[0]?{name:'chat',id:sessions[0].id}:{name:'new'});if(MOBILE.matches)setSidebarOpen(false)}} onToggle={()=>setSidebarOpen(!sidebarOpen)} onSelect={selectSession} onNew={newChat} onLogout={logout} onDelete={setPendingDelete} />
    {isMobile&&(sidebarOpen||sourcesOpen)&&<button type="button" className="scrim" aria-label="Close panel" onClick={()=>{setSidebarOpen(false);setSourcesOpen(false)}}/>}
    <main className="workspace">
      <header className="topbar"><button className="icon-btn menu-btn" aria-label={sidebarOpen?'Close navigation':'Open navigation'} onClick={()=>setSidebarOpen(!sidebarOpen)}>☰</button><div className="crumb"><span className="eyebrow">TRAVEL INN / KNOWLEDGE ASSISTANT</span><strong>{currentTitle}</strong></div><div className="top-actions"><button className="theme-btn" onClick={()=>setTheme(theme==='light'?'dark':'light')} aria-label={`Switch to ${theme==='light'?'dark':'light'} mode`}>{theme==='light'?'☾':'☀'}<span>{theme==='light'?'Dark':'Light'}</span></button>{view==='chat'&&<button className="sources-btn" aria-expanded={sourcesOpen} aria-label={`${sourcesOpen?'Hide':'Show'} sources (${sources.length})`} onClick={()=>setSourcesOpen(!sourcesOpen)}><span>Sources</span> <b>{sources.length}</b></button>}</div></header>
      {missing?<NotFound path={`Conversation ${selected}`} gone onHome={()=>navigate({name:'new'},{replace:true})}/>:view==='saved'?<SavedAnswers answers={savedAnswers} sessions={sessions} onChange={refreshSaved} onOpenConversation={selectSession}/>:<div className="content-grid"><section className="chat-column"><div className="chat-statusbar"><span>Knowledge assistant · Travel Inn property documents</span></div><div className="conversation" ref={scrollRef} onScroll={e=>{const el=e.currentTarget;stickRef.current=el.scrollHeight-el.scrollTop-el.clientHeight<80}}>{detail.turns.length===0&&!streaming&&!answer&&<StartHere/>}{detail.turns.map(t=><TurnView key={t.seq} turn={t} sessionId={selected} onSource={viewSource} onSaved={refreshSaved} savedIds={savedIds} who={initials(account.name)}/>) }{(streaming||answer)&&<>{(streaming||!!answer)&&<Thinking items={activities} notes={notes} elapsed={elapsed} writing={!!answer} mode={streamMeta.mode}/>}{answer&&<div className="turn assistant live"><div className="avatar assistant-avatar">TI</div><div className="turn-body"><div className="turn-meta">Travel Inn Assistant <span>Streaming</span></div><div className={`answer ${shown.length<answer.length?'typing':''}`} onClick={e=>{const n=Number((e.target as HTMLElement).dataset.citation);const s=sources.find(x=>x.n===n)??sources.find(x=>x.orig===n);if(s)viewSource(s)}} dangerouslySetInnerHTML={{__html:renderMarkdown(shown)}}/><AnswerActionBar answerId={`live:${selected}`} text={answer} sessionId={selected} saved={false} canSave={false} onSavedChange={refreshSaved}/>{streamMeta.truncated&&<div className="notice amber">Search cut short, so this may be incomplete. Try <button onClick={()=>setDraft('Search harder: '+draft)}>Search harder</button>.</div>}{streamMeta.answerCut&&<div className="notice amber">This answer ran out of room and stops mid-way. Ask for a narrower slice, or <button onClick={()=>setDraft('Continue that answer from where it stopped.')}>continue it</button>.</div>}</div></div>}</>}</div>{error&&<div className="chat-error notice red" role="alert"><span>{error}</span><button className="chat-error-x" onClick={()=>setError('')} aria-label="Dismiss">&times;</button></div>}<Composer value={draft} onChange={setDraft} onSubmit={submit} onStop={stop} streaming={streaming} boxRef={composerRef} narrow={isMobile}/></section>{sourcesOpen&&<EvidenceRail sources={sources} selected={selectedSource} onView={viewSource} onClose={()=>setSourcesOpen(false)} savedSources={savedSources} onToggleSource={toggleSource} answered={detail.turns.some(t=>t.role==='assistant'&&!!t.text?.trim())}/>}</div>}
    </main>
    {pendingDelete!==null&&<ConfirmDialog title="Delete this conversation?" body={`“${sessions.find(x=>x.id===pendingDelete)?.title||'New conversation'}” and every message in it will be removed. This cannot be undone.`} confirmLabel="Delete" danger onConfirm={()=>removeSession(pendingDelete)} onClose={()=>setPendingDelete(null)}/>}
    {viewing&&<SourceDialog source={viewing} onClose={closeSource}/>}
  </div>
}

function NotFound({path,gone,onHome}:{path:string;gone?:boolean;onHome:()=>void}){return <section className="notfound"><div className="start-mark">TI</div><h1>{gone?'That conversation is gone':'Page not found'}</h1><p>{gone?'It may have been deleted, or the link points at a conversation that never existed.':<>Nothing lives at <code>{path}</code>.</>}</p><button className="primary-btn compact" onClick={onHome}>Start a new conversation</button></section>}

function SavedAnswers({answers,sessions,onChange,onOpenConversation}:{answers:SavedAnswer[];sessions:Session[];onChange:()=>void;onOpenConversation:(id:number)=>void}){return <section className="saved-view"><div className="saved-header"><div><span className="eyebrow">WORKSPACE</span><h1>Saved answers</h1><p>Keep useful, source-backed responses close at hand.</p></div><span className="saved-total">{answers.length} {answers.length===1?'answer':'answers'}</span></div>{answers.length===0?<div className="saved-empty"><span>☆</span><h2>No saved answers yet</h2><p>Use “Save answer” beneath any response to keep it here.</p></div>:<div className="saved-list">{[...answers].reverse().map(answer=>{const session=answer.session_id?sessions.find(item=>item.id===answer.session_id):null;return <article className="saved-card" key={answer.id}><div className="saved-card-meta"><span>Saved {formatSavedDate(answer.saved_at)}</span>{session&&<button className="saved-source-link" onClick={()=>onOpenConversation(session.id)}>Open conversation →</button>}</div><div className="saved-card-text" dangerouslySetInnerHTML={{__html:renderMarkdown(answer.text)}}/><AnswerActionBar answerId={answer.id} text={answer.text} sessionId={answer.session_id??null} saved onSavedChange={onChange}/></article>})}</div>}</section>}
function formatSavedDate(value?:string){const date=new Date(value||'');return Number.isNaN(date.getTime())?'Recently':date.toLocaleDateString(undefined,{month:'short',day:'numeric'})}
function LoginScreen({onLogin,error}:{onLogin:(p:string)=>Promise<void>|void;error:string}){const[p,setP]=useState(''),[busy,setBusy]=useState(false),[show,setShow]=useState(false);const submit=async(e:FormEvent)=>{e.preventDefault();if(busy||!p)return;setBusy(true);try{await onLogin(p)}finally{setBusy(false)}};return <div className="login-screen"><div className="login-card"><div className="brand-mark">TI</div><span className="eyebrow">TRAVEL INN</span><h1>Knowledge Assistant</h1><p>Ask questions across Travel Inn's property documents and get answers with their sources.</p><form onSubmit={submit}><label>Workspace password<div className="pw-field"><input autoFocus type={show?'text':'password'} autoComplete="current-password" value={p} disabled={busy} onChange={e=>setP(e.target.value)} placeholder="Enter password"/><button type="button" className="pw-eye" onClick={()=>setShow(v=>!v)} disabled={busy} aria-label={show?'Hide password':'Show password'} aria-pressed={show} title={show?'Hide password':'Show password'}>{show?<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" d="M3 3l18 18M10.6 10.7a2 2 0 002.8 2.8M9.4 5.3A9.5 9.5 0 0112 5c5 0 9 4.5 9 7a12 12 0 01-2.4 3.3M6.3 6.9A12.4 12.4 0 003 12c0 2.5 4 7 9 7a9.6 9.6 0 003.9-.8"/></svg>:<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" d="M3 12s3.6-7 9-7 9 7 9 7-3.6 7-9 7-9-7-9-7z"/><circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" strokeWidth="1.7"/></svg>}</button></div></label><button className="primary-btn" disabled={busy||!p}>{busy?'Signing in…':'Continue'} <span>↗</span></button></form>{error&&<div className="notice red" role="alert">{error}</div>}<small>Shared workspace · source-backed answers</small></div></div>}
function Sidebar({open,sessions,selected,account,view,savedCount,onSaved,onChats,onToggle,onSelect,onNew,onLogout,onDelete}:{open:boolean;sessions:Session[];selected:number;account:Account;view:'chat'|'saved';savedCount:number;onSaved:()=>void;onChats:()=>void;onToggle:()=>void;onSelect:(id:number)=>void;onNew:()=>void;onLogout:()=>void;onDelete:(id:number)=>void}){const[query,setQuery]=useState('');const q=query.trim();const[hits,setHits]=useState<SearchHit[]|null>(null);const[searching,setSearching]=useState(false);const seq=useRef(0)
  // Debounced, and answered on the server because the message text lives there.
  // The token guards against a slow early request landing after a fast late one.
  useEffect(()=>{if(!q){setHits(null);setSearching(false);return}
    setSearching(true);const mine=++seq.current
    const timer=setTimeout(()=>{api.searchChats(q).then(r=>{if(mine===seq.current){setHits(r.results);setSearching(false)}}).catch(()=>{if(mine===seq.current){setHits([]);setSearching(false)}})},220)
    return()=>clearTimeout(timer)},[q])
  const grouped=groupSessions(sessions);return <aside className={`sidebar ${open?'':'collapsed'}`}><div className="side-head"><div className="brand"><div className="brand-mark">TI</div><div><strong>Travel Inn</strong><span>Knowledge desk</span></div></div><button className="icon-btn" onClick={onToggle} aria-label="Close navigation">&larr;</button></div><button className="new-chat" onClick={onNew}><span>&#43;</span> New conversation <kbd>{MOD} K</kbd></button><div className="side-label">Your workspace <span>&#8942;</span></div><button className={`nav-item ${view==='chat'?'active':''}`} onClick={onChats}>&bull; <span>All conversations</span></button><div className="history-head"><span>Recent conversations</span></div><div className="search-row"><span className="search-icon" aria-hidden="true">&#8981;</span><input className="search-input" type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search conversations" aria-label="Search conversations"/>{q&&<button className="search-clear" onClick={()=>setQuery('')} aria-label="Clear search">&times;</button>}</div><div className="history">{hits===null?grouped.map(group=><section className="history-group" key={group.label}><div className="history-group-label">{group.label}</div>{group.sessions.map(s=><HistoryRow key={s.id} id={s.id} title={s.title} note={formatSessionTime(s.last_active)} selected={selected===s.id} onSelect={onSelect} onDelete={onDelete}/>)}</section>):<section className="history-group">{hits.map(h=><HistoryRow key={h.id} id={h.id} title={h.title} note={formatSessionTime(h.last_active)} snippet={h.snippet} selected={selected===h.id} onSelect={onSelect} onDelete={onDelete}/>)}</section>}{q&&searching&&hits===null&&<p className="history-none">Searching…</p>}{q&&hits!==null&&hits.length===0&&!searching&&<p className="history-none">Nothing matches “{q}”, in any conversation name or message.</p>}</div><div className="side-bottom"><button className={`nav-item ${view==='saved'?'active':''}`} onClick={onSaved}>&#9734; <span>Saved answers</span>{savedCount>0&&<b className="saved-count">{savedCount}</b>}</button><div className="profile"><div className="avatar profile-avatar">{initials(account.name)}</div><span><strong>{account.name}</strong><small>{account.email}</small></span><ProfileMenu account={account} onLogout={onLogout}/></div></div></aside>}

// The three dots used to BE the sign-out button: one stray click and you were
// back at the password screen. They open a menu now, and signing out is a
// deliberate second click inside it.
function ProfileMenu({account,onLogout}:{account:Account;onLogout:()=>void}){
  const [open,setOpen]=useState(false)
  const ref=useRef<HTMLDivElement|null>(null)
  useEffect(()=>{if(!open)return
    const away=(e:MouseEvent)=>{if(!ref.current?.contains(e.target as Node))setOpen(false)}
    const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false)}
    document.addEventListener('mousedown',away);window.addEventListener('keydown',key)
    return()=>{document.removeEventListener('mousedown',away);window.removeEventListener('keydown',key)}},[open])
  return <div className="profile-menu" ref={ref}>
    <button className="icon-btn" aria-haspopup="menu" aria-expanded={open} onClick={()=>setOpen(o=>!o)} aria-label="Account menu" title="Account">&#8942;</button>
    {open&&<div className="menu" role="menu">
      <div className="menu-who"><strong>{account.name}</strong><small>{account.email}</small></div>
      <button type="button" role="menuitem" className="menu-item danger" onClick={()=>{setOpen(false);onLogout()}}>Sign out</button>
    </div>}
  </div>
}
// One row, whether it came from the list or from a search. A search row also
// shows the sentence that matched, so a hit inside an answer explains itself.
function HistoryRow({id,title,note,snippet,selected,onSelect,onDelete}:{id:number;title:string|null;note:string;snippet?:string|null;selected:boolean;onSelect:(id:number)=>void;onDelete:(id:number)=>void}){
  const name=title||'New conversation'
  return <div className={`history-item ${selected?'selected':''}`}>
    <button className="history-open" onClick={()=>onSelect(id)}><span><strong>{name}</strong>{snippet?<Snippet text={snippet}/>:<small>{note}</small>}</span></button>
    <button className="history-del" onClick={()=>onDelete(id)} aria-label={`Delete ${name}`} title="Delete conversation">&times;</button>
  </div>
}
// Answers are stored as markdown, so a raw excerpt arrives full of ** and [12]
// and bullet dashes. Strip the FORMATTING only -- no word is ever inspected.
const plain=(s:string)=>s
  .replace(/\[\d{1,3}\]/g,'')            // citation markers
  .replace(/[*_`#>]/g,'')                 // bold, italic, code, heading marks
  .replace(/^\s*[-+]\s+/gm,'')            // list bullets
  .replace(/\s+/g,' ')
// Postgres marks the matched words with <b>. Split on them and render text
// nodes: nothing from a document is ever handed to the browser as HTML.
function Snippet({text}:{text:string}){const parts=text.split(/<\/?b>/);return <small className="history-snip">{parts.map((part,i)=>i%2?<mark key={i}>{plain(part)}</mark>:<span key={i}>{plain(part)}</span>)}</small>}

type SessionGroup={label:string;sessions:Session[]}
function sessionDate(value?:string){if(!value)return null;const text=value.trim();const now=new Date();const relative=text.match(/^(just now|today|yesterday|tomorrow)(?:\s+[^0-9]*\s*(\d{1,2}):(\d{2})\s*(am|pm)?)?/i);if(relative){const d=new Date(now);const kind=relative[1].toLowerCase();if(kind==='yesterday')d.setDate(d.getDate()-1);if(kind==='tomorrow')d.setDate(d.getDate()+1);if(relative[2]){let hour=Number(relative[2]);const minute=Number(relative[3]);if(relative[4]?.toLowerCase()==='pm'&&hour<12)hour+=12;if(relative[4]?.toLowerCase()==='am'&&hour===12)hour=0;d.setHours(hour,minute,0,0)}return d}const parsed=new Date(text);return Number.isNaN(parsed.getTime())?null:parsed}
function groupSessions(sessions:Session[]):SessionGroup[]{const now=new Date();const day=(d:Date)=>new Date(d.getFullYear(),d.getMonth(),d.getDate()).getTime();const today=day(now);const groups:Record<string,Session[]>={Tomorrow:[],Today:[],Yesterday:[],Earlier:[]};for(const s of sessions){const d=sessionDate(s.last_active);// No timestamp means the server has not described this row yet, which only happens to one this browser just created. That belongs at the top of today, not a thousand days in the past.
  const delta=d?Math.round((day(d)-today)/86400000):0;const label=delta===1?'Tomorrow':delta===0?'Today':delta===-1?'Yesterday':'Earlier';groups[label].push(s)}for(const list of Object.values(groups))list.sort((a,b)=>(sessionDate(b.last_active)?.getTime()??Date.now())-(sessionDate(a.last_active)?.getTime()??Date.now()));return ['Tomorrow','Today','Yesterday','Earlier'].filter(label=>groups[label].length).map(label=>({label,sessions:groups[label]}))}
function formatSessionTime(value?:string){if(!value)return 'Just now';if(/^(Today|Yesterday|Tomorrow)/i.test(value))return value;const d=sessionDate(value);if(!d)return value;return d.toLocaleDateString(undefined,{month:'short',day:'numeric'})+' '+String.fromCharCode(183)+' '+d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'})}
function TurnView({turn,sessionId,onSource,onSaved,savedIds,who}:{turn:Turn;sessionId:number;onSource:(s:SourceRef)=>void;onSaved:()=>void;savedIds:Set<string>;who:string}){if(turn.role==='user')return <div className="turn user"><div className="avatar user-avatar">{who}</div><div className="turn-body"><div className="turn-meta">You <span>{formatTurnTime(turn.created_at)}</span></div><p>{turn.text}</p></div></div>;if(!turn.text?.trim())return <div className="turn assistant"><div className="avatar assistant-avatar">TI</div><div className="turn-body"><div className="turn-meta">Travel Inn Assistant</div><p className="turn-failed">This answer didn&rsquo;t complete. Ask again, or rephrase the question.</p></div></div>;const cited=citedSources(turn.text,turn.sources);return <div className="turn assistant"><div className="avatar assistant-avatar">TI</div><div className="turn-body"><div className="turn-meta">Travel Inn Assistant <span>{cited.length?'Source-backed':'No sources cited'}</span></div><div className="answer" onClick={e=>{const n=Number((e.target as HTMLElement).dataset.citation);const s=cited.find(x=>x.n===n)??cited.find(x=>x.orig===n);if(s)onSource(s)}} dangerouslySetInnerHTML={{__html:renderMarkdown(turn.text)}}/>{!!cited.length&&<div className="evidence-row"><strong className="evidence-title">Evidence</strong><span className="evidence-sub">{cited.length} {cited.length===1?'source':'sources'}</span><button className="link-button" onClick={()=>onSource(cited[0])}>Open sources →</button></div>}{turn.status==='cut'&&<div className="notice amber">This answer ran out of room and stops mid-sentence. Ask it again, or ask for a narrower slice.</div>}{turn.status==='interrupted'&&<div className="notice amber">This answer was interrupted before it finished.</div>}<AnswerActionBar answerId={`${sessionId}:${turn.seq}`} text={turn.text} sessionId={sessionId} saved={savedIds.has(`${sessionId}:${turn.seq}`)} onSavedChange={onSaved}/></div></div>}

function StartHere(){return <div className="start-here"><div className="start-mark">TI</div><h1>Ask about any Travel Inn property</h1><p>Rates, rooms, amenities, distances, dates &mdash; ask the way you would ask a colleague. Every answer comes back with the document and page behind it.</p></div>}

// One quiet line, closed by default. Retrieval rounds and the model's own
// reasoning are diagnostics: available on a click, never in the reader's way.
function Thinking({items,notes,elapsed,writing,mode}:{items:Activity[];notes:string;elapsed:number;writing:boolean;mode?:Mode}){
  const [open,setOpen]=useState(false)
  const failed=items.some(i=>i.state==='error')
  const done=failed?'Stopped':mode==='chat'?`Replied in ${elapsed}s`:`Thought for ${elapsed}s`
  const label=writing||failed?done:items.find(i=>i.state==='active')?.label||'Thinking'
  const busy=!writing&&!failed
  // Small talk has one step and no reasoning behind it. Offering a disclosure
  // that opens onto nothing is worse than not offering one.
  const expandable=!!notes||items.length>1
  return <div className={`thinking ${open&&expandable?'open':''}`}>
    <button type="button" className="thinking-head" disabled={!expandable} aria-expanded={expandable?open:undefined} onClick={()=>setOpen(!open)}>
      {busy?<span className="dots" aria-hidden="true"><i/><i/><i/></span>:<span className="thinking-mark" aria-hidden="true">{failed?'!':'✓'}</span>}
      <span className="thinking-label">{label}</span>
      {busy&&<span className="thinking-elapsed">{elapsed}s</span>}
      {expandable&&<span className="thinking-caret" aria-hidden="true">{open?'⌃':'⌄'}</span>}
    </button>
    {open&&expandable&&<div className="thinking-body">
      {items.map(i=>{const state=writing&&i.state==='active'?'done':i.state;return <div className={`thinking-step ${state}`} key={i.id}><span aria-hidden="true">{state==='done'?'✓':state==='error'?'!':'◌'}</span><div><strong>{i.label}</strong>{i.detail&&<small>{i.detail}</small>}</div></div>})}
      {/* The model writes its notes in markdown it never meant anyone to read;
          the stars are noise in a panel that is already plain text. */}
      {notes&&<><strong className="thinking-notes-title">Its own notes</strong><p className="thinking-notes">{notes.replace(/\*\*/g,'')}</p></>}
    </div>}
  </div>
}
function Composer({value,onChange,onSubmit,onStop,streaming,boxRef,narrow}:{value:string;onChange:(v:string)=>void;onSubmit:()=>void;onStop:()=>void;streaming:boolean;boxRef:RefObject<HTMLTextAreaElement|null>;narrow:boolean}){useEffect(()=>{const el=boxRef.current;if(!el)return;el.style.height='auto';el.style.height=`${Math.min(el.scrollHeight,160)}px`},[value]);return <div className="composer-wrap"><div className="composer"><textarea ref={boxRef} aria-label="Ask a question" value={value} onChange={e=>onChange(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();onSubmit()}}} placeholder={narrow?"Ask about a property…":"Ask about properties, amenities, distances, or dates…"} maxLength={4000} rows={1}/>{streaming?<button className="stop-btn" onClick={onStop}>■ <span>Stop</span></button>:<button className="send-btn" disabled={!value.trim()} onClick={onSubmit} aria-label="Send question">&#8593;</button>}</div><div className="composer-meta"><span>Enter to send · Shift + Enter for new line</span></div></div>}
// Corpus paths use Windows separators ("State\City\File.pdf"), so splitting on
// "/" alone left the whole path as the card title.
function fileName(path?:string|null){if(!path)return '';const parts=path.split(/[\\/]/).filter(Boolean);return parts[parts.length-1]||path}
function formatTurnTime(value?:string){if(!value)return 'Just now';const d=new Date(value);if(Number.isNaN(d.getTime()))return value;const today=new Date();const sameDay=d.toDateString()===today.toDateString();const time=d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});return sameDay?time:`${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} · ${time}`}
const sourceKey=(s:SourceRef)=>`${s.sha1}:${s.page??''}`
function initials(name?:string){const parts=(name||'').trim().split(/\s+/).filter(Boolean);if(!parts.length)return 'TI';return (parts[0][0]+(parts.length>1?parts[parts.length-1][0]:'')).toUpperCase()}
// One card must not cost one API call. Fifty-two cards used to mint fifty-two
// presigned URLs on mount, saturating the browser's six connections per origin
// and stalling every click behind them. The page render belongs in the viewer,
// which loads exactly one source: the selected one.
const sourceLabel=(s:SourceRef)=>fileName(s.rel_path)||'Approved property record'
function SourceCard({source,selected,onView,onSave,saved}:{source:SourceRef;selected:boolean;onView:()=>void;onSave:()=>void;saved:boolean}){const ext=(source.rel_path?.split('.').pop()||'doc').toUpperCase();return <article className={`source-card ${selected?'selected':''}`}><button className="source-card-trigger" onClick={onView}><span className="source-body"><span className="source-kind" aria-hidden="true">{ext}</span><strong>{sourceLabel(source)}</strong><small>Page {source.page||'—'} · SHA {source.sha1.slice(0,8)}</small></span></button><div className="source-actions"><button onClick={onView}>View source</button><button onClick={onSave} aria-pressed={saved}>{saved?'Saved':'Save source'}</button></div></article>}
function EvidenceRail({sources,selected,onView,onClose,savedSources,onToggleSource,answered}:{sources:SourceRef[];selected:SourceRef|null;onView:(s:SourceRef)=>void;onClose:()=>void;savedSources:Set<string>;onToggleSource:(sha1:string,next:boolean)=>void;answered:boolean}){return <aside className="evidence" aria-label="Sources"><div className="evidence-head"><div><span className="eyebrow">EVIDENCE</span><h2>Sources</h2></div><button className="icon-btn" onClick={onClose} aria-label="Collapse sources">&rarr;</button></div><p className="evidence-intro">Every claim is tied to a Travel Inn document.</p>{sources.length===0&&(answered?<div className="source-empty"><span>&#8961;</span><strong>No documents cited</strong><p>This answer didn&rsquo;t quote anything from the corpus, so there is nothing to show here.</p></div>:<div className="source-empty"><span>&#8961;</span><strong>No sources yet</strong><p>Ask a question to see the documents behind each answer.</p></div>)}<div className="source-list">{sources.map(s=><SourceCard key={sourceKey(s)} source={s} selected={sourceKey(selected||{sha1:''})===sourceKey(s)} onView={()=>onView(s)} onSave={()=>onToggleSource(s.sha1,!savedSources.has(s.sha1))} saved={savedSources.has(s.sha1)}/>)}</div></aside>}

export default App








