// In an isolated Vite tab: await (await import('/scripts/agent-history.browser.mjs')).verifyAgentHistory()
import router from '../src/router/index.ts';
import {authState,writeAuthToken,clearSession} from '../src/api/auth.ts';

export async function verifyAgentHistory() {
  const originalFetch=window.fetch, originalRoute=router.currentRoute.value.fullPath;
  const savedLocal=localStorage.getItem('livelife.auth.token'), savedTab=sessionStorage.getItem('livelife.auth.token'), savedUser=authState.user;
  const key='livelife.agent.session.v3', savedHint=sessionStorage.getItem(key);
  const a=crypto.randomUUID(),b=crypto.randomUUID(), now=new Date().toISOString();
  const summaries=[{session_id:a,title:'合成会话甲',created_at:now,updated_at:now,expires_at:null},{session_id:b,title:'合成会话乙',created_at:now,updated_at:now,expires_at:null}];
  const message=text=>({id:crypto.randomUUID(),role:'assistant',content:text,status:'completed',citations:[],rating:'like',created_at:now,request_id:crypto.randomUUID()});
  let failList=false, slowB=false, releaseB;
  const results=[];
  const assert=(ok,text)=>{if(!ok)throw Error(text);results.push(text)};
  const wait=async predicate=>{const end=performance.now()+5000;while(!predicate()){if(performance.now()>end)throw Error('History UI did not settle');await new Promise(r=>setTimeout(r,15));}};
  const click=selector=>{const node=document.querySelector(selector);if(!node)throw Error('Missing '+selector);node.click()};
  try {
    await router.push('/calendar');clearSession();writeAuthToken('synthetic-history-token');authState.user={id:'synthetic-history-owner',email:'synthetic@stu.pku.edu.cn'};
    window.fetch=async (url,init)=>{
      const path=new URL(String(url),location.href).pathname;
      if(path.endsWith('/auth/me'))return Response.json(authState.user);
      if(path.endsWith('/agent/sessions')){
        if(failList){failList=false;return Response.json({detail:{code:'unavailable'}},{status:503})}
        return Response.json({items:summaries,next_offset:null});
      }
      const id=path.split('/').at(-1), summary=summaries.find(s=>s.session_id===id);
      if(summary){const result={...summary,messages:[message(id===a?'甲的私有文本':'乙的私有文本')],next_before:null};
        if(id===b&&slowB)return new Promise(resolve=>{releaseB=()=>resolve(Response.json(result))});
        return Response.json(result);
      }
      return originalFetch(url,init);
    };
    await router.push('/agent');await wait(()=>document.querySelector('.message-bubble')?.textContent.includes('甲的私有文本'));
    failList=true;click('.history-button');await wait(()=>document.querySelector('.history-list [role="alert"]'));
    assert(!!document.querySelector('.history-list [role="alert"] button'),'history failure exposes retry');
    click('.history-list [role="alert"] button');await wait(()=>document.querySelectorAll('.history-item').length===2);
    slowB=true;[...document.querySelectorAll('.history-item')].find(n=>n.textContent.includes('会话乙')).click();await wait(()=>releaseB);
    click('.history-button');await wait(()=>document.querySelectorAll('.history-item').length===2);
    [...document.querySelectorAll('.history-item')].find(n=>n.textContent.includes('会话甲')).click();await wait(()=>document.querySelector('.message-bubble')?.textContent.includes('甲的私有文本'));
    releaseB();await new Promise(r=>setTimeout(r,80));
    assert(!document.querySelector('.conversation').textContent.includes('乙的私有文本'),'late B detail cannot overwrite selected A');
    assert(JSON.parse(sessionStorage.getItem(key)).session_id===a,'late B response cannot overwrite active-conversation hint');
    assert(document.querySelector('.rating-action.selected'),'restored feedback remains selected');
    clearSession();await wait(()=>!document.querySelector('.agent-page'));
    assert(sessionStorage.getItem(key)===null,'logout removes active-conversation hint');
    return results;
  } finally {
    releaseB?.();await router.push('/calendar');window.fetch=originalFetch;clearSession();
    if(savedLocal!==null)localStorage.setItem('livelife.auth.token',savedLocal);
    if(savedTab!==null)sessionStorage.setItem('livelife.auth.token',savedTab);
    authState.user=savedUser;if(savedHint!==null)sessionStorage.setItem(key,savedHint);
    await router.push(originalRoute);
  }
}
