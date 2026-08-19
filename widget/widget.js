(()=>{
  const cfg=window.ENGAGEAI_WIDGET_CONFIG||{};
  const API=cfg.apiBaseUrl||'https://YOUR-ACTUAL-BACKEND-URL.onrender.com';
  const ORG=cfg.organizationId;
  if(!ORG){console.error('EngageAI: organizationId is required');return}

  // Keep visitor identity across browser restarts, but keep the active conversation
  // per browser session. A returning visitor therefore gets a new session under
  // the same Visitor record instead of a new visitor inbox card.
  const visitorKey=`engageai:${ORG}:visitor_id`;
  const sessionKey=`engageai:${ORG}:conversation_session`;
  let state=JSON.parse(sessionStorage.getItem(sessionKey)||'{}');
  const rememberedVisitor=localStorage.getItem(visitorKey);
  if(rememberedVisitor) state.visitor_id=rememberedVisitor;

  document.head.insertAdjacentHTML('beforeend',`<link rel="stylesheet" href="${cfg.widgetCssUrl||'../widget/widget.css'}">`);
  document.body.insertAdjacentHTML('beforeend',`<button id="engageai-chat-button">💬</button><div id="engageai-widget"><div class="ea-header"><div><b>${cfg.organizationName||'Assistant'}</b><div class="ea-online">● Online / Available</div></div><button id="ea-close" class="btn btn-sm btn-light">×</button></div><div id="ea-chat" class="ea-chat"></div><div id="ea-loading" class="ea-loading" hidden>Assistant is responding…</div><div class="ea-input"><textarea id="ea-message" rows="2" placeholder="Type your message..."></textarea><button id="ea-send" class="btn btn-primary">Send</button></div><div class="ea-actions"><button id="ea-download" class="btn btn-sm btn-outline-secondary">Download Conversation</button></div></div>`);

  const box=document.querySelector('#ea-chat');
  const send=document.querySelector('#ea-send');
  const input=document.querySelector('#ea-message');
  const loading=document.querySelector('#ea-loading');
  let busy=false;
  let chatEpoch=0;

  function save(){
    if(state.visitor_id) localStorage.setItem(visitorKey,state.visitor_id);
    sessionStorage.setItem(sessionKey,JSON.stringify(state));
  }

  function add(sender,text,time=new Date().toISOString()){
    state.messages=state.messages||[];
    state.messages.push({sender,text,time});
    save();
    render();
  }

  function render(){
    box.innerHTML=(state.messages||[]).map(m=>`<div class="ea-msg ${m.sender}">${escapeHtml(m.text)}<div class="ea-time">${new Date(m.time).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</div></div>`).join('');
    box.scrollTop=box.scrollHeight;
  }

  function escapeHtml(s){
    const d=document.createElement('div');
    d.textContent=s;
    return d.innerHTML.replace(/\n/g,'<br>');
  }

  async function start(){
    if(state.visitor_id&&state.conversation_id)return;
    const r=await fetch(API+'/widget/start',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({organization_id:ORG,visitor_id:state.visitor_id||localStorage.getItem(visitorKey)||null})
    });
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Unable to start chat');
    state.visitor_id=d.visitor_id;
    state.conversation_id=d.conversation_id;
    state.messages=state.messages||[];
    save();
  }

  async function sendMessage(){
    const text=input.value.trim();
    if(!text||busy)return;
    const requestEpoch=chatEpoch;
    busy=true;
    send.disabled=true;
    loading.hidden=false;
    input.value='';
    add('visitor',text);

    try{
      await start();
      const r=await fetch(API+'/widget/chat',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          organization_id:ORG,
          visitor_id:state.visitor_id,
          conversation_id:state.conversation_id,
          message:text
        })
      });
      const d=await r.json();
      if(!r.ok)throw new Error(d.detail||'Chat error');
      if(requestEpoch!==chatEpoch){
        if(d.visitor_id)localStorage.setItem(visitorKey,d.visitor_id);
        return;
      }

      // The backend can reconcile this session with an older visitor record
      // when the same email is supplied. Always keep the canonical visitor id.
      if(d.visitor_id){
        state.visitor_id=d.visitor_id;
        localStorage.setItem(visitorKey,d.visitor_id);
      }
      if(d.conversation_id) state.conversation_id=d.conversation_id;
      save();
      add('agent',d.response);
    }catch(e){
      console.error('EngageAI widget chat error:',e);
      if(requestEpoch===chatEpoch)add('agent','Unable to connect to the assistant.');
    }finally{
      busy=false;
      send.disabled=false;
      loading.hidden=true;
    }
  }

  document.querySelector('#engageai-chat-button').onclick=async()=>{
    document.querySelector('#engageai-widget').style.display='flex';
    document.querySelector('#engageai-chat-button').style.display='none';
    try{
      await start();
      if(!(state.messages||[]).length)add('agent',cfg.welcomeMessage||'Hello! How can I help you?');
    }catch(e){
      console.error('EngageAI widget start error:',e);
      add('agent','Unable to start the conversation.');
    }
  };

  document.querySelector('#ea-close').onclick=()=>{
    document.querySelector('#engageai-widget').style.display='none';
    document.querySelector('#engageai-chat-button').style.display='block';

    // The server already stores the conversation. Closing the widget only clears
    // the visitor-facing UI and ends this active session. The persistent visitor
    // id remains in localStorage, so the next open starts a fresh conversation
    // under the same visitor profile in the owner portal.
    chatEpoch+=1;
    busy=false;
    send.disabled=false;
    loading.hidden=true;
    input.value='';
    state={visitor_id:localStorage.getItem(visitorKey)||state.visitor_id||null};
    sessionStorage.removeItem(sessionKey);
    box.innerHTML='';
  };

  send.onclick=sendMessage;
  input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage()}};
  document.querySelector('#ea-download').onclick=()=>{
    if(state.conversation_id)window.open(`${API}/conversations/${state.conversation_id}/download?format=txt`,'_blank');
  };

  render();
})();
