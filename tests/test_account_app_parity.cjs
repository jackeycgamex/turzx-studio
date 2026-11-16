const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const appURL=process.env.ACCOUNT_APP_URL||'http://127.0.0.1:8766';
const screenURL=process.env.SCREEN_URL||'http://127.0.0.1:8765';
const now=1794807000000;
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const screen=await browser.newPage(),app=await browser.newPage();
    const errors=[];
    for(const page of [screen,app]){
      page.on('pageerror',error=>errors.push(error.message));
      await page.addInitScript(value=>{Date.now=()=>value;},now);
    }
    let state;
    await screen.route('**/api/state',route=>route.fulfill({json:state}));
    await screen.route('**/api/metrics',route=>route.fulfill({json:{}}));
    await app.route('**/api/session',route=>route.fulfill({json:{token:'test'}}));
    await app.route('**/api/app-state',route=>route.fulfill({json:{claude:state.claude,style:state,busy:false}}));
    await app.route('**/api/switch',()=>{throw Error('Parity verification must not switch accounts');});
    fs.mkdirSync('runtime/account-app-validation',{recursive:true});
    const scenarios=Array.from({length:6},(_,count)=>({count,background:'thought'}));
    for(const background of ['stand','greeting','floral','celestial','atelier','botanical','glasswave','paperland','none'])scenarios.push({count:3,background});
    let checked=0;
    for(const [width,height] of [[1280,720],[720,1280]]){
      for(const {count,background} of scenarios){
        state={page:'cswap',claude_background:background,image_brightness:108,image_saturation:94,image_fade:0,claude:{status:'ok',stale:false,active_account_id:'2',accounts:Array.from({length:count},(_,i)=>({id:String(i+1),label:`账号 ${i+1}`,status:'ok',updated_at:now/1000,subscription_type:'Max',usage:{five_hour:{utilization:20+i*10,resets_at:now/1000+7200},seven_day:{utilization:44,resets_at:now/1000+86400},seven_day_fable:{utilization:12,resets_at:now/1000+90000}}}))}};
        for(const [page,url] of [[screen,screenURL+'/display.html?page=cswap'],[app,appURL]]){
          await page.setViewportSize({width,height});
          await page.goto(url);
          await page.waitForSelector(`.account-scene[data-count="${count}"]`);
          await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.querySelectorAll('.account-wallpaper img')].map(img=>img.decode()));});
        }
        await app.addStyleTag({content:'#feedback{visibility:hidden}'});
        const label=`${width}x${height}-${count}-${background}`;
        const expected=await screen.locator('#display').screenshot();
        const actual=await app.locator('#display').screenshot();
        if(!expected.equals(actual)||count===3&&background==='thought'){
          fs.writeFileSync(`runtime/account-app-validation/screen-${label}.png`,expected);
          fs.writeFileSync(`runtime/account-app-validation/app-${label}.png`,actual);
        }
        assert(expected.equals(actual),`App differs from display: ${label}`);
        checked++;
      }
    }
    assert.deepEqual(errors,[]);
    console.log(`Passed: ${checked} exact image comparisons, 0–5 accounts, 10 backgrounds, landscape and portrait.`);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
