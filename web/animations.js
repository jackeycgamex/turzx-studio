/* Original, seeded Canvas animations. A frame depends only on time and settings. */
(() => {
  'use strict';
  const TAU = Math.PI * 2;
  const definitions = {
    orbit: {title:'缓慢轨道', subtitle:'层层轨道，保持自己的节奏。', color:'#e9c398'},
    aurora: {title:'极光夜航', subtitle:'把一片流动的夜空，留在桌边。', color:'#9ce7cb'},
    flow: {title:'流光织场', subtitle:'细线交错，像一阵看得见的风。', color:'#e8bd8a'},
    stars: {title:'星际漫游', subtitle:'缓缓前行，让远方接近。', color:'#b4d6f3'}
  };
  const cache = new Map();
  function points(seed, count) {
    const key=seed+':'+count;
    if(cache.has(key))return cache.get(key);
    let a=seed>>>0;
    const random=()=>{a=(a+0x6D2B79F5)>>>0;let t=a;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
    const result=Array.from({length:count},()=>[random(),random(),random(),random()]);
    if(cache.size>8)cache.clear();cache.set(key,result);return result;
  }
  function backdrop(ctx,w,h,color){ctx.fillStyle=color;ctx.fillRect(0,0,w,h);}
  function glow(ctx,x,y,r,color){const g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,color);g.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);}
  function orbit(ctx,w,h,t,o){
    backdrop(ctx,w,h,'#0b1421');
    const short=Math.min(w,h),cx=w*.55,cy=h*.52,n=o.detail==='light'?22:36;
    ctx.save();ctx.translate(cx,cy);ctx.rotate(-.45+Math.sin(t/38)*.12);
    for(let i=0;i<n;i++){
      const f=i/(n-1),r=short*(.2+f*.43),p=t/15+f*4.3+o.seed*.03;
      ctx.beginPath();ctx.ellipse(Math.sin(p)*short*.04,Math.cos(p*.6)*short*.03,r*1.55,r*.62,0,0,TAU);
      ctx.strokeStyle=`rgba(${f<.5?'101,165,197':'187,146,113'},${.18+Math.sin(f*Math.PI)*.5})`;ctx.lineWidth=1.5;ctx.stroke();
    }
    ctx.restore();const a=t/12;ctx.fillStyle='#e9c398';ctx.beginPath();ctx.arc(cx+Math.cos(a)*short*.37,cy+Math.sin(a)*short*.25,short*.014,0,TAU);ctx.fill();
  }
  function aurora(ctx,w,h,t,o){
    backdrop(ctx,w,h,'#07131e');
    glow(ctx,w*.7,h*.38,Math.max(w,h)*.72,'rgba(21,68,79,.6)');
    const stars=points(o.seed,o.detail==='light'?48:85);
    for(const [x,y,z,p] of stars){ctx.fillStyle=`rgba(190,224,225,${.2+.24*(.5+.5*Math.sin(t*.12+p*TAU))})`;ctx.beginPath();ctx.arc(x*w,y*h*.86,.7+z*.8,0,TAU);ctx.fill();}
    const ribbons=o.detail==='light'?3:5;
    for(let k=0;k<ribbons;k++){
      const phase=t*.13+k*.65+o.seed*.013;
      const mid=(u)=>h*(.34+k*.045+.1*Math.sin(u*5.2+phase)+.045*Math.sin(u*10.5-phase*.7));
      const depth=(u)=>h*(.07+.045*Math.sin(u*4.2+phase*.6));
      const gradient=ctx.createLinearGradient(0,h*.12,0,h*.73);
      gradient.addColorStop(0,'rgba(56,210,167,0)');gradient.addColorStop(.38,`rgba(${k%2?'98,133,211':'68,226,168'},.13)`);gradient.addColorStop(.62,'rgba(112,238,190,.22)');gradient.addColorStop(1,'rgba(64,124,155,0)');
      ctx.beginPath();for(let i=0;i<=80;i++){const u=i/80,x=u*w,y=mid(u);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);}for(let i=80;i>=0;i--){const u=i/80;ctx.lineTo(u*w,mid(u)+depth(u));}ctx.closePath();ctx.fillStyle=gradient;ctx.fill();
      ctx.beginPath();for(let i=0;i<=80;i++){const u=i/80;const x=u*w,y=mid(u)+depth(u)*.8;if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);}ctx.strokeStyle=`rgba(${k%2?'153,185,227':'143,244,198'},.23)`;ctx.lineWidth=1.2;ctx.stroke();
    }
    // A quiet silhouette anchors the luminous sky without a downloaded image.
    ctx.fillStyle='#081018';ctx.beginPath();ctx.moveTo(0,h);ctx.lineTo(0,h*.81);for(let i=0;i<=24;i++){const x=i/24*w;const y=h*(.84-.05*Math.sin(i*.45)-.025*Math.sin(i*1.37));ctx.lineTo(x,y);}ctx.lineTo(w,h);ctx.fill();
  }
  function flow(ctx,w,h,t,o){
    backdrop(ctx,w,h,'#14151f');
    const n=o.detail==='light'?28:50;
    const curve=(u,v)=>[w*(u+.065*Math.sin(v*7+t*.14)),h*(v+.105*Math.sin(u*6.8-t*.13+o.seed*.021)*Math.sin(v*Math.PI))];
    for(let j=0;j<n;j++){
      const v=.15+j/(n-1)*.7;
      ctx.beginPath();for(let i=0;i<=65;i++){const [x,y]=curve(-.1+i/65*1.2,v);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);}
      ctx.strokeStyle=j<n*.55?`rgba(102,175,189,${.2+.32*Math.sin(j/n*Math.PI)})`:`rgba(222,169,117,${.18+.3*Math.sin(j/n*Math.PI)})`;
      ctx.lineWidth=1.4;ctx.stroke();
      if(j%4===0){const u=((t*.025+j*.071)%1.2)-.1;const [x,y]=curve(u,v);ctx.fillStyle=j<n*.55?'#abd9db':'#e8bd8a';ctx.beginPath();ctx.arc(x,y,2.6,0,TAU);ctx.fill();}
    }
  }
  function stars(ctx,w,h,t,o){
    backdrop(ctx,w,h,'#080f1b');const size=Math.min(w,h),cx=w*.5+Math.sin(t*.035)*size*.035,cy=h*.49;
    glow(ctx,cx,cy,size*.8,'rgba(27,50,90,.38)');
    for(const [sx,sy,sz,hue] of points(o.seed,o.detail==='light'?140:280)){
      const z=.22+(((sz-t*.026)%1+1)%1)*1.85;
      const x=(sx-.5)*2.6,y=(sy-.5)*2.6,f=size*.55;
      const px=cx+x*f/z,py=cy+y*f/z;
      if(px< -20||px>w+20||py< -20||py>h+20)continue;
      const a=Math.min(.9,Math.max(0,(2.1-z)/1.8))*Math.min(1,(z-.22)/.08);
      const color=hue>.83?'239,204,170':'183,214,247';
      ctx.strokeStyle=`rgba(${color},${a})`;ctx.lineWidth=.6+1.6*(1-z/2.1);
      ctx.beginPath();ctx.moveTo(cx+x*f/(z+.018),cy+y*f/(z+.018));ctx.lineTo(px,py);ctx.stroke();
      ctx.fillStyle=`rgba(${color},${a})`;ctx.beginPath();ctx.arc(px,py,Math.max(.45,1.5*(1-z/2.1)),0,TAU);ctx.fill();
    }
  }
  const painters={orbit,aurora,flow,stars};
  function draw(canvas,options={}){
    const w=Math.round(options.width||innerWidth),h=Math.round(options.height||innerHeight);
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    const o={preset:'orbit',time:0,seed:52,detail:'balanced',show_clock:true,...options};
    const ctx=canvas.getContext('2d',{alpha:true});ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;
    (painters[o.preset]||painters.orbit)(ctx,w,h,o.time,o);
    if(o.show_clock){
      const def=definitions[o.preset]||definitions.orbit;
      const inset=Math.min(w,h)*.06;
      const shade=ctx.createLinearGradient(0,0,0,h);shade.addColorStop(0,'rgba(0,0,0,.22)');shade.addColorStop(.25,'rgba(0,0,0,0)');shade.addColorStop(.72,'rgba(0,0,0,0)');shade.addColorStop(1,'rgba(0,0,0,.3)');ctx.fillStyle=shade;ctx.fillRect(0,0,w,h);
      ctx.fillStyle='#edf3ed';ctx.font=`550 ${Math.round(Math.min(w,h)*.049)}px Manrope, Microsoft YaHei, sans-serif`;ctx.textBaseline='top';ctx.fillText(def.title,inset,inset);
      ctx.font=`500 ${Math.round(Math.min(w,h)*.089)}px Manrope, Microsoft YaHei, sans-serif`;ctx.textBaseline='alphabetic';
      const clock=options.clock_text||new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());
      ctx.fillStyle=def.color;ctx.fillText(clock,inset,h-inset);
      ctx.font=`450 ${Math.round(Math.min(w,h)*.03)}px Manrope, Microsoft YaHei, sans-serif`;ctx.fillStyle='#b1c2c8';ctx.textAlign='right';ctx.fillText(o.paused?'动画已暂停':'生成动画',w-inset,h-inset);ctx.textAlign='left';
    }
  }
  window.TurzxAnimations={draw,definitions};
})();
