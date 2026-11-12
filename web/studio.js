(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  const pages = [
    {id:'openai',title:'OpenAI 订阅',en:'SUBSCRIPTION',desc:'ChatGPT 功能额度、共享额度与真实续费状态。',hint:'ChatGPT 深度研究、图像额度与 Work/Codex 共享额度分别展示。读取实际账期和续费时间，不推算未提供的限额或扣款。',path:'M4 4h16v16H4zM8 9h8M8 13h5M8 17h8'},
    {id:'system',title:'性能脉搏',en:'SYSTEM',desc:'看见电脑此刻的工作状态。',hint:'数据来自当前电脑。无法读取的传感器保留为「未接入」。',path:'M4 4h16v16H4zM8 1v3m4-3v3m4-3v3M8 20v3m4-3v3m4-3v3M1 8h3m-3 4h3m-3 4h3m16-8h3m-3 4h3m-3 4h3M8 8h8v8H8z'},
    {id:'network',title:'网络航道',en:'NETWORK',desc:'上传、下载，流动一目了然。',hint:'曲线只记录实际流量。网卡活跃不代表所有网站或代理服务都可达。',path:'M7 3v16m-4-4 4 4 4-4M17 21V5m-4 4 4-4 4 4'},
    {id:'clock',title:'此时此刻',en:'CLOCK',desc:'此地与远方，共享一个当下。',hint:'本地时间固定使用北京时间。伦敦和纽约自动跟随各自的夏令时规则。',path:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 6v6l4 3'},
    {id:'focus',title:'专注空间',en:'FOCUS',desc:'为眼前这一件事，留一段时间。',hint:'计时由工作台保存。可以切换页面，专注计时仍会继续。',path:'M9 2h6m-3 0v3M19 6l2-2M20 14a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM12 9v5l3 2'},
    {id:'ambient',title:'动画实验室',en:'ANIMATION',desc:'四种动态画面，找到你的桌边节奏。',hint:'轨道、极光、流场与星际漫游。可调速度、细节与时钟；浏览器预览比实体屏更新更快，实屏速度以实测为准。',path:'M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM2 19 22 5M9 8l6 8'},
    {id:'media',title:'音乐一隅',en:'MEDIA',desc:'留一个位置，给喜欢的声音。',hint:'当前版本尚未接入播放器。封面、曲目和播放进度留作下一步扩展。',path:'M9 18V5l11-2v13M9 5v4l11-2M9 18c0 2-6 3-6 0s6-3 6 0ZM20 16c0 2-6 3-6 0s6-3 6 0Z'},
    {id:'guide',title:'更多可能',en:'EXPLORE',desc:'从一块小屏，展开更多日常。',hint:'区分已经实现的软件能力、等待接入的数据源，以及仍需实测的硬件能力。',path:'M12 2v5m0 10v5M2 12h5m10 0h5M5 5l4 4m6 6 4 4M5 19l4-4m6-6 4-4M9 9h6v6H9z'},
    {id:'calibrate',title:'显示校准',en:'CALIBRATE',desc:'找到合适的方向、亮度和阅读距离。',hint:'确认四角都能看见、圆形没有拉伸、灰阶可区分，再选择舒适的字号和亮度。',path:'M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5M8 12h8m-4-4v8'}
  ];
  let state = null, metrics = null, busy = false, noteDirty = false, infoLoaded = false, noticeTimer, lastError = null;
  $('page-list').innerHTML = pages.map(p=>`<button class="page-button" data-page="${p.id}" aria-current="${p.id==='system'}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${p.path}"/></svg><span class="page-label"><strong>${p.title}</strong><small>${p.en}</small></span></button>`).join('');
  function notify(message,success=false,persistent=false){clearTimeout(noticeTimer);$('notice').textContent=message;$('notice').classList.toggle('success',success);$('notice').hidden=false;if(!persistent)noticeTimer=setTimeout(()=>$('notice').hidden=true,6000);}
  function setConnection(text,kind=''){const e=$('connection');e.className='connection '+kind;e.querySelector('span').textContent=text;}
  async function request(url,options={}){const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),15000);try{const r=await fetch(url,{cache:'no-store',...options,signal:controller.signal});let data;try{data=await r.json();}catch{throw new Error('工作台没有返回有效响应。');}if(!r.ok||data?.ok===false)throw new Error(data?.error||data?.message||'操作未完成，请重试。');return data;}finally{clearTimeout(timeout);}}
  function previewSize(){const portrait=state?[0,180].includes(Number(state.rotation)):false;const box=$('preview-box'),frame=$('display-preview');box.classList.toggle('portrait',portrait);box.parentElement.classList.toggle('portrait',portrait);const w=portrait?720:1280,h=portrait?1280:720;frame.style.width=w+'px';frame.style.height=h+'px';frame.style.transform=`scale(${box.clientWidth/w})`;$('resolution-label').textContent=`${w} × ${h} · ${portrait?'竖屏':'横屏'}`;}
  const focusTime = seconds => {const n=Math.max(0,Math.ceil(finite(seconds)?seconds:1500));return `${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;};
  function applyState(next){
    if(!next||typeof next!=='object')return;state=next;const p=pages.find(x=>x.id===state.page)||pages[0];
    document.body.classList.toggle('openai-workbench',state.page==='openai');
    document.querySelectorAll('.page-button').forEach(b=>b.setAttribute('aria-current',String(b.dataset.page===p.id)));
    $('page-title').textContent=p.title;$('page-description').textContent=p.desc;$('scene-guidance').textContent=p.hint;
    for(const key of ['rotation','fps','interval']){if(state[key]!=null&&document.activeElement!==$(key)){if(!Array.from($(key).options).some(o=>o.value===String(state[key])))$(key).add(new Option(String(state[key]),String(state[key])));$(key).value=String(state[key]);}}
    $('auto').checked=Boolean(state.auto);$('interval').disabled=!state.auto;
    const connected=Boolean(state.connected),streaming=Boolean(state.streaming);setConnection(streaming?'正在投屏':connected?'设备已连接':'工作台已连接',streaming?'active':'online');
    $('start-button').disabled=streaming||busy;$('start-button').textContent=streaming?'正在投屏':'开始投屏';$('stop-button').disabled=!streaming&&!connected||busy;
    $('output-summary').textContent=state.error?'上次输出遇到问题，请查看下方提示。':streaming?'当前画面正在发送到 USB 副屏。':'浏览器预览可用。开始后发送到实体屏。';
    $('preview-status').textContent=streaming?(finite(state.stats?.effective_fps)?`实际发送 ${state.stats.effective_fps.toFixed(2)} fps`:'正在测量发送速度'):'浏览器预览';
    $('brightness').disabled=!connected||busy;$('brightness').title=connected?'调整实体屏亮度':'开始投屏后可调整亮度';
    if(finite(state.brightness)){$('brightness-value').textContent=state.brightness+'%';if(document.activeElement!==$('brightness'))$('brightness').value=state.brightness;}else $('brightness-value').textContent='未读取';
    const stats=state.stats||{};$('stat-frames').innerHTML=`${finite(stats.frames)?stats.frames.toLocaleString():'0'} <small>帧</small>`;$('stat-latency').innerHTML=`${finite(stats.last_ms)?stats.last_ms.toFixed(0):'—'} <small>ms</small>`;$('stat-bytes').innerHTML=`${finite(stats.bytes)&&stats.bytes>0?(stats.bytes/1048576).toFixed(2):'—'} <small>MiB</small>`;
    const focus=state.focus||{};$('focus-time').textContent=focusTime(focus.remaining);$('focus-state').textContent=focus.remaining===0?'本轮完成':focus.running?'专注中':focus.remaining<focus.duration?'已暂停':'准备开始';$('focus-start').textContent=focus.running?'暂停':'开始专注';
    if(!noteDirty&&document.activeElement!==$('note')){$('note').value=state.note||'';$('note-count').textContent=$('note').value.length+' / 160';}
    if(state.error&&state.error!==lastError){notify(String(state.error),false,true);lastError=state.error;}else if(!state.error)lastError=null;
    const motion=state.animation||{};
    $('subscription-controls').hidden=state.page!=='openai';
    if(document.activeElement!==$('subscription-view'))$('subscription-view').value=state.subscription_view||'overview';
    $('subscription-auto').checked=Boolean(state.subscription_auto);
    const subscription=state.subscription||{},buckets=subscription.buckets||[];
    const bucketOptions=buckets.map(b=>`<option value="${safe(b.id)}">${safe(b.name||(b.id==='codex'?'Work / Codex':b.id))}</option>`).join('');
    if($('subscription-bucket').innerHTML!==bucketOptions)$('subscription-bucket').innerHTML=bucketOptions;
    $('subscription-bucket-row').hidden=buckets.length<2;
    if(document.activeElement!==$('subscription-bucket'))$('subscription-bucket').value=buckets.some(b=>b.id===state.subscription_bucket)?state.subscription_bucket:buckets[0]?.id||'';
    const subscriptionTime=subscription.observed_at?new Date(subscription.observed_at*1000).toLocaleTimeString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):null;
    const chatgpt=subscription.chatgpt_feature_limits||{},billing=subscription.billing||{};
    const sourceTime=s=>s.observed_at?new Date(s.observed_at*1000).toLocaleTimeString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未同步';
    $('subscription-status').textContent=subscription.refreshing?'正在刷新订阅数据…':chatgpt.error||billing.error||subscription.error||`ChatGPT ${sourceTime(chatgpt)} · Work ${subscriptionTime||'未同步'} · 续费 ${sourceTime(billing)}`;
    $('subscription-refresh').disabled=busy||Boolean(subscription.refreshing);
    $('animation-controls').hidden=state.page!=='ambient';
    for(const [key,id] of [['preset','animation-preset'],['detail','animation-detail']])if(motion[key]!==undefined&&document.activeElement!==$(id))$(id).value=motion[key];
    if(document.activeElement!==$('animation-speed'))$('animation-speed').value=motion.speed||1;
    $('animation-speed-value').textContent=Number(motion.speed||1).toFixed(2)+'×';
    $('animation-clock').checked=motion.show_clock!==false;
    $('animation-pause').textContent=motion.paused?'继续动画':'暂停动画';$('animation-pause').setAttribute('aria-pressed',String(!!motion.paused));
    $('animation-performance').textContent=streaming&&finite(stats.last_frame_bytes)?`实际 ${Number(stats.effective_fps||0).toFixed(1)} fps · 每帧 ${(stats.last_frame_bytes/1024).toFixed(0)} KiB\n绘制 ${Number(stats.render_ms||0).toFixed(0)} ms · 转换 ${Number(stats.encode_ms||0).toFixed(0)} ms · 传输 ${Number(stats.last_ms||0).toFixed(0)} ms`:'开始投屏后显示本机实际速度。';
    previewSize();
  }
  function applyMetrics(data){metrics=data;if(state?.page==='openai'){const sub=state.subscription||{},sources=[sub,sub.chatgpt_feature_limits||{},sub.billing||{}],old=s=>s.status==='stale'||s.observed_at&&Date.now()/1000-s.observed_at>(s.stale_seconds||180);$('data-state').textContent=sources.some(old)?'部分来源已过期':sources.every(s=>s.status==='live')?'订阅已同步':sub.status==='disconnected'?'账户未连接':sources.some(s=>s.status==='error')?'部分来源未同步':'订阅同步中';return;}const age=data?.timestamp?Date.now()-Date.parse(data.timestamp):Infinity;$('data-state').textContent=!data?.timestamp?'等待采样':age>6500?'数据已过期':'本机实时';}
  async function control(patch,success){
    const isOutput=patch.action==='start'||patch.action==='stop';if(isOutput&&busy)return;
    if(isOutput){busy=true;document.body.classList.add('busy');$('start-button').disabled=true;$('stop-button').disabled=true;notify(patch.action==='start'?'正在连接副屏并准备画面…':'正在停止输出…',false,true);}
    try{const next=await request('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});applyState(next.state||next);if(success)notify(success,true);else if(isOutput)$('notice').hidden=true;if(next.error)notify(next.error,false,true);return true;}catch(e){notify(e.name==='AbortError'?'操作等待超时，请检查设备连接后重试。':e.message,false,true);return false;}finally{if(isOutput){busy=false;document.body.classList.remove('busy');if(state)applyState(state);}}
  }
  async function poll(){try{const [s,m]=await Promise.all([request('/api/state'),request('/api/metrics')]);if(!busy)applyState(s);applyMetrics(m);}catch{setConnection('工作台连接中断','error');$('data-state').textContent=metrics?'数据已过期':'等待连接';$('preview-status').textContent='保留最近预览';$('start-button').disabled=true;$('stop-button').disabled=true;$('brightness').disabled=true;}}
  $('animation-preset').addEventListener('change',e=>control({animation:{preset:e.target.value}}));
  $('animation-speed').addEventListener('input',e=>$('animation-speed-value').textContent=Number(e.target.value).toFixed(2)+'×');
  $('animation-speed').addEventListener('change',e=>control({animation:{speed:Number(e.target.value)}}));
  $('animation-detail').addEventListener('change',e=>control({animation:{detail:e.target.value}}));
  $('animation-clock').addEventListener('change',e=>control({animation:{show_clock:e.target.checked}}));
  $('animation-pause').addEventListener('click',()=>control({animation:{paused:!state?.animation?.paused}}));
  $('animation-seed').addEventListener('click',()=>control({animation:{seed:Math.floor(Math.random()*2147483647)}},'已生成新的画面。'));
  $('page-list').addEventListener('click',e=>{const button=e.target.closest('[data-page]');if(button)control({page:button.dataset.page});});
  $('rotation').addEventListener('change',e=>control({rotation:Number(e.target.value)}));$('fps').addEventListener('change',e=>control({fps:Number(e.target.value)}));$('interval').addEventListener('change',e=>control({interval:Number(e.target.value)}));$('auto').addEventListener('change',e=>control({auto:e.target.checked}));
  $('subscription-view').addEventListener('change',e=>control({subscription_view:e.target.value,subscription_auto:false}));
  $('subscription-bucket').addEventListener('change',e=>control({subscription_bucket:e.target.value}));
  $('subscription-auto').addEventListener('change',e=>control({subscription_auto:e.target.checked}));
  $('subscription-refresh').addEventListener('click',()=>control({action:'subscription_refresh'},'已请求刷新，短时间内的重复请求会合并。'));
  $('brightness').addEventListener('input',e=>$('brightness-value').textContent=e.target.value+'%');$('brightness').addEventListener('change',e=>control({brightness:Number(e.target.value)}));
  $('start-button').addEventListener('click',()=>control({action:'start'},'已开始向副屏发送画面。'));
  $('stop-button').addEventListener('click',()=>control({action:'stop'},'已停止输出；副屏保留最后一帧。'));
  $('focus-start').addEventListener('click',()=>control({action:state?.focus?.running?'focus_pause':'focus_start'}));$('focus-reset').addEventListener('click',()=>control({action:'focus_reset'}));
  $('note').addEventListener('input',()=>{noteDirty=true;$('note-count').textContent=$('note').value.length+' / 160';});
  $('save-note').addEventListener('click',async()=>{if(await control({note:$('note').value},'便签已保存。'))noteDirty=false;});
  async function showInfo(){const panel=$('device-details');panel.hidden=!panel.hidden;$('info-toggle').setAttribute('aria-expanded',String(!panel.hidden));if(panel.hidden||infoLoaded)return;try{const info=await request('/api/info');const d=info.device||{};const facts=[['设备',d.name||'TURZX 5.2'],['USB 标识',d.vid&&d.pid?`${d.vid}:${d.pid}`:'1CBE:0050'],['原生画布',`${d.native_width||720} × ${d.native_height||1280}`],['控制方式','USB 图像输出']];let html=`<div class="facts-grid">${facts.map(([k,v])=>`<div class="fact"><span>${safe(k)}</span>${safe(v)}</div>`).join('')}</div>`;
      const entries=info.verified_facts;if(Array.isArray(entries))html+=entries.slice(0,6).map(v=>`<p>${safe(typeof v==='string'?v:v.label?`${v.label}：${v.value??v.detail??''}`:v.fact??v.description??JSON.stringify(v))}</p>`).join('');else if(entries&&typeof entries==='object')html+=Object.entries(entries).slice(0,6).map(([k,v])=>`<p>${safe(k)}：${safe(typeof v==='string'?v:JSON.stringify(v))}</p>`).join('');
      const sources=Array.isArray(info.sources)?info.sources:[];html+=`<div class="source-links">${sources.filter(s=>/^https?:\/\//i.test(typeof s==='string'?s:s.url)).map(s=>{const url=typeof s==='string'?s:s.url,label=typeof s==='string'?'查看来源':s.title||s.name||s.label||'查看来源';return `<a href="${safe(url)}" target="_blank" rel="noopener noreferrer">${safe(label)} ↗</a>`;}).join('')}</div>`;$('device-facts').innerHTML=html;infoLoaded=true;}catch{$('device-facts').innerHTML='<p>暂时无法读取设备资料。稍后收起并重新打开即可重试。</p>';}}
  $('info-toggle').addEventListener('click',showInfo);$('info-close').addEventListener('click',()=>{$('device-details').hidden=true;$('info-toggle').setAttribute('aria-expanded','false');});
  document.addEventListener('keydown',e=>{if(/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)||e.ctrlKey||e.metaKey||e.altKey)return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const i=pages.findIndex(p=>p.id===state?.page),n=(i+(e.key==='ArrowRight'?1:-1)+pages.length)%pages.length;control({page:pages[n].id});}});
  new ResizeObserver(previewSize).observe($('preview-box'));$('display-preview').addEventListener('load',previewSize);previewSize();poll();setInterval(poll,1200);
})();
