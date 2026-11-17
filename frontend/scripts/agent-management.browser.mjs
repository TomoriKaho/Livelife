// Run in an isolated Vite tab; synthetic account/API only, no model calls.
import router from '../src/router/index.ts';
import {writeAuthToken,clearSession,authState} from '../src/api/auth.ts';

export async function verifyAgentManagement(preview = async () => {}) {
  const original=window.fetch, confirm=window.confirm, results=[];
  const rows=[];let creates=0,streams=0,pins=0;
  const now=new Date().toISOString();
  const wait=async f=>{const until=Date.now()+6000;while(!f()){if(Date.now()>until)throw Error('Management UI timeout');await new Promise(r=>setTimeout(r,20));}};
  const click=s=>{const e=document.querySelector(s);if(!e)throw Error('Missing '+s);e.click();};
  const assert=(v,t)=>{if(!v)throw Error(t);results.push(t);};
  try {
    await router.push('/calendar');clearSession();writeAuthToken('management-synthetic');
    window.confirm=()=>true;
    window.fetch=async(url,init={})=>{
      const path=new URL(String(url),location.href).pathname;
      if(path.endsWith('/auth/me'))return Response.json({id:'management-owner',email:'synthetic@pku.edu.cn'});
      if(path.endsWith('/agent/sessions')) {
        if(init.method==='POST'){creates++;const row={session_id:crypto.randomUUID(),title:'首条消息',created_at:now,updated_at:now,expires_at:null,is_pinned:false};rows.push(row);return Response.json(row,{status:201});}
        return Response.json({items:[...rows].sort((a,b)=>Number(b.is_pinned)-Number(a.is_pinned)),next_offset:null});
      }
      if(path.endsWith('/messages/stream')){streams++;return new Response(`event: message_start\ndata: {"message_id":"${crypto.randomUUID()}"}\n\nevent: delta\ndata: {"text":"测试回答"}\n\nevent: done\ndata: {"status":"completed"}\n\n`,{headers:{'Content-Type':'text/event-stream'}});}
      const row=rows.find(r=>path.endsWith('/'+r.session_id));
      if(row){
        if(init.method==='PATCH'){pins++;row.is_pinned=JSON.parse(init.body).is_pinned;return Response.json(row);}
        if(init.method==='DELETE'){rows.splice(rows.indexOf(row),1);return new Response(null,{status:204});}
        return Response.json({...row,messages:[],next_before:null});
      }
      return original(url,init);
    };
    await router.push('/agent');await wait(()=>document.querySelector('textarea')&&!document.querySelector('.history-new')?.disabled);
    click('.history-button');await wait(()=>document.querySelector('.history-new'));
    click('.history-new');click('.history-button');await wait(()=>document.querySelector('.history-new'));click('.history-new');
    click('.history-button');await wait(()=>document.querySelector('.history-temporary'));
    assert(creates===0&&document.querySelectorAll('.history-temporary').length===1,'repeated new and empty history create only one local placeholder');
    click('.drawer-close');const editor=document.querySelector('textarea');editor.value='首条消息';editor.dispatchEvent(new Event('input',{bubbles:true}));
    await wait(()=>!document.querySelector('.send-button').disabled);click('.send-button');await wait(()=>streams===1&&document.querySelector('.rating-action'));
    assert(creates===1,'first send creates exactly one server conversation');
    rows.push({session_id:crypto.randomUUID(),title:'另一个对话',created_at:now,updated_at:now,expires_at:null,is_pinned:false});
    click('.history-button');await wait(()=>document.querySelectorAll('.history-more').length===2);
    document.querySelectorAll('.history-more')[1].click();await wait(()=>document.querySelector('.conversation-menu'));
    click('.conversation-menu button');await wait(()=>pins===1&&!document.querySelector('.conversation-menu'));
    assert(document.querySelector('.history-item strong').textContent.includes('另一个对话'),'pin action moves conversation to top');
    click('.history-more');await wait(()=>document.querySelector('.conversation-menu'));
    assert(document.querySelector('.conversation-menu button').textContent==='取消置顶','menu reflects persisted pin state');
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await wait(()=>!document.querySelector('.conversation-menu'));
    assert(!!document.querySelector('.history-overlay'),'Escape closes menu before drawer');
    click('.history-more');await wait(()=>document.querySelector('.conversation-menu'));await new Promise(r=>setTimeout(r,450));await preview();click('.conversation-menu .menu-delete');
    await wait(()=>rows.length===1&&document.querySelectorAll('.history-more').length===1);
    assert(rows.length===1,'delete is available from compact row menu');
    return results;
  } finally {await router.push('/calendar');window.fetch=original;window.confirm=confirm;clearSession();authState.user=null;}
}
