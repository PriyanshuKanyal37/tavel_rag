import type { StreamEvent } from '../types'
import { humanise } from './errors'

export class StreamDisconnectedError extends Error { constructor(){ super('The stream ended before the answer was saved.'); this.name='StreamDisconnectedError' } }

export async function streamAsk(sessionId:number, question:string, signal:AbortSignal, onEvent:(event:StreamEvent)=>void) {
  const response = await fetch(`/api/chat/sessions/${sessionId}/ask`, { method:'POST', credentials:'include', signal, headers:{'Content-Type':'application/json'}, body:JSON.stringify({question}) })
  if (!response.ok) { let message = `Request failed (${response.status})`; try { const body=await response.json(); message=body.detail?.message || body.detail || body.message || message } catch {} throw Object.assign(new Error(humanise(message)), {status:response.status}) }
  if (!response.body) throw new StreamDisconnectedError()
  const reader=response.body.getReader(), decoder=new TextDecoder()
  let completed = false
  let serverError = false
  const parser = new SSEParser((event) => {
    if (event.type === 'done') completed = true
    if (event.type === 'error') serverError = true
    onEvent(event)
  })
  try {
    while(true){ const {value,done}=await reader.read(); if(done) break; parser.push(decoder.decode(value,{stream:true})) }
    parser.push(decoder.decode()); parser.finish()
    if (!completed && !serverError) throw new StreamDisconnectedError()
  } catch(error) { if ((error as Error).name==='AbortError') throw error; throw error }
}

export class SSEParser {
  private buffer='';
  constructor(private readonly onEvent:(event:StreamEvent)=>void){}
  push(chunk:string){ this.buffer += chunk; let boundary; while((boundary=this.buffer.indexOf('\n\n'))>=0){ const frame=this.buffer.slice(0,boundary); this.buffer=this.buffer.slice(boundary+2); this.emit(frame) } }
  finish(){ if(this.buffer.trim()) this.emit(this.buffer); this.buffer='' }
  private emit(frame:string){ let name='message'; const data:string[]=[]; for(const line of frame.replace(/\r/g,'').split('\n')){ if(line.startsWith('event:')) name=line.slice(6).trim(); else if(line.startsWith('data:')) data.push(line.slice(5).trimStart()) } if(!data.length)return; try { const payload=JSON.parse(data.join('\n')); this.onEvent({type:name,...payload} as StreamEvent) } catch { this.onEvent({type:'error',message:'The server sent an unreadable event.'}) } }
}
