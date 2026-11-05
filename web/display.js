(() => {
  'use strict';
  const root = document.getElementById('display');
  const params = new URLSearchParams(location.search);
  const renderer = params.get('renderer') === '1';
  const pinnedPage = params.get('page');
  const safe = value => String(value ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const number = (value, digits=0) => finite(value) ? value.toFixed(digits) : null;
  const metric = (value, unit='', digits=0) => finite(value) ? `${number(value,digits)}<span class="unit">${safe(unit)}</span>` : '<span class="unavailable">未接入</span>';
  let state = {page:'system',rotation:270,streaming:false,focus:{duration:1500,remaining:1500,running:false},note:'把注意力留给真正重要的事。'};
  let metrics = {};
  let failed = false;
  let stateReceivedAt = Date.now();
  let animationId = null;
  let lastAmbientPaint = 0;
  const dateFormat = new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'long',day:'numeric',weekday:'long'});
  const timeFormat = zone => new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  const time = (zone='Asia/Shanghai',withSeconds=false) => timeFormat(zone).format(new Date()).slice(0,withSeconds?8:5);
  const duration = seconds => {const n=Math.max(0,Math.ceil(finite(seconds)?seconds:1500));return `${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;};
  const stale = () => failed || !metrics.timestamp || Date.now()-Date.parse(metrics.timestamp)>6500;
  const sensorState = () => !metrics.timestamp ? ['','等待采样'] : stale()?['stale','数据已过期']:['live','本机实时'];
  const footer = (text,clock=true) => `<footer class="screen-foot"><span class="foot-note">${safe(text)}</span>${clock?`<time>${time()}</time>`:''}</footer>`;
  const header = (title,label,kind='') => `<header class="screen-head"><h1>${safe(title)}</h1>${label?`<span class="status ${kind}">${safe(label)}</span>`:'<span class="brand-name">TURZX STUDIO</span>'}</header>`;
  const level = value => `<div class="level"><i style="width:${finite(value)?Math.max(0,Math.min(100,value)):0}%"></i></div>`;
  const sample = entry => typeof entry==='number'?entry:typeof entry?.value==='number'?entry.value:NaN;
  function lineChart(histories,colors,height=140){
    const series=histories.map(history=>(Array.isArray(history)?history:[]).slice(-60).map(sample));
    const all=series.flat().filter(finite);
    if(!all.length)return '<div class="chart-empty">等待真实采样</div>';
    const maximum=Math.max(1,...all), count=Math.max(2,...series.map(a=>a.length)), w=600,h=height,pad=8;
    let paths='';
    series.forEach((list,j)=>{let d='',drawing=false;list.forEach((v,i)=>{if(!finite(v)){drawing=false;return;}const x=pad+i/(count-1)*(w-pad*2),y=h-pad-v/maximum*(h-pad*2);d+=`${drawing?'L':'M'}${x.toFixed(1)},${y.toFixed(1)} `;drawing=true;});paths+=`<path d="${d}" fill="none" stroke="${colors[j]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>`;});
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="实测历史曲线"><path d="M0 ${h-1}H${w} M0 ${h/2}H${w} M0 1H${w}" fill="none" stroke="currentColor" stroke-opacity=".14" stroke-width="1"/>${paths}</svg>`;
  }
  function rate(value){if(!finite(value))return '<span class="unavailable">未接入</span>';const units=['B/s','KiB/s','MiB/s','GiB/s'];let n=Math.max(0,value),i=0;while(n>=1024&&i<3){n/=1024;i++;}return `${n.toFixed(n>=100?0:n>=10?1:2)}<span class="unit">${units[i]}</span>`;}
  function uptime(value){if(!finite(value))return '运行时间未接入';const hours=Math.floor(value/3600);return `已运行 ${hours>=24?Math.floor(hours/24)+'天 ':''}${hours%24}小时 ${Math.floor(value/60)%60}分`;}
  function systemPage(){
    const cpu=metrics.cpu||{},mem=metrics.memory||{},gpu=metrics.gpu||{},disk=(metrics.disks||[])[0],s=sensorState();
    return `<section class="screen system-screen">${header('性能脉搏',s[1],s[0])}<div class="screen-main system-layout"><section class="cpu-channel"><div class="channel-name">CPU <small>${finite(cpu.logical)?cpu.logical+' 线程':''}</small></div><div class="cpu-number">${metric(cpu.percent,'%')}</div><div class="hardware-name">${safe(cpu.name||'处理器信息未接入')}</div><div class="cpu-chart">${lineChart([cpu.history],['#b6e7bb'],125)}</div><div class="chart-caption"><span>实测负载</span><span>最近 ${Math.min(60,(cpu.history||[]).length)} 次采样</span></div></section><div class="side-channels"><section class="sensor-block"><div class="sensor-line"><h2>内存</h2><strong>${metric(mem.percent,'%')}</strong></div>${level(mem.percent)}<div class="sensor-sub">${finite(mem.used_gb)&&finite(mem.total_gb)?`${mem.used_gb.toFixed(1)} / ${mem.total_gb.toFixed(1)} GiB`:'容量未接入'}</div></section><section class="sensor-block"><div class="sensor-line"><h2>GPU</h2><strong>${metric(gpu.percent,'%')}</strong></div><div class="sensor-sub">${safe(gpu.name||'显卡信息未接入')}</div><div class="sensor-sub">${finite(gpu.memory_used_gb)?'显存 '+gpu.memory_used_gb.toFixed(1)+(finite(gpu.memory_total_gb)?' / '+gpu.memory_total_gb.toFixed(1):'')+' GiB':finite(gpu.memory_total_gb)?'显存总量 '+gpu.memory_total_gb.toFixed(1)+' GiB':'显存用量未接入'}</div></section><section class="sensor-block"><div class="sensor-line"><h2>${disk?safe(disk.drive)+' 磁盘':'磁盘'}</h2><strong>${metric(disk?.percent,'%')}</strong></div><div class="sensor-sub">${disk&&finite(disk.used_gb)&&finite(disk.total_gb)?`${disk.used_gb.toFixed(0)} / ${disk.total_gb.toFixed(0)} GiB`:'容量未接入'}</div></section></div></div>${footer(finite(metrics.temperature_c)?`温度 ${metrics.temperature_c.toFixed(0)}°C · ${uptime(metrics.uptime_s)}`:`温度未接入 · ${uptime(metrics.uptime_s)}`)}</section>`;
  }
  function networkPage(){const n=metrics.network||{},s=sensorState(),active=(n.interfaces||[]).filter(x=>x.up).map(x=>x.name).join(' · ');return `<section class="screen network-screen">${header('网络航道',s[1],s[0])}<div class="screen-main network-layout"><div class="network-values"><section class="network-flow"><div class="label"><svg viewBox="0 0 24 24"><path d="M12 3v17m-6-6 6 6 6-6"/></svg>下载</div><div class="flow-value">${rate(n.recv_bps)}</div><div class="network-total">${finite(n.total_recv_gb)?'累计接收 '+n.total_recv_gb.toFixed(2)+' GiB':'累计流量未接入'}</div></section><section class="network-flow"><div class="label"><svg viewBox="0 0 24 24"><path d="M12 21V4m-6 6 6-6 6 6"/></svg>上传</div><div class="flow-value">${rate(n.sent_bps)}</div><div class="network-total">${finite(n.total_sent_gb)?'累计发送 '+n.total_sent_gb.toFixed(2)+' GiB':'累计流量未接入'}</div></section></div><div class="network-graph">${lineChart([n.history_down,n.history_up],['#9ed9f2','#c7baa1'],160)}<div class="chart-caption"><div class="network-legend"><span><i></i>下载</span><span><i></i>上传</span></div><span>实测吞吐</span></div></div></div>${footer(active||'等待网卡信息')}</section>`;}
  function clockPage(){const t=time('Asia/Shanghai',true);return `<section class="screen clock-screen">${header('此时此刻','北京时间')}<div class="screen-main clock-layout"><div class="clock-main"><span class="hhmm">${t.slice(0,5)}</span><span class="ss">${t.slice(6)}</span></div><div class="clock-date">${dateFormat.format(new Date())}</div><div class="world-times"><div class="world-zone"><span>东京</span><strong>${time('Asia/Tokyo')}</strong></div><div class="world-zone"><span>伦敦</span><strong>${time('Europe/London')}</strong></div><div class="world-zone"><span>纽约</span><strong>${time('America/New_York')}</strong></div></div></div>${footer(state.note||'每个当下，都值得专注。',false)}</section>`;}
  function focusPage(){const f=state.focus||{},left=finite(f.remaining)?Math.max(0,f.remaining):1500,total=finite(f.duration)&&f.duration>0?f.duration:1500,done=Math.min(100,Math.max(0,(1-left/total)*100));const label=left===0?'这一段，完成了':f.running?'专注进行中':left<total?'稍作停留':'准备好，开始专注';return `<section class="screen focus-screen ${left===0?'focus-complete':''}">${header('专注空间',`${Math.round(total/60)} 分钟`)}<div class="screen-main focus-layout"><div class="focus-state-label">${label}</div><div class="focus-digits">${duration(left)}</div><div class="focus-progress"><i style="width:${done}%"></i></div><div class="focus-note">${safe(state.note||'只做眼前这一件事。')}</div></div>${footer(f.running?'把注意力留在这里。':left===0?'起身走走，让思绪呼吸。':'从电脑工作台开始或继续。')}</section>`;}
  function ambientPage(){return `<section class="screen ambient-screen"><canvas id="ambient-canvas" class="ambient-canvas" aria-label="随时间缓慢变化的原创几何轨道"></canvas><div class="ambient-overlay"><div><h1 class="ambient-title">缓慢轨道</h1><div class="ambient-sub">让目光，暂时离开数字。</div></div><div class="ambient-bottom"><time class="ambient-clock">${time()}</time><span class="ambient-kind">生成视觉 · ORBIT</span></div></div></section>`;}
  function mediaPage(){return `<section class="screen media-screen">${header('音乐一隅','未接入媒体源')}<div class="screen-main media-layout"><div class="record-art" aria-hidden="true"><div class="record-label"></div></div><div class="media-copy"><h2>留一个位置<br>给喜欢的声音。</h2><p>接入播放器后，<br>这里将显示封面、曲目与进度。</p><div class="media-source-state">当前没有媒体数据</div></div></div>${footer('播放信息尚未接入 · 不显示模拟曲目')}</section>`;}
  function guidePage(){return `<section class="screen guide-screen">${header('一块屏幕，更多可能','能力地图')}<div class="screen-main guide-layout"><section class="guide-column"><h2>现在可体验</h2><p class="guide-intro">本机数据与生成画面</p><ul class="guide-list"><li>性能 / 网络<small>真实采样与历史曲线</small></li><li>时钟 / 专注<small>时间、倒计时与便签</small></li><li>氛围 / 校准<small>原创图形与显示检查</small></li></ul></section><section class="guide-column"><h2>等待数据源</h2><p class="guide-intro">接入后才呈现真实内容</p><ul class="guide-list"><li>媒体 / 天气<small>播放器、城市与接口</small></li><li>任务 / 训练<small>进度、阶段与提醒</small></li><li>温度 / 功耗<small>兼容的传感器接口</small></li></ul></section><section class="guide-column"><h2>仍需验证</h2><p class="guide-intro">不从产品名称推断</p><ul class="guide-list"><li>触控 / 音频<small>未确认硬件能力</small></li><li>离线播放<small>存储与固件支持</small></li><li>扩展桌面<small>官网列出，尚待实测</small></li></ul></section></div>${footer('USB 图像输出 · 实际刷新能力以本机实测为准',false)}</section>`;}
  function calibratePage(){const bars=Array.from({length:8},()=>'<i></i>').join(''),gray=Array.from({length:11},(_,i)=>{let c=Math.round(i*25.5);return `<i style="background:rgb(${c},${c},${c})"></i>`;}).join('');return `<section class="screen calibrate-screen"><span class="edge-label tl">TL</span><span class="edge-label tr">TR</span><span class="edge-label bl">BL</span><span class="edge-label br">BR</span>${header('显示校准',`${innerWidth} × ${innerHeight}`)}<div class="screen-main calibrate-layout"><div class="calibration-bars">${bars}</div><div class="grayscale">${gray}</div><div class="calibration-middle"><div class="type-specimens"><span>24 px · 看清每一个细节 0123456789</span><span>28 px · 清晰来自合适的距离</span><span>32 px · 阅读舒适，信息从容</span><span>40 px · 大字，看得见</span></div><div class="circle-test" aria-label="正圆应没有拉伸"></div></div></div>${footer('四角完整 · 正圆不变形 · 灰阶可分辨',false)}</section>`;}
  const pages={system:systemPage,network:networkPage,clock:clockPage,focus:focusPage,ambient:ambientPage,media:mediaPage,guide:guidePage,calibrate:calibratePage};
  function paintAmbient(timestamp=Date.now()){
    const c=document.getElementById('ambient-canvas');if(!c)return;const w=innerWidth,h=innerHeight;c.width=w;c.height=h;const ctx=c.getContext('2d');const t=timestamp/1000;
    ctx.fillStyle='#0b1421';ctx.fillRect(0,0,w,h);const cx=w*.57,cy=h*.54,short=Math.min(w,h);ctx.save();ctx.translate(cx,cy);ctx.rotate(-.45+Math.sin(t/38)*.12);
    for(let i=0;i<36;i++){const r=short*(.2+i*.012),phase=t/15+i*.12;ctx.beginPath();ctx.ellipse(Math.sin(phase)*short*.04,Math.cos(phase*.6)*short*.03,r*1.55,r*.62,0,0,Math.PI*2);ctx.strokeStyle=`rgba(${i<18?'101,165,197':'187,146,113'},${.15+Math.sin(i/36*Math.PI)*.48})`;ctx.lineWidth=1.2;ctx.stroke();}
    ctx.restore();const a=t/12;const x=cx+Math.cos(a)*short*.37,y=cy+Math.sin(a)*short*.25;ctx.fillStyle='#e9c398';ctx.beginPath();ctx.arc(x,y,short*.014,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle='#3c6274';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(w*.08,h*.71);ctx.lineTo(w*.92,h*.29);ctx.stroke();
  }
  function render(){
    const page=pages[pinnedPage||state.page]?pinnedPage||state.page:'system';
    root.dataset.page=page;root.innerHTML=pages[page]();
    if(page==='ambient')paintAmbient();
    if(failed&&!['system','network'].includes(page)){root.insertAdjacentHTML('beforeend','<div class="offline-band">工作台连接中断</div>');}
  }
  window.renderFrame = async (nextState,nextMetrics) => {
    if(nextState){state={...state,...nextState};stateReceivedAt=Date.now();}
    if(nextMetrics)metrics=nextMetrics;
    failed=false;render();await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(resolve));window.renderReady=true;
  };
  async function poll(){try{const [sr,mr]=await Promise.all([fetch('/api/state',{cache:'no-store'}),fetch('/api/metrics',{cache:'no-store'})]);if(!sr.ok||!mr.ok)throw new Error('poll');await window.renderFrame(await sr.json(),await mr.json());}catch{failed=true;render();window.renderReady=true;}}
  function animate(timestamp){if(root.dataset.page==='ambient'&&timestamp-lastAmbientPaint>=200){paintAmbient();lastAmbientPaint=timestamp;}animationId=requestAnimationFrame(animate);}
  render();
  document.fonts.ready.then(()=>{window.renderReady=true;});
  if(!renderer){poll();setInterval(poll,1000);if(!matchMedia('(prefers-reduced-motion: reduce)').matches)animationId=requestAnimationFrame(animate);}
  addEventListener('resize',render);
})();
