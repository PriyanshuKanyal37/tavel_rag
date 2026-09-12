import { describe,expect,it } from 'vitest'
import { SSEParser } from './sse'
describe('SSEParser',()=>{it('parses frames split across chunks and multiline data',()=>{const got:any[]=[];const p=new SSEParser(e=>got.push(e));p.push('event: token\ndata: {"text":"hel');p.push('lo"}\n\nevent: done\ndata: {"rounds":2}');p.finish();expect(got).toEqual([{type:'token',text:'hello'},{type:'done',rounds:2}])})
it('turns malformed JSON into an error event',()=>{const got:any[]=[];const p=new SSEParser(e=>got.push(e));p.push('event: token\ndata: nope\n\n');expect(got[0].type).toBe('error')})})
